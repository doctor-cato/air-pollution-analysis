"""Profile the public AirNow Hanoi mirror without approving it as a source.

The script writes only derived evidence (a JSON manifest) and keeps downloaded
CSV payloads in a caller-selected directory.  It intentionally does not merge
VN002 with VN001, write canonical data, or update tracked provenance: those
actions require a reviewed CP0 source decision.
"""

from __future__ import annotations

import argparse
import csv
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
RAW_BASE = f"https://raw.githubusercontent.com/{REPOSITORY}/{BRANCH}/"
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


def profile_csv(path: Path, path_year: int, kind: str) -> dict[str, Any]:
    frame = pd.read_csv(path)
    schema = list(frame.columns)
    date_column = "Date (LT)" if "Date (LT)" in frame.columns else "Date (LST)"
    value_column = "Raw Conc." if "Raw Conc." in frame.columns else "Value"
    parsed = pd.to_datetime(frame[date_column], errors="coerce", format="mixed")
    actual_years = sorted({int(year) for year in parsed.dropna().dt.year.unique()})
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
        "actual_years": actual_years,
        "row_count": int(len(frame)),
        "hanoi_principal_rows": int(len(observed)),
        "valid_raw_concentration_rows": int(valid.sum()),
        "duplicate_timestamps_within_file": duplicate_timestamps,
        "minimum_timestamp": None if observed.empty else observed["timestamp"].min().isoformat(),
        "maximum_timestamp": None if observed.empty else observed["timestamp"].max().isoformat(),
    }


def coverage_from_downloads(files: list[dict[str, Any]], raw_dir: Path) -> dict[str, Any]:
    """Report union coverage while exposing YTD/MTD duplicate observations."""
    rows: list[pd.DataFrame] = []
    for file in files:
        frame = pd.read_csv(raw_dir / Path(file["path"]).name)
        date_column = "Date (LT)" if "Date (LT)" in frame.columns else "Date (LST)"
        value_column = "Raw Conc." if "Raw Conc." in frame.columns else "Value"
        keep = (
            frame["Site"].astype(str).str.strip().str.casefold().eq("hanoi")
            & frame["Parameter"].astype(str).str.strip().str.upper().eq("PM2.5 - PRINCIPAL")
        )
        selected = frame.loc[keep, [date_column, value_column]].copy()
        selected["timestamp"] = pd.to_datetime(selected[date_column], errors="coerce", format="mixed")
        selected["valid_raw"] = pd.to_numeric(selected[value_column], errors="coerce").ge(0)
        rows.append(selected[["timestamp", "valid_raw"]].dropna(subset=["timestamp"]))
    all_rows = pd.concat(rows, ignore_index=True)
    duplicate_source_rows = int(all_rows.duplicated(subset=["timestamp"]).sum())
    # A timestamp is valid when at least one retained file has a valid observed
    # raw concentration.  This never fills a missing value with NowCast.
    union = all_rows.groupby("timestamp", as_index=False)["valid_raw"].max()
    monthly: list[dict[str, Any]] = []
    for period in pd.period_range("2022-01", "2025-12", freq="M"):
        start, end = period.start_time, period.end_time.floor("h")
        grid = pd.date_range(start, end, freq="h")
        present = union[(union["timestamp"] >= start) & (union["timestamp"] <= end)].set_index("timestamp")["valid_raw"]
        valid_grid = present.reindex(grid, fill_value=False).astype(bool)
        missing = ~valid_grid
        gap_lengths = missing.ne(missing.shift(fill_value=False)).cumsum()
        longest_gap = int(missing.groupby(gap_lengths).sum().max()) if missing.any() else 0
        monthly.append({
            "month": str(period),
            "expected_hours": len(grid),
            "observed_hours": int(present.size),
            "valid_hours": int(valid_grid.sum()),
            "missing_or_invalid_hours": int(missing.sum()),
            "longest_gap_hours": longest_gap,
        })
    annual = []
    for year in range(2022, 2026):
        subset = [row for row in monthly if row["month"].startswith(str(year))]
        annual.append({
            "year": year,
            "expected_hours": sum(row["expected_hours"] for row in subset),
            "observed_hours": sum(row["observed_hours"] for row in subset),
            "valid_hours": sum(row["valid_hours"] for row in subset),
            "missing_or_invalid_hours": sum(row["missing_or_invalid_hours"] for row in subset),
            "longest_gap_hours": max(row["longest_gap_hours"] for row in subset),
        })
    return {"duplicate_source_rows_ytd_mtd": duplicate_source_rows, "monthly": monthly, "annual": annual}


def run(output: Path, raw_dir: Path) -> dict[str, Any]:
    source_commit = fetch_json(f"{API_BASE}/commits/{BRANCH}")["sha"]
    tree = fetch_json(f"{API_BASE}/git/trees/{BRANCH}?recursive=1")["tree"]
    files = []
    raw_dir.mkdir(parents=True, exist_ok=True)
    for item in tree:
        match = PATH_RE.match(item["path"])
        if not match:
            continue
        path_year, named_year, kind = int(match.group(1)), int(match.group(2)), match.group(3)
        local = raw_dir / Path(item["path"]).name
        local.write_bytes(fetch_bytes(RAW_BASE + item["path"]))
        item_profile = profile_csv(local, path_year, kind)
        item_profile.update({"path": item["path"], "git_blob_sha": item["sha"], "named_year": named_year})
        files.append(item_profile)

    files.sort(key=lambda row: row["path"])
    wrong_year_paths = [row["path"] for row in files if row["path_year"] != row["named_year"] or row["actual_years"] != [row["named_year"]]]
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
        "wrong_year_or_cross_year_paths": wrong_year_paths,
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
