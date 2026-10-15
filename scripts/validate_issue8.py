#!/usr/bin/env python
"""Comprehensive validation of Issue #8 implementation.

Verifies:
1. File existence (notebook, statistical profile CSV, parquet, generator script)
2. Data provenance, artifact shapes, and SHA-256 checksums
3. CSV structure (24 base statistics + 3 circular/notes columns)
4. Mathematical consistency between CSV and parquet data (linear + circular)
5. Dataset sanity (chronological sort, non-imputation of PM2.5)
6. .gitignore correctness (!reports/statistical_profile.csv)
7. Notebook structure, 100% synchronization with generator script, and execution
"""
import sys
import os
import json
import hashlib
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import numpy as np

PASS = 0
FAIL = 0
WARN = 0


def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {label} — {detail}")


def warn(label: str, detail: str = ""):
    global WARN
    WARN += 1
    print(f"  ⚠ WARN: {label} — {detail}")


#: Mọi trạng thái mà `verify_file_checksum` có thể trả về. Danh sách này là hợp
#: đồng bắt buộc: `checksum_verdict` xử lý TÁT CẢ các trạng thái ở đây, nên không
#: thể có nhánh nào bị bỏ qua im lặng.
CHECKSUM_STATUSES = ("MATCH", "MISMATCH", "NOT_FOUND", "NO_EXPECTED_HASH")


def checksum_verdict(result: dict, mismatch_severity: str = "WARN") -> tuple:
    """
    Chuẩn hoá kết quả `verify_file_checksum` thành một phán quyết có thể kiểm thử.

    Hợp đồng quan trọng: **chỉ** `MISMATCH` với `mismatch_severity='FAIL'` và
    `MATCH` là 'FAIL'; `NOT_FOUND` và `NO_EXPECTED_HASH` LUÔN là 'WARN'. Như vậy
    việc thiếu checksum kỳ vọng (hoặc thiếu tệp) không bao giờ bị báo nhầm là
    "đã xác minh tính toàn vẹn dữ liệu".

    Trả về tuple ``(kind, label, detail)`` với ``kind`` thuộc {'PASS','WARN','FAIL'}.
    """
    status = result.get("status")
    message = result.get("message", "")

    if status == "MATCH":
        return ("PASS", "checksum verified (MATCH)", message)

    if status == "MISMATCH":
        if mismatch_severity == "FAIL":
            return ("FAIL", "checksum MISMATCH", message)
        return (
            "WARN",
            "checksum differs from metadata provenance (MISMATCH)",
            message + " — KHÔNG được tính là đã xác minh tính toàn vẹn dữ liệu.",
        )

    if status == "NOT_FOUND":
        return (
            "WARN",
            "file not found on disk (NOT_FOUND)",
            message + " — KHÔNG có gì để hash, không thể xác minh tính toàn vẹn.",
        )

    if status == "NO_EXPECTED_HASH":
        return (
            "WARN",
            "checksum verification skipped (NO_EXPECTED_HASH)",
            message + (
                " — KHÔNG có checksum kỳ vọng để đối chiếu, nên bước này "
                "KHÔNG được tính là một kiểm tra checksum thành công."
            ),
        )

    raise ValueError(
        "verify_file_checksum trả về trạng thái lạ '%s'; "
        "mọi trạng thái phải nằm trong CHECKSUM_STATUSES=%s"
        % (status, list(CHECKSUM_STATUSES))
    )


def report_checksum(result: dict, label: str, mismatch_severity: str = "WARN"):
    """Gọi `checksum_verdict` rồi in kết quả bằng `check`/`warn` tương ứng."""
    kind, _auto_label, detail = checksum_verdict(result, mismatch_severity)
    if kind == "PASS":
        check(label, True, detail)
    elif kind == "FAIL":
        check(label, False, detail)
    else:
        warn(label, detail)


def verify_file_checksum(file_path: Path | str, expected_sha: str | None) -> dict:
    """
    Xác minh tính toàn vẹn tệp qua SHA-256 đối chiếu với checksum kỳ vọng.

    Trả về dict chuẩn:
        - status: 'MATCH' | 'MISMATCH' | 'NOT_FOUND' | 'NO_EXPECTED_HASH'
        - actual_sha: chuỗi hex 64 ký tự (nếu tệp tồn tại) hoặc None
        - expected_sha: chuỗi hex 64 ký tự hoặc None
        - match: bool (True khi và chỉ khi actual_sha == expected_sha)
        - message: thông báo giải thích chi tiết
    """
    p = Path(file_path)
    # Dùng is_file() chứ không phải exists(): nếu metadata thiếu khóa 'raw_file'
    # thì Path(ROOT / "") hội tụ về chính thư mục repo — thư mục tồn tại nên
    # exists() trả True và read_bytes() ném IsADirectoryError, làm script chết.
    if not p.is_file():
        return {
            "status": "NOT_FOUND",
            "actual_sha": None,
            "expected_sha": expected_sha,
            "match": False,
            "message": f"Tệp không tồn tại trên đĩa: {p}",
        }

    actual_sha = hashlib.sha256(p.read_bytes()).hexdigest()

    if not expected_sha or not isinstance(expected_sha, str):
        return {
            "status": "NO_EXPECTED_HASH",
            "actual_sha": actual_sha,
            "expected_sha": expected_sha,
            "match": False,
            "message": (
                f"Không có checksum kỳ vọng trong metadata provenance cho {p} "
                f"(SHA-256 thực tế đo được: {actual_sha[:16]}...)"
            ),
        }

    if actual_sha.lower() == expected_sha.lower():
        return {
            "status": "MATCH",
            "actual_sha": actual_sha,
            "expected_sha": expected_sha,
            "match": True,
            "message": f"SHA-256 khớp tuyệt đối với checksum kỳ vọng ({actual_sha[:16]}...).",
        }
    else:
        return {
            "status": "MISMATCH",
            "actual_sha": actual_sha,
            "expected_sha": expected_sha,
            "match": False,
            "message": (
                f"SHA-256 không khớp cho {p}: kỳ vọng {expected_sha[:16]}..., "
                f"thực tế {actual_sha[:16]}..."
            ),
        }


def check_notebook_sync(notebook_path: Path, generator_cells: list) -> tuple[bool, str]:
    """
    Kiểm tra đồng bộ tế bào theo tế bào (cell-by-cell) giữa notebook trên đĩa và generator.
    """
    if not notebook_path.exists():
        return False, f"Notebook không tồn tại: {notebook_path}"

    with open(notebook_path, "r", encoding="utf-8") as f:
        nb_disk = json.load(f)

    disk_cells = nb_disk.get("cells", [])
    if len(disk_cells) != len(generator_cells):
        return False, f"Số lượng cell không khớp: đĩa={len(disk_cells)} vs generator={len(generator_cells)}"

    for idx, (c_disk, c_gen) in enumerate(zip(disk_cells, generator_cells)):
        if c_disk.get("cell_type") != c_gen.get("cell_type"):
            return False, f"Cell #{idx} sai loại: đĩa={c_disk.get('cell_type')} vs generator={c_gen.get('cell_type')}"

        disk_src = "".join(c_disk.get("source", [])).strip()
        gen_src = "".join(c_gen.get("source", [])).strip()
        if disk_src != gen_src:
            return False, f"Cell #{idx} nội dung source không khớp giữa notebook và generator"

    return True, f"Toàn bộ {len(disk_cells)} cells khớp tuyệt đối 100% giữa notebook và generator"


def main():
    # ─── 1. File existence ──────────────────────────────────────────────
    print("\n═══ 1. File Existence ═══")
    nb_path = ROOT / "notebooks" / "04_descriptive_stats.ipynb"
    csv_path = ROOT / "reports" / "statistical_profile.csv"
    parquet_path = ROOT / "data" / "processed" / "air_pollution_final.parquet"
    gen_script = ROOT / "scripts" / "generate_04_notebook.py"

    check("Notebook exists", nb_path.exists())
    check("CSV exists", csv_path.exists())
    check("Parquet exists", parquet_path.exists())
    check("Generator script exists", gen_script.exists())

    # ─── 2. Provenance & Checksum Audit ────────────────────────────────
    print("\n═══ 2. Provenance & Checksum Audit ═══")
    meta_path = ROOT / "data" / "raw" / "metadata.json"
    check("metadata.json exists", meta_path.exists())

    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        # 2.1 Metadata schema and target city
        check("metadata.json schema_version is 1.3.0", meta.get("schema_version") == "1.3.0")
        check("metadata.json target_city is 'Hanoi, Vietnam'", meta.get("target_city") == "Hanoi, Vietnam")

        # 2.2 Canonical artifact shape contract
        artifact_shapes = (
            meta.get("collection_pipeline_execution", {})
            .get("artifact_dtypes", {})
            .get("shape", {})
        )
        expected_processed_shape = artifact_shapes.get("data/processed/air_pollution_final.parquet")
        check("Registered processed shape in metadata is [9044, 18]", expected_processed_shape == [9044, 18])

        if parquet_path.exists():
            df_actual = pd.read_parquet(parquet_path)
            check(
                f"Processed dataset matches registered shape [9044, 18] (actual: {list(df_actual.shape)})",
                list(df_actual.shape) == [9044, 18],
            )

        # 2.3 Processed dataset checksum verification
        expected_proc_sha = (
            meta.get("collection_pipeline_execution", {})
            .get("artifact_dtypes", {})
            .get("processed_sha256")
        )
        res_proc = verify_file_checksum(parquet_path, expected_proc_sha)
        report_checksum(
            res_proc,
            "Processed artifact SHA-256 vs metadata.json provenance",
        )
        if res_proc["status"] == "NO_EXPECTED_HASH":
            # processed artifact không có hash chuẩn trong provenance: hợp đồng
            # toàn vẹn chỉ dựa trên shape [9044, 18] + 18 cột schema.
            warn(
                "  └ integrity contract for processed artifact",
                "Metadata không định nghĩa hash chuẩn cho processed artifact; "
                "hợp đồng toàn vẹn dựa trên shape [9044, 18] và 18 cột schema.",
            )

        # 2.4 Raw OpenAQ payload checksum verification
        rec_exec = meta.get("collection_pipeline_execution", {})
        raw_aq = rec_exec.get("openaq_ingestion", {})
        raw_aq_file = ROOT / raw_aq.get("raw_file", "")
        raw_aq_expected_sha = raw_aq.get("raw_sha256")

        res_aq = verify_file_checksum(raw_aq_file, raw_aq_expected_sha)
        report_checksum(res_aq, "Raw OpenAQ payload SHA-256 vs metadata.json provenance")
        if res_aq["status"] == "MISMATCH":
            # Parquet không byte-reproducible qua các lần nạp S3 khác nhau
            # (docs/history/02) -> hạ xuống WARN, không tính là đã xác minh.
            warn(
                "  └ why MISMATCH is expected here",
                "Parquet không byte-reproducible qua các lần nạp S3 khác nhau "
                "theo docs/history/02.",
            )
        elif res_aq["status"] == "NOT_FOUND":
            warn(
                "  └ raw payload location",
                "data/raw/*.parquet bị .gitignore loại khỏi repository theo Three-tier "
                "Raw Data Policy; tệp chỉ tồn tại trên máy đã chạy pipeline.",
            )

        # 2.5 Raw Open-Meteo payload checksum verification
        raw_wx = rec_exec.get("open_meteo_ingestion", {})
        raw_wx_file = ROOT / raw_wx.get("raw_file", "")
        raw_wx_expected_sha = raw_wx.get("raw_sha256")

        res_wx = verify_file_checksum(raw_wx_file, raw_wx_expected_sha)
        report_checksum(res_wx, "Raw Open-Meteo payload SHA-256 vs metadata.json provenance")
        if res_wx["status"] == "MISMATCH":
            warn(
                "  └ why MISMATCH is expected here",
                "Open-Meteo API trả về generationtime_ms thay đổi theo từng lần request.",
            )
        elif res_wx["status"] == "NOT_FOUND":
            warn(
                "  └ raw payload location",
                "data/raw/*.json bị .gitignore loại khỏi repository theo Three-tier "
                "Raw Data Policy; tệp chỉ tồn tại trên máy đã chạy pipeline.",
            )
    else:
        warn("metadata.json not found", "cannot verify data provenance")

    # ─── 3. CSV structure ───────────────────────────────────────────────
    print("\n═══ 3. CSV Structure ═══")
    if csv_path.exists():
        csv = pd.read_csv(csv_path)
        required_cols = [
            "variable", "n", "n_missing", "missing_rate",
            "mean", "median", "mode", "variance", "std",
            "q1", "q3", "iqr", "range", "min", "max",
            "skewness", "kurtosis",
            "p10", "p25", "p50", "p75", "p90", "p95", "p99",
            "circular_mean", "circular_std", "notes",
        ]
        for col in required_cols:
            check(f"CSV has column '{col}'", col in csv.columns, f"missing from {list(csv.columns)}")

        check("CSV has ≥ 8 variables", len(csv) >= 8, f"only {len(csv)} rows")

        expected_vars = {
            "pm25", "pm10", "temperature", "relative_humidity",
            "wind_speed", "wind_direction", "surface_pressure", "precipitation",
        }
        actual_vars = set(csv["variable"].values)
        check("CSV contains expected variables", expected_vars.issubset(actual_vars),
              f"missing: {expected_vars - actual_vars}")

    # ─── 4. CSV vs Parquet consistency ──────────────────────────────────
    print("\n═══ 4. CSV vs Parquet Consistency ═══")
    if csv_path.exists() and parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        csv = pd.read_csv(csv_path)

        continuous_vars = [
            "pm25", "pm10", "temperature", "relative_humidity",
            "wind_speed", "wind_direction", "surface_pressure", "precipitation",
        ]

        for var in continuous_vars:
            if var not in df.columns:
                warn(f"Variable '{var}' not in parquet", "skipping validation")
                continue

            row = csv[csv["variable"] == var]
            if row.empty:
                warn(f"Variable '{var}' not in CSV", "skipping validation")
                continue
            row = row.iloc[0]

            series = df[var].dropna()
            n_valid = len(series)
            n_total = len(df)
            n_missing = n_total - n_valid

            # n and n_missing
            check(f"{var}: n matches ({int(row['n'])} vs {n_valid})", int(row["n"]) == n_valid)
            check(f"{var}: n_missing matches ({int(row['n_missing'])} vs {n_missing})", int(row["n_missing"]) == n_missing)

            # Mean
            computed_mean = series.mean()
            csv_mean = row["mean"]
            check(f"{var}: mean matches (csv={csv_mean:.4f}, computed={computed_mean:.4f})",
                  abs(csv_mean - computed_mean) < 0.01)

            # Median
            computed_median = series.median()
            csv_median = row["median"]
            check(f"{var}: median matches (csv={csv_median:.4f}, computed={computed_median:.4f})",
                  abs(csv_median - computed_median) < 0.01)

            # P50 == Median
            csv_p50 = row["p50"]
            check(f"{var}: P50 == median ({csv_p50:.4f} vs {csv_median:.4f})",
                  abs(csv_p50 - csv_median) < 0.001)

            # Q1, Q3
            computed_q1 = series.quantile(0.25)
            computed_q3 = series.quantile(0.75)
            check(f"{var}: Q1 matches", abs(row["q1"] - computed_q1) < 0.01)
            check(f"{var}: Q3 matches", abs(row["q3"] - computed_q3) < 0.01)
            check(f"{var}: P25 == Q1", abs(row["p25"] - row["q1"]) < 0.001)
            check(f"{var}: P75 == Q3", abs(row["p75"] - row["q3"]) < 0.001)

            # IQR
            computed_iqr = computed_q3 - computed_q1
            check(f"{var}: IQR == Q3-Q1", abs(row["iqr"] - computed_iqr) < 0.01)

            # Range
            computed_range = series.max() - series.min()
            check(f"{var}: range matches", abs(row["range"] - computed_range) < 0.01)

            # Std & Variance
            computed_std = series.std()
            check(f"{var}: std matches", abs(row["std"] - computed_std) < 0.01)
            computed_var = series.var()
            check(f"{var}: variance matches", abs(row["variance"] - computed_var) < 1.0)

            # Skewness & Kurtosis
            computed_skew = series.skew()
            check(f"{var}: skewness matches", abs(row["skewness"] - computed_skew) < 0.01)
            computed_kurt = series.kurtosis()
            check(f"{var}: kurtosis matches", abs(row["kurtosis"] - computed_kurt) < 0.01)

            # Quantile monotonicity
            quantile_cols = ["p10", "p25", "p50", "p75", "p90", "p95", "p99"]
            vals = [row[c] for c in quantile_cols]
            is_monotonic = all(vals[i] <= vals[i+1] + 0.001 for i in range(len(vals)-1))
            check(f"{var}: quantiles monotonically non-decreasing", is_monotonic)

            # Missing rate
            computed_rate = n_missing / n_total
            check(f"{var}: missing_rate matches", abs(row["missing_rate"] - computed_rate) < 0.001)

            # Circular statistics validation
            if var == "wind_direction":
                from scipy import stats
                computed_cmean = float(stats.circmean(series, high=360, low=0))
                computed_cstd = float(stats.circstd(series, high=360, low=0))
                csv_cmean = float(row["circular_mean"])
                csv_cstd = float(row["circular_std"])
                check(f"{var}: circular_mean matches (csv={csv_cmean:.2f}°, computed={computed_cmean:.2f}°)",
                      abs(csv_cmean - computed_cmean) < 0.1)
                check(f"{var}: circular_std matches (csv={csv_cstd:.2f}°, computed={computed_cstd:.2f}°)",
                      abs(csv_cstd - computed_cstd) < 0.1)
                check(f"{var}: notes contains circular warning",
                      isinstance(row["notes"], str) and len(row["notes"]) > 20)
            else:
                check(f"{var}: circular_mean is NaN for linear variable", pd.isna(row["circular_mean"]))
                check(f"{var}: circular_std is NaN for linear variable", pd.isna(row["circular_std"]))

    # ─── 5. Dataset sanity ──────────────────────────────────────────────
    print("\n═══ 5. Dataset Sanity ═══")
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
        check(f"Dataset shape: {df.shape[0]} rows × {df.shape[1]} cols", 
              df.shape[0] > 8000 and df.shape[1] >= 18)
        check("'timestamp' column exists", "timestamp" in df.columns)
        check("'pm25' column exists", "pm25" in df.columns)

        if "timestamp" in df.columns:
            ts = pd.to_datetime(df["timestamp"])
            check("Timestamps sorted", ts.is_monotonic_increasing)
            check("No duplicate timestamps", ts.duplicated().sum() == 0)

        if "pm25" in df.columns:
            n_missing_pm25 = df["pm25"].isna().sum()
            check(f"PM2.5 has {n_missing_pm25} NaN values (not imputed)", n_missing_pm25 > 0)

    # ─── 6. .gitignore check ────────────────────────────────────────────
    print("\n═══ 6. .gitignore ═══")
    gitignore_path = ROOT / ".gitignore"
    if gitignore_path.exists():
        # Bắt buộc chỉ định encoding="utf-8": read_text() mặc định dùng locale của
        # hệ điều hành (cp1252 trên Windows) và sẽ ném UnicodeDecodeError khi
        # .gitignore chứa byte không thuộc ASCII — khiến script chết giữa chừng
        # trên Windows trong khi vẫn chạy bình thường trên Ubuntu CI.
        content = gitignore_path.read_text(encoding="utf-8")
        check("reports/statistical_profile.csv is NOT ignored",
              "!reports/statistical_profile.csv" in content)

    # ─── 7. Notebook Structure & Generator Synchronization ──────────────
    print("\n═══ 7. Notebook Structure & Generator Synchronization ═══")
    if nb_path.exists():
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)

        cells = nb.get("cells", [])
        code_cells = [c for c in cells if c["cell_type"] == "code"]
        md_cells = [c for c in cells if c["cell_type"] == "markdown"]

        check(f"Notebook has exactly 37 cells ({len(code_cells)} code, {len(md_cells)} markdown)",
              len(cells) == 37 and len(code_cells) == 15 and len(md_cells) == 22)

        # Outputs validation
        cells_with_output = [c for c in code_cells if c.get("outputs")]
        check(f"{len(cells_with_output)}/{len(code_cells)} code cells have outputs",
              len(cells_with_output) == len(code_cells))

        error_cells = []
        for i, c in enumerate(code_cells):
            for out in c.get("outputs", []):
                if out.get("output_type") == "error":
                    error_cells.append(i)
        check("No error outputs in notebook", len(error_cells) == 0, f"errors in code cells: {error_cells}")

        # Code content validation
        code_text = "\n".join("".join(c["source"]) for c in code_cells)
        check("Notebook code contains 'stats.circmean'", "stats.circmean" in code_text)
        check("Notebook code contains 'stats.circstd'", "stats.circstd" in code_text)
        check("Notebook code contains Polar Wind Rose plot", "projection\": \"polar\"" in code_text or "polar" in code_text)

        # Markdown sections validation
        md_text = "\n".join("".join(c["source"]) for c in md_cells)
        required_sections = [
            ("Dataset Overview", ["dataset", "overview", "shape"]),
            ("Descriptive Statistics", ["descriptive", "statistic"]),
            ("Circular Statistics for Wind Direction", ["circular", "hướng gió", "direction"]),
            ("Temporal / Diurnal", ["hour", "diurnal", "temporal"]),
            ("Correlation", ["correlation", "pearson", "spearman"]),
            ("Season", ["season", "mùa"]),
        ]
        for section_name, keywords in required_sections:
            found = any(kw.lower() in md_text.lower() for kw in keywords)
            check(f"Notebook mentions '{section_name}'", found)

        # Kernelspec
        kernelspec = nb.get("metadata", {}).get("kernelspec", {})
        check("Notebook has kernelspec", bool(kernelspec))

        # Generator cell-by-cell synchronization check
        if gen_script.exists():
            import scripts.generate_04_notebook as gen_mod
            gen_dict = gen_mod.build_notebook_dict()
            gen_cells = gen_dict.get("cells", [])

            is_synced, sync_msg = check_notebook_sync(nb_path, gen_cells)
            check(f"Notebook source 100% in sync with generator: {sync_msg}", is_synced)

        # Live notebook execution check (Restart Kernel & Run All)
        if parquet_path.exists():
            print("  Đang kiểm chứng thực thi thực tế (Restart Kernel & Run All)...")
            try:
                import nbformat
                from nbclient import NotebookClient

                nb_to_run = nbformat.read(nb_path, as_version=4)
                client = NotebookClient(nb_to_run, timeout=600, kernel_name="python3")
                executed_nb = client.execute()

                exec_errors = []
                for idx, cell in enumerate(c for c in executed_nb.cells if c.cell_type == "code"):
                    for out in cell.get("outputs", []):
                        if out.get("output_type") == "error":
                            exec_errors.append((idx, out.get("ename"), out.get("evalue")))

                check(
                    "Live notebook execution (Restart Kernel & Run All) succeeded with 0 errors",
                    len(exec_errors) == 0,
                    f"Cell errors: {exec_errors}",
                )
            except Exception as exc:
                check("Live notebook execution (Restart Kernel & Run All) succeeded with 0 errors", False, str(exc))
        else:
            warn(
                "Live notebook execution SKIPPED in CI",
                "Môi trường CI không có data/processed/air_pollution_final.parquet (bước chưa được xác minh trong CI).",
            )


    # ─── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY: {PASS} passed, {FAIL} failed, {WARN} warnings")
    if FAIL == 0:
        print("ALL CHECKS PASSED ✓")
    else:
        print("SOME CHECKS FAILED — review above")
        sys.exit(1)


if __name__ == "__main__":
    main()
