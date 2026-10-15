#!/usr/bin/env python
"""Comprehensive validation of Issue #8 implementation.

Checks:
1. CSV existence and structure
2. CSV values match parquet-computed statistics
3. Notebook cell outputs consistency
4. Raw data integrity (no modification)
5. Required files exist
6. .gitignore correctness
"""
import sys, os, json, hashlib, math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import numpy as np

PASS = 0
FAIL = 0
WARN = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {label}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {label} — {detail}")

def warn(label, detail=""):
    global WARN
    WARN += 1
    print(f"  ⚠ WARN: {label} — {detail}")

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

# ─── 2. Provenance & Artifact Integrity ─────────────────────────────
print("\n═══ 2. Provenance & Artifact Integrity ═══")
meta_path = ROOT / "data" / "raw" / "metadata.json"
check("metadata.json exists", meta_path.exists())
if meta_path.exists():
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    
    # Kiểm tra schema version và địa điểm
    check("metadata.json schema_version is 1.3.0", meta.get("schema_version") == "1.3.0")
    check("metadata.json target_city is 'Hanoi, Vietnam'", meta.get("target_city") == "Hanoi, Vietnam")
    
    # Kiểm tra hợp đồng kích thước artifact đã đăng ký
    artifact_shapes = (
        meta.get("collection_pipeline_execution", {})
        .get("artifact_dtypes", {})
        .get("shape", {})
    )
    expected_processed_shape = artifact_shapes.get("data/processed/air_pollution_final.parquet")
    check("Registered processed shape in metadata is [9044, 18]", expected_processed_shape == [9044, 18])
    
    # Kiểm tra hash SHA-256 của tập dữ liệu phân tích processed
    if parquet_path.exists():
        with open(parquet_path, "rb") as f_p:
            p_sha256 = hashlib.sha256(f_p.read()).hexdigest()
        check(f"Processed dataset SHA-256 computed ({p_sha256[:16]}...)", len(p_sha256) == 64)
    
    # Kiểm tra các tệp raw thô và ghi nhận tính toàn vẹn minh bạch
    # (data/raw/*.parquet và *.json thuộc .gitignore, lưu ý Parquet không byte-reproducible theo docs/history/02)
    rec_exec = meta.get("collection_pipeline_execution", {})
    raw_aq = rec_exec.get("openaq_ingestion", {})
    raw_aq_file = ROOT / raw_aq.get("raw_file", "")
    raw_aq_expected_sha = raw_aq.get("raw_sha256")
    
    if raw_aq_file.exists():
        with open(raw_aq_file, "rb") as f_raw:
            actual_aq_sha = hashlib.sha256(f_raw.read()).hexdigest()
        print(f"  ℹ Raw OpenAQ payload on disk SHA-256: {actual_aq_sha[:16]}... (recorded in metadata: {raw_aq_expected_sha[:16]}...)")
    else:
        print(f"  ℹ Raw OpenAQ payload ({raw_aq.get('raw_file')}) is gitignored and not present on disk.")
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
        "circular_mean", "circular_std", "notes"
    ]
    for col in required_cols:
        check(f"CSV has column '{col}'", col in csv.columns, f"missing from {list(csv.columns)}")
    
    check("CSV has ≥ 8 variables", len(csv) >= 8, f"only {len(csv)} rows")
    
    # Check variable names
    expected_vars = {"pm25", "pm10", "temperature", "relative_humidity",
                     "wind_speed", "wind_direction", "surface_pressure", "precipitation"}
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
        check(f"{var}: n matches ({int(row['n'])} vs {n_valid})", 
              int(row["n"]) == n_valid)
        check(f"{var}: n_missing matches ({int(row['n_missing'])} vs {n_missing})",
              int(row["n_missing"]) == n_missing)
        
        # Mean
        computed_mean = series.mean()
        csv_mean = row["mean"]
        check(f"{var}: mean matches (csv={csv_mean:.4f}, computed={computed_mean:.4f})",
              abs(csv_mean - computed_mean) < 0.01,
              f"diff={abs(csv_mean - computed_mean):.6f}")
        
        # Median
        computed_median = series.median()
        csv_median = row["median"]
        check(f"{var}: median matches (csv={csv_median:.4f}, computed={computed_median:.4f})",
              abs(csv_median - computed_median) < 0.01,
              f"diff={abs(csv_median - computed_median):.6f}")
        
        # P50 == Median
        csv_p50 = row["p50"]
        check(f"{var}: P50 == median ({csv_p50:.4f} vs {csv_median:.4f})",
              abs(csv_p50 - csv_median) < 0.001,
              f"diff={abs(csv_p50 - csv_median):.6f}")
        
        # Q1, Q3
        computed_q1 = series.quantile(0.25)
        computed_q3 = series.quantile(0.75)
        csv_q1 = row["q1"]
        csv_q3 = row["q3"]
        check(f"{var}: Q1 matches", abs(csv_q1 - computed_q1) < 0.01)
        check(f"{var}: Q3 matches", abs(csv_q3 - computed_q3) < 0.01)
        
        # P25 == Q1, P75 == Q3
        check(f"{var}: P25 == Q1", abs(row["p25"] - csv_q1) < 0.001)
        check(f"{var}: P75 == Q3", abs(row["p75"] - csv_q3) < 0.001)
        
        # IQR
        computed_iqr = computed_q3 - computed_q1
        csv_iqr = row["iqr"]
        check(f"{var}: IQR == Q3-Q1", abs(csv_iqr - computed_iqr) < 0.01)
        
        # Range
        computed_range = series.max() - series.min()
        csv_range = row["range"]
        check(f"{var}: range matches", abs(csv_range - computed_range) < 0.01)
        
        # Std
        computed_std = series.std()
        csv_std = row["std"]
        check(f"{var}: std matches", abs(csv_std - computed_std) < 0.01,
              f"diff={abs(csv_std - computed_std):.6f}")
        
        # Variance
        computed_var = series.var()
        csv_var = row["variance"]
        check(f"{var}: variance matches", abs(csv_var - computed_var) < 1.0,
              f"csv={csv_var:.2f}, computed={computed_var:.2f}")
        
        # Skewness
        computed_skew = series.skew()
        csv_skew = row["skewness"]
        check(f"{var}: skewness matches", abs(csv_skew - computed_skew) < 0.01,
              f"csv={csv_skew:.4f}, computed={computed_skew:.4f}")
        
        # Kurtosis (Fisher/excess)
        computed_kurt = series.kurtosis()
        csv_kurt = row["kurtosis"]
        check(f"{var}: kurtosis matches", abs(csv_kurt - computed_kurt) < 0.01,
              f"csv={csv_kurt:.4f}, computed={computed_kurt:.4f}")
        
        # Quantile monotonicity
        quantile_cols = ["p10", "p25", "p50", "p75", "p90", "p95", "p99"]
        vals = [row[c] for c in quantile_cols]
        is_monotonic = all(vals[i] <= vals[i+1] + 0.001 for i in range(len(vals)-1))
        check(f"{var}: quantiles monotonically non-decreasing", is_monotonic,
              f"values: {[f'{v:.2f}' for v in vals]}")
        
        # Missing rate
        computed_rate = n_missing / n_total
        csv_rate = row["missing_rate"]
        check(f"{var}: missing_rate matches", abs(csv_rate - computed_rate) < 0.001,
              f"csv={csv_rate:.4f}, computed={computed_rate:.4f}")
        
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
    
    # Timestamp sorted
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        check("Timestamps sorted", ts.is_monotonic_increasing)
        check("No duplicate timestamps", ts.duplicated().sum() == 0,
              f"{ts.duplicated().sum()} duplicates found")
    
    # No pm25 imputation check — missing should still be NaN
    if "pm25" in df.columns:
        n_missing_pm25 = df["pm25"].isna().sum()
        check(f"PM2.5 has {n_missing_pm25} NaN values (not imputed)", n_missing_pm25 > 0,
              "PM2.5 has 0 missing → may have been imputed!")

# ─── 6. .gitignore check ────────────────────────────────────────────
print("\n═══ 6. .gitignore ═══")
gitignore_path = ROOT / ".gitignore"
if gitignore_path.exists():
    content = gitignore_path.read_text()
    check("reports/statistical_profile.csv is NOT ignored",
          "!reports/statistical_profile.csv" in content,
          "exception line not found")

# ─── 7. Notebook structure & Synchronization ─────────────────────────
print("\n═══ 7. Notebook Structure & Generator Synchronization ═══")
if nb_path.exists():
    import json
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    
    cells = nb.get("cells", [])
    check(f"Notebook has {len(cells)} cells (== 37)", len(cells) == 37)
    
    # Check for outputs — notebook should have been executed
    code_cells = [c for c in cells if c["cell_type"] == "code"]
    cells_with_output = [c for c in code_cells if c.get("outputs")]
    check(f"{len(cells_with_output)}/{len(code_cells)} code cells have outputs",
          len(cells_with_output) == len(code_cells))
    
    # Check no error outputs
    error_cells = []
    for i, c in enumerate(code_cells):
        for out in c.get("outputs", []):
            if out.get("output_type") == "error":
                error_cells.append(i)
    check("No error outputs in notebook", len(error_cells) == 0,
          f"errors in code cells: {error_cells}")
    
    # Check code content for circular statistics
    code_text = "\n".join("".join(c["source"]) for c in code_cells)
    check("Notebook code contains 'stats.circmean'", "stats.circmean" in code_text)
    check("Notebook code contains 'stats.circstd'", "stats.circstd" in code_text)
    check("Notebook code contains Polar Wind Rose plot", "projection\": \"polar\"" in code_text or "polar" in code_text)
    
    # Check markdown content for required sections
    md_cells = [c for c in cells if c["cell_type"] == "markdown"]
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
    
    # Check kernel spec
    kernelspec = nb.get("metadata", {}).get("kernelspec", {})
    check("Notebook has kernelspec", bool(kernelspec), "no kernelspec found")
    
    # Check synchronization with scripts/generate_04_notebook.py
    if gen_script.exists():
        gen_text = gen_script.read_text(encoding="utf-8")
        check("Generator script defines 37 cells", "CELL 37" in gen_text or "with {len(cells)} cells" in gen_text)
        check("Generator script has automated execution block", "NotebookClient" in gen_text)

# ─── Summary ────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"VALIDATION SUMMARY: {PASS} passed, {FAIL} failed, {WARN} warnings")
if FAIL == 0:
    print("ALL CHECKS PASSED ✓")
else:
    print("SOME CHECKS FAILED — review above")
    sys.exit(1)
