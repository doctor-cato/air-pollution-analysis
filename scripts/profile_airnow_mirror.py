"""Profile the public AirNow Hanoi mirror without approving it as a source.

The script writes only derived evidence (a JSON manifest) and keeps downloaded
CSV payloads in a caller-selected directory.  It intentionally does not merge
VN002 with VN001, write canonical data, or update tracked provenance: those
actions require a reviewed CP0 source decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


REPOSITORY = "dolekhanhdang/Air-Quality-Data-from-U.S.-Embassies"
BRANCH = "main"
PATH_RE = re.compile(r"^Data/Hanoi/(202[2-5])/Hanoi_PM2\.5_(202[2-5])_(YTD|\d{2}_MTD)\.csv$")
API_BASE = f"https://api.github.com/repos/{REPOSITORY}"


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "air-pollution-analysis-cp0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except OSError as error:
            last_error = error
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("unreachable") from last_error


def fetch_json(url: str) -> Any:
    return json.loads(fetch_bytes(url).decode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(payload: bytes) -> str:
    """Return the Git SHA-1 for a regular blob, independently of GitHub API."""
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def pinned_raw_url(source_commit: str, relative_path: str) -> str:
    """Build an immutable raw GitHub URL; never fetch a moving branch name."""
    return f"https://raw.githubusercontent.com/{REPOSITORY}/{source_commit}/{relative_path}"


def local_raw_path(raw_dir: Path, relative_path: str) -> Path:
    """Preserve the repository-relative path to prevent basename collisions."""
    return raw_dir / Path(relative_path)


def download_verified_blob(item: dict[str, Any], source_commit: str, raw_dir: Path) -> tuple[Path, str]:
    """Download one immutable blob and fail loudly if Git object identity differs."""
    destination = local_raw_path(raw_dir, item["path"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = fetch_bytes(pinned_raw_url(source_commit, item["path"]))
    actual_blob_sha = git_blob_sha1(payload)
    if actual_blob_sha != item["sha"]:
        raise ValueError(
            f"Git blob SHA mismatch for {item['path']}: expected {item['sha']}, got {actual_blob_sha}"
        )
    destination.write_bytes(payload)
    return destination, actual_blob_sha


def profile_csv(path: Path, path_year: int, kind: str) -> dict[str, Any]:
    frame = pd.read_csv(path)
    schema = list(frame.columns)
    date_column = "Date (LT)" if "Date (LT)" in frame.columns else "Date (LST)"
    value_column = "Raw Conc." if "Raw Conc." in frame.columns else "Value"
    principal = frame["Parameter"].astype(str).str.strip().str.upper().eq("PM2.5 - PRINCIPAL")
    hanoi = frame["Site"].astype(str).str.strip().str.casefold().eq("hanoi")
    observed = frame.loc[hanoi & principal, [date_column, value_column]].copy()
    observed["timestamp"] = pd.to_datetime(observed[date_column], errors="coerce", format="mixed")
    observed["raw"] = pd.to_numeric(observed[value_column], errors="coerce")
    observed = observed.dropna(subset=["timestamp"])
    valid = observed["raw"].ge(0)
    duplicate_timestamps = int(observed["timestamp"].duplicated().sum())
    return {
        "path_year": path_year,
        "kind": kind,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "schema": schema,
        "actual_years": sorted({int(year) for year in observed["timestamp"].dt.year.unique()}),
        "row_count": int(len(frame)),
        "hanoi_principal_rows": int(len(observed)),
        "valid_raw_concentration_rows": int(valid.sum()),
        "duplicate_timestamps_within_file": duplicate_timestamps,
        "minimum_timestamp": None if observed.empty else observed["timestamp"].min().isoformat(),
        "maximum_timestamp": None if observed.empty else observed["timestamp"].max().isoformat(),
    }


def coverage_from_downloads(files: list[dict[str, Any]], raw_dir: Path) -> dict[str, Any]:
    """Audit evidence without resolving conflicts by selecting an arbitrary value."""
    rows: list[pd.DataFrame] = []
    for file in files:
        frame = pd.read_csv(local_raw_path(raw_dir, file["path"]))
        date_column = "Date (LT)" if "Date (LT)" in frame.columns else "Date (LST)"
        value_column = "Raw Conc." if "Raw Conc." in frame.columns else "Value"
        keep = (
            frame["Site"].astype(str).str.strip().str.casefold().eq("hanoi")
            & frame["Parameter"].astype(str).str.strip().str.upper().eq("PM2.5 - PRINCIPAL")
        )
        selected = frame.loc[keep, [date_column, value_column]].copy()
        selected["timestamp"] = pd.to_datetime(selected[date_column], errors="coerce", format="mixed")
        selected["raw_value"] = pd.to_numeric(selected[value_column], errors="coerce")
        selected["source_path"] = file["path"]
        selected["source_kind"] = file["kind"]
        rows.append(selected[["timestamp", "raw_value", "source_path", "source_kind"]].dropna(subset=["timestamp"]))
    all_rows = pd.concat(rows, ignore_index=True)
    duplicate_groups = all_rows.groupby("timestamp", sort=True)
    duplicate_rows = int((duplicate_groups.size() - 1).clip(lower=0).sum())
    statuses = []
    for timestamp, group in duplicate_groups:
        values = group["raw_value"].tolist()
        # Missing is a distinct observation state; it must not be silently
        # replaced by a concurrent numeric value from another mirror file.
        tokens = {"<NA>" if pd.isna(value) else repr(float(value)) for value in values}
        is_duplicate = len(group) > 1
        is_conflict = is_duplicate and len(tokens) > 1
        value = values[0] if len(tokens) == 1 else None
        status = "valid" if value is not None and value >= 0 else "invalid"
        if is_conflict:
            status = "conflicting"
        statuses.append({
            "timestamp": timestamp,
            "status": status,
            "source_rows": len(group),
            "has_ytd_mtd_overlap": {"YTD", "MTD"}.issubset(set(group["source_kind"])),
        })
    union = pd.DataFrame(statuses)
    identical_duplicate_hours = int(sum(1 for row in statuses if row["source_rows"] > 1 and row["status"] != "conflicting"))
    conflicting_duplicate_hours = int(sum(1 for row in statuses if row["status"] == "conflicting"))
    ytd_mtd_overlap_hours = int(sum(1 for row in statuses if row["has_ytd_mtd_overlap"]))
    grid_start, grid_end = pd.Timestamp("2022-01-01"), pd.Timestamp("2025-12-31 23:00")
    calendar = pd.DataFrame({"timestamp": pd.date_range(grid_start, grid_end, freq="h")})
    calendar = calendar.merge(union[["timestamp", "status"]], on="timestamp", how="left")
    calendar["status"] = calendar["status"].fillna("missing")
    calendar["gap"] = calendar["status"].ne("valid")
    run_id = calendar["gap"].ne(calendar["gap"].shift(fill_value=False)).cumsum()
    calendar["gap_run"] = run_id
    monthly: list[dict[str, Any]] = []
    for period in pd.period_range("2022-01", "2025-12", freq="M"):
        start, end = period.start_time, period.end_time.floor("h")
        scoped = calendar[(calendar["timestamp"] >= start) & (calendar["timestamp"] <= end)]
        gap_sizes = calendar.loc[calendar["gap"]].groupby("gap_run").size()
        scoped_gap_ids = scoped.loc[scoped["gap"], "gap_run"].unique()
        longest_gap = int(gap_sizes.reindex(scoped_gap_ids).max()) if len(scoped_gap_ids) else 0
        monthly.append({
            "month": str(period),
            "expected_hours": int(len(scoped)),
            "observed_hours": int(scoped["status"].ne("missing").sum()),
            "valid_hours": int(scoped["status"].eq("valid").sum()),
            "missing_or_invalid_hours": int(scoped["status"].ne("valid").sum()),
            "conflicting_hours": int(scoped["status"].eq("conflicting").sum()),
            "longest_gap_hours": longest_gap,
        })
    annual = []
    for year in range(2022, 2026):
        start, end = pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-12-31 23:00")
        scoped = calendar[(calendar["timestamp"] >= start) & (calendar["timestamp"] <= end)]
        gap_sizes = calendar.loc[calendar["gap"]].groupby("gap_run").size()
        scoped_gap_ids = scoped.loc[scoped["gap"], "gap_run"].unique()
        annual.append({
            "year": year,
            "expected_hours": int(len(scoped)),
            "observed_hours": int(scoped["status"].ne("missing").sum()),
            "valid_hours": int(scoped["status"].eq("valid").sum()),
            "missing_or_invalid_hours": int(scoped["status"].ne("valid").sum()),
            "conflicting_hours": int(scoped["status"].eq("conflicting").sum()),
            "longest_gap_hours": int(gap_sizes.reindex(scoped_gap_ids).max()) if len(scoped_gap_ids) else 0,
        })
    return {
        "duplicate_source_rows": duplicate_rows,
        "ytd_mtd_overlap_hours": ytd_mtd_overlap_hours,
        "identical_duplicate_hours": identical_duplicate_hours,
        "conflicting_duplicate_hours": conflicting_duplicate_hours,
        "conflict_policy": "conflicting timestamps are not selected as valid observations",
        "monthly": monthly,
        "annual": annual,
    }


def run(output: Path, raw_dir: Path) -> dict[str, Any]:
    source_commit = fetch_json(f"{API_BASE}/commits/{BRANCH}")["sha"]
    tree = fetch_json(f"{API_BASE}/git/trees/{source_commit}?recursive=1")["tree"]
    files = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for item in tree:
        match = PATH_RE.match(item["path"])
        if not match:
            continue
        path_year, named_year, kind = int(match.group(1)), int(match.group(2)), match.group(3)
        local, verified_blob_sha = download_verified_blob(item, source_commit, raw_dir)
        item_profile = profile_csv(local, path_year, kind)
        item_profile.update({
            "path": item["path"],
            "download_url": pinned_raw_url(source_commit, item["path"]),
            "git_blob_sha": item["sha"],
            "verified_git_blob_sha": verified_blob_sha,
            "named_year": named_year,
        })
        files.append(item_profile)

    files.sort(key=lambda row: row["path"])
    files_in_wrong_directory = [row["path"] for row in files if row["path_year"] != row["named_year"]]
    files_with_cross_year_records = [row["path"] for row in files if row["actual_years"] != [row["named_year"]]]
    schema_counts = Counter(tuple(row["schema"]) for row in files)
    license_metadata = fetch_json(f"{API_BASE}").get("license")
    decision = {
        "status": "blocked",
        "approved_for_analysis": False,
        "reason": (
            "The secondary mirror has no repository license metadata and contains "
            "misfiled/cross-year MTD files. It remains an unapproved reference only; "
            "do not ingest, merge, or infer from it until provenance and terms are reviewed."
        ),
    }
    result = {
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repository": REPOSITORY,
        "branch": BRANCH,
        "source_commit": source_commit,
        "repository_license": license_metadata,
        "file_count": len(files),
        "files_in_wrong_directory": files_in_wrong_directory,
        "files_with_cross_year_records": files_with_cross_year_records,
        "schema_variants": [{"columns": list(schema), "file_count": count} for schema, count in schema_counts.items()],
        "coverage": coverage_from_downloads(files, raw_dir),
        "decision": decision,
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output, args.raw_dir)
    print(f"profiled {result['file_count']} files; decision={result['decision']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
