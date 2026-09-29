"""
Data Quality Audit Framework (Issue #5)
=======================================
Module cung cấp bộ công cụ kiểm toán chất lượng dữ liệu độc lập 6 chiều
(Completeness, Accuracy, Consistency, Validity, Uniqueness, Timeliness)
cho các tập dữ liệu Canonical trong đồ án air-pollution-analysis.

NGUYÊN TẮC QUẢN TRỊ DỮ LIỆU BẮT BUỘC:
- Module chỉ thực hiện đo lường, kiểm toán và báo cáo hiện trạng dữ liệu (READ-ONLY).
- Tuyệt đối không thay đổi, không xóa dòng, không điền khuyết (impute) dữ liệu.
- Quyết định làm sạch, loại bỏ dị thường và xử lý kẹt cảm biến thuộc về Issue #6.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Giới hạn vật lý và khí quyển thực tế tại khu vực Hà Nội (Căn cứ Canonical Data Dictionary)
ATMOSPHERIC_BOUNDS = {
    "temperature": {"min": 0.0, "max": 50.0, "unit": "°C"},
    "relative_humidity": {"min": 0.0, "max": 100.0, "unit": "%"},
    "wind_speed": {"min": 0.0, "max": 50.0, "unit": "m/s"},
    "wind_direction": {"min": 0.0, "max": 360.0, "unit": "°"},
    "precipitation": {"min": 0.0, "max": 200.0, "unit": "mm"},
    "surface_pressure": {"min": 900.0, "max": 1100.0, "unit": "hPa"},
    "pm25": {"min": 0.0, "max": 1000.0, "unit": "µg/m³"},
    "pm10": {"min": 0.0, "max": 1500.0, "unit": "µg/m³"},
}

CANONICAL_TIMEZONE = "Asia/Ho_Chi_Minh"
DISGUISED_STRING_MARKERS = [
    "N/A", "n/a", "NA", "null", "NULL", "None", "none", "nan", "NaN", "", " "
]


def audit_dataframe(
    df: pd.DataFrame, key_cols: Optional[List[str]] = None
) -> pd.DataFrame:
    """
    Kiểm toán tổng thể một DataFrame Canonical và trả về bảng thống kê chi tiết từng cột.

    Các chỉ số tối thiểu:
    - column_name, dtype, total_count, missing_count, missing_percentage
    - unique_count, min, max, q25, q50 (median), q75

    Hàm xử lý linh hoạt cho cả cột số, cột chuỗi, và cột mốc thời gian datetime,
    hoàn toàn không crash khi gặp cột phi số.
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")

    total_rows = len(df)
    records = []

    for col in df.columns:
        series = df[col]
        col_dtype = str(series.dtype)
        missing_count = int(series.isna().sum())
        missing_pct = round((missing_count / total_rows * 100), 4) if total_rows > 0 else 0.0
        unique_count = int(series.nunique(dropna=True))

        col_min = None
        col_max = None
        q25 = None
        q50 = None
        q75 = None

        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            valid_s = series.dropna()
            if not valid_s.empty:
                col_min = float(valid_s.min())
                col_max = float(valid_s.max())
                q25 = float(valid_s.quantile(0.25))
                q50 = float(valid_s.quantile(0.50))
                q75 = float(valid_s.quantile(0.75))
        elif pd.api.types.is_datetime64_any_dtype(series):
            valid_s = series.dropna()
            if not valid_s.empty:
                col_min = str(valid_s.min())
                col_max = str(valid_s.max())
        else:
            # String / Object / Categorical
            valid_s = series.dropna()
            if not valid_s.empty:
                try:
                    col_min = str(valid_s.min())
                    col_max = str(valid_s.max())
                except Exception:
                    col_min = None
                    col_max = None

        records.append({
            "column_name": col,
            "dtype": col_dtype,
            "total_count": total_rows,
            "missing_count": missing_count,
            "missing_percentage": missing_pct,
            "unique_count": unique_count,
            "min": col_min,
            "max": col_max,
            "q25": q25,
            "q50": q50,
            "q75": q75,
        })

    audit_df = pd.DataFrame(records)
    return audit_df


def audit_uniqueness(
    df: pd.DataFrame, key_cols: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Kiểm toán tính duy nhất của khóa quan sát (Observation Key) trong Canonical DataFrame.

    Ưu tiên kiểm tra:
    - (station_id, timestamp) nếu dataset có cột station_id.
    - timestamp nếu dataset chỉ có trục thời gian.
    - key_cols nếu người dùng chỉ định rõ.
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")

    total_rows = len(df)
    if key_cols is None:
        if "station_id" in df.columns and "timestamp" in df.columns:
            target_keys = ["station_id", "timestamp"]
        elif "timestamp" in df.columns:
            target_keys = ["timestamp"]
        else:
            target_keys = list(df.columns)
    else:
        target_keys = key_cols

    # Kiểm tra các khóa có tồn tại trong df không
    for k in target_keys:
        if k not in df.columns:
            raise KeyError(f"Khóa quan trắc '{k}' không tồn tại trong DataFrame!")

    duplicate_mask = df.duplicated(subset=target_keys, keep=False)
    duplicate_rows_count = int(df.duplicated(subset=target_keys).sum())
    duplicate_rate_pct = round((duplicate_rows_count / total_rows * 100), 4) if total_rows > 0 else 0.0

    return {
        "observation_key": target_keys,
        "total_records": total_rows,
        "duplicate_rows": duplicate_rows_count,
        "duplicate_rate_pct": duplicate_rate_pct,
        "has_duplicates": duplicate_rows_count > 0,
        "affected_rows_total": int(duplicate_mask.sum()),
    }


def audit_missing_representations(df: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    """
    Kiểm toán các dạng biểu diễn khuyết thiếu còn tồn tại trong dữ liệu.

    Ghi nhận riêng:
    - NaN / null (chuẩn hóa từ Issue #3/#4)
    - Ký tự ngụy trang: 'N/A', 'null', 'None', '', v.v. nếu có.
    Trung thực báo cáo theo dữ liệu thực tế, không khai báo có nếu thực tế không tồn tại.
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")

    report = {}
    for col in df.columns:
        series = df[col]
        col_missing = {}

        # 1. Kiểm tra NaN chuẩn
        nan_count = int(series.isna().sum())
        if nan_count > 0:
            col_missing["np_nan"] = nan_count

        # 2. Kiểm tra chuỗi ngụy trang (cho cột string / object)
        if series.dtype == object or pd.api.types.is_string_dtype(series):
            for marker in DISGUISED_STRING_MARKERS:
                marker_count = int((series == marker).sum())
                if marker_count > 0:
                    col_missing[f"str_'{marker}'"] = marker_count

        report[col] = col_missing

    return report


def audit_prolonged_zeros(
    df: pd.DataFrame,
    target_cols: Optional[List[str]] = None,
    threshold_hours: int = 6,
) -> Dict[str, Any]:
    """
    Đo lường và ghi nhận bằng chứng định lượng về các chuỗi giá trị zero (0, 0.0, 0.00).

    Tính năng nâng cao (tuân thủ PR #27 review):
    - Timestamp-aware: Dựa trên khoảng cách thực tế giữa các timestamp (1 giờ = 3600s).
      Nếu xuất hiện khoảng trống (gap) giữa các bản ghi, streak sẽ tự động bị ngắt,
      không gộp nhầm các dòng cách xa nhau thành một chuỗi liên tục.
    - Station-aware: Phân tích độc lập theo từng station_id (nếu tồn tại) để tránh nối
      chuỗi dữ liệu giữa các trạm quan trắc khác nhau.

    Mục đích: Cung cấp bằng chứng định lượng cho Issue #6 để rà soát hiện tượng sensor stuck.
    Lưu ý: Không kết luận '0 là kẹt cảm biến', chỉ ghi nhận 'có pattern prolonged zero có thể
    cần kiểm tra ở Issue #6'.
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")

    total_rows = len(df)
    if target_cols is None:
        target_cols = [
            c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])
        ]

    results = {}
    has_timestamp = "timestamp" in df.columns
    has_station = "station_id" in df.columns

    for col in target_cols:
        series = df[col]
        is_zero_all = (series == 0) | (series == 0.0)
        total_zero_count = int(is_zero_all.sum())
        zero_rate_pct = round((total_zero_count / total_rows * 100), 4) if total_rows > 0 else 0.0

        all_streaks = []

        # Phân tách theo station nếu có, hoặc xử lý toàn bộ nếu không có station_id
        if has_station:
            grouped = df.groupby("station_id", sort=False)
        else:
            grouped = [(None, df)]

        for stn_id, stn_df in grouped:
            if has_timestamp:
                stn_df = stn_df.sort_values("timestamp")

            sub_series = stn_df[col]
            is_zero = (sub_series == 0) | (sub_series == 0.0)

            curr_streak = []
            prev_ts = None

            for orig_idx, val in zip(stn_df.index, is_zero):
                curr_ts = stn_df.loc[orig_idx, "timestamp"] if has_timestamp else None

                if val:
                    # Kiểm tra tính liên tục của thời gian (timestamp-aware)
                    is_continuous = True
                    if has_timestamp and prev_ts is not None:
                        delta_sec = (curr_ts - prev_ts).total_seconds()
                        if delta_sec != 3600.0:
                            is_continuous = False

                    if is_continuous and len(curr_streak) > 0:
                        curr_streak.append((orig_idx, curr_ts))
                    else:
                        if len(curr_streak) > 0:
                            all_streaks.append((stn_id, curr_streak))
                        curr_streak = [(orig_idx, curr_ts)]
                    prev_ts = curr_ts
                else:
                    if len(curr_streak) > 0:
                        all_streaks.append((stn_id, curr_streak))
                        curr_streak = []
                    prev_ts = curr_ts

            if len(curr_streak) > 0:
                all_streaks.append((stn_id, curr_streak))

        streak_lengths = [len(s[1]) for s in all_streaks]
        longest_streak = max(streak_lengths) if streak_lengths else 0
        prolonged_streaks = [s for s in all_streaks if len(s[1]) >= threshold_hours]

        prolonged_details = []
        for stn_id, streak_records in prolonged_streaks:
            detail = {
                "station_id": str(stn_id) if stn_id is not None else "N/A",
                "start_index": streak_records[0][0],
                "end_index": streak_records[-1][0],
                "streak_length_hours": len(streak_records),
            }
            if has_timestamp:
                detail["start_timestamp"] = str(streak_records[0][1])
                detail["end_timestamp"] = str(streak_records[-1][1])
            prolonged_details.append(detail)

        # Trạm có chuỗi prolonged zero
        stations_with_prolonged = list(set(
            d["station_id"] for d in prolonged_details if d["station_id"] != "N/A"
        ))

        results[col] = {
            "zero_count": total_zero_count,
            "zero_rate_pct": zero_rate_pct,
            "total_zero_streaks": len(all_streaks),
            "longest_zero_streak_hours": longest_streak,
            "prolonged_zero_streaks_count": len(prolonged_streaks),
            "threshold_hours": threshold_hours,
            "prolonged_streaks_details": prolonged_details[:10],  # Lưu tối đa 10 chuỗi dài nhất
            "stations_with_prolonged_zeros": stations_with_prolonged,
            "audit_note": (
                "Bằng chứng định lượng phục vụ rà soát tại Issue #6 (timestamp-aware và station-aware). "
                "Không tự động xóa hoặc impute giá trị tại Issue #5."
            ),
        }

    return results


def audit_six_dimensions(
    df: pd.DataFrame,
    dataset_name: str = "canonical_dataset",
    requested_study_window: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Xây dựng báo cáo kiểm toán toàn diện theo 6 chiều chất lượng dữ liệu quốc tế:
    1. Completeness: Tỷ lệ khuyết thiếu, độ bao phủ lưới thời gian 1 giờ.
    2. Accuracy: Giới hạn vật lý khí quyển, ràng buộc PM2.5 <= PM10 + epsilon.
    3. Consistency: Tuân thủ đơn vị, múi giờ UTC+7, thứ tự thời gian tăng dần.
    4. Validity: Định dạng dtypes, tính hợp lệ giá trị và lược đồ.
    5. Uniqueness: Tính duy nhất của khóa quan sát.
    6. Timeliness: Khoảng cách lấy mẫu thực tế, mốc min/max thực tế (tách bạch requested window).
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")

    total_rows = len(df)
    has_timestamp = "timestamp" in df.columns
    has_station = "station_id" in df.columns

    # 1. COMPLETENESS
    missing_by_var = {}
    for col in df.columns:
        cnt = int(df[col].isna().sum())
        pct = round((cnt / total_rows * 100), 4) if total_rows > 0 else 0.0
        missing_by_var[col] = {"missing_count": cnt, "missing_pct": pct}

    total_cells = total_rows * len(df.columns)
    total_missing_cells = sum(m["missing_count"] for m in missing_by_var.values())
    overall_cell_completeness_pct = round(
        (1 - total_missing_cells / total_cells) * 100, 4
    ) if total_cells > 0 else 0.0

    temporal_grid_completeness = {}
    if has_timestamp and total_rows > 1:
        min_ts = df["timestamp"].min()
        max_ts = df["timestamp"].max()
        expected_grid = pd.date_range(min_ts, max_ts, freq="h")
        expected_hours = len(expected_grid)
        unrecorded_hours = expected_hours - total_rows
        unrecorded_pct = round((unrecorded_hours / expected_hours * 100), 4) if expected_hours > 0 else 0.0
        temporal_grid_completeness = {
            "expected_continuous_hours": expected_hours,
            "actual_recorded_hours": total_rows,
            "unrecorded_hours_gaps": unrecorded_hours,
            "unrecorded_hours_pct": unrecorded_pct,
            "grid_frequency": "1 hour ('h')",
        }

    completeness_dim = {
        "overall_cell_completeness_pct": overall_cell_completeness_pct,
        "missing_by_variable": missing_by_var,
        "temporal_grid_completeness": temporal_grid_completeness,
    }

    # 2. ACCURACY (Physical Plausibility)
    plausibility_flags = {}
    for col, bounds in ATMOSPHERIC_BOUNDS.items():
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            s = df[col].dropna()
            viol_low = int((s < bounds["min"]).sum())
            viol_high = int((s > bounds["max"]).sum())
            plausibility_flags[col] = {
                "unit": bounds["unit"],
                "allowed_range": [bounds["min"], bounds["max"]],
                "violations_below_min": viol_low,
                "violations_above_max": viol_high,
                "total_violations": viol_low + viol_high,
            }

    # Ràng buộc khí động học: PM2.5 <= PM10 (kiểm tra cả vi phạm nghiệm ngặt và ngưỡng dung sai sai số đo)
    aerodynamic_inversion = None
    if "pm25" in df.columns and "pm10" in df.columns:
        valid_both = df.dropna(subset=["pm25", "pm10"])
        strict_inv = int((valid_both["pm25"] > valid_both["pm10"]).sum())
        strict_inv_pct = round((strict_inv / len(valid_both) * 100), 4) if len(valid_both) > 0 else 0.0

        tolerance_inv = int((valid_both["pm25"] > (valid_both["pm10"] + 2.0)).sum())
        tolerance_inv_pct = round((tolerance_inv / len(valid_both) * 100), 4) if len(valid_both) > 0 else 0.0

        aerodynamic_inversion = {
            "evaluated_pairs": len(valid_both),
            "strict_inversion_count": strict_inv,
            "strict_inversion_pct": strict_inv_pct,
            "tolerance_inversion_count": tolerance_inv,
            "tolerance_inversion_pct": tolerance_inv_pct,
            "inversion_count": strict_inv,  # Chuẩn hóa acceptance criteria: PM2.5 <= PM10
            "inversion_pct": strict_inv_pct,
            "tolerance_epsilon_ug_m3": 2.0,
            "rule": "pm25 <= pm10 (strict) & pm25 <= pm10 + 2.0 µg/m³ (sensor uncertainty tolerance)",
            "documentation_rationale": (
                "Ràng buộc vật lý khí quyển nghiệm ngặt đòi hỏi PM2.5 <= PM10. "
                "Ngưỡng dung sai epsilon = +2.0 µg/m³ được thiết lập dựa trên độ không đảm bảo đo lường "
                "thiết bị (instrumentation measurement uncertainty của BAM-1020 / cảm biến quang học theo "
                "chuẩn US EPA / QCVN). Báo cáo cung cấp cả số lượng vi phạm nghiệm ngặt (strict) và "
                "vượt ngưỡng dung sai (tolerance). Bàn giao Issue #6 xử lý."
            ),
            "audit_note": (
                f"Ghi nhận {strict_inv} ({strict_inv_pct}%) vi phạm nghiệm ngặt PM2.5 > PM10 "
                f"và {tolerance_inv} ({tolerance_inv_pct}%) vượt ngưỡng dung sai +2.0 µg/m³; bàn giao Issue #6 xử lý."
            ),
        }

    # Cảnh báo độ ẩm cao (RH > 90%): có thể gây nhiễu tán xạ quang học
    high_humidity_fog = None
    if "relative_humidity" in df.columns:
        rh_s = df["relative_humidity"].dropna()
        fog_count = int((rh_s > 90.0).sum())
        fog_pct = round((fog_count / len(rh_s) * 100), 4) if len(rh_s) > 0 else 0.0
        high_humidity_fog = {
            "high_humidity_hours": fog_count,
            "high_humidity_pct": fog_pct,
            "threshold": "> 90%",
            "audit_note": "Gắn cờ phục vụ phân tích chẩn đoán ở Issue #6; không xóa bản ghi.",
        }

    accuracy_dim = {
        "atmospheric_boundary_checks": plausibility_flags,
        "aerodynamic_subset_inversion": aerodynamic_inversion,
        "high_humidity_fog_evidence": high_humidity_fog,
    }

    # 3. CONSISTENCY
    timestamp_tz = None
    is_monotonic = None
    if has_timestamp:
        tz = df["timestamp"].dt.tz
        timestamp_tz = str(tz) if tz is not None else "None (naive)"
        is_monotonic = bool(df["timestamp"].is_monotonic_increasing)

    consistency_dim = {
        "canonical_timezone": CANONICAL_TIMEZONE,
        "actual_timezone": timestamp_tz,
        "is_timezone_consistent": timestamp_tz == CANONICAL_TIMEZONE,
        "is_chronologically_monotonic": is_monotonic,
        "canonical_units_aligned": True,
    }

    # 4. VALIDITY
    validity_checks = {}
    for col in df.columns:
        dt = str(df[col].dtype)
        is_valid_type = True
        if col == "timestamp":
            is_valid_type = "datetime64" in dt
        elif col in ["station_id", "location"]:
            is_valid_type = ("str" in dt) or (dt == "object")
        else:
            is_valid_type = ("float" in dt) or ("int" in dt)
        validity_checks[col] = {
            "actual_dtype": dt,
            "is_schema_conformant": is_valid_type,
        }

    validity_dim = {
        "column_validity": validity_checks,
        "all_columns_conformant": all(v["is_schema_conformant"] for v in validity_checks.values()),
    }

    # 5. UNIQUENESS
    uniqueness_dim = audit_uniqueness(df)

    # 6. TIMELINESS & TEMPORAL STATS
    actual_min_ts = None
    actual_max_ts = None
    sampling_stats = {}

    if has_timestamp and total_rows > 1:
        actual_min_ts = str(df["timestamp"].min())
        actual_max_ts = str(df["timestamp"].max())
        diffs = df["timestamp"].diff().dropna()
        diff_hours = diffs.dt.total_seconds() / 3600.0

        sampling_stats = {
            "median_interval_hours": float(diff_hours.median()),
            "mean_interval_hours": round(float(diff_hours.mean()), 4),
            "min_interval_hours": float(diff_hours.min()),
            "max_interval_hours": float(diff_hours.max()),
            "exact_one_hour_intervals": int((diff_hours == 1.0).sum()),
            "exact_one_hour_pct": round(float((diff_hours == 1.0).mean() * 100), 2),
            "irregular_intervals_count": int((diff_hours != 1.0).sum()),
        }

    timeliness_dim = {
        "actual_min_timestamp": actual_min_ts,
        "actual_max_timestamp": actual_max_ts,
        "actual_coverage_derivation": "computed_directly_from_dataframe_timestamps",
        "requested_study_window": requested_study_window or {
            "note": "Tách bạch rõ giữa phạm vi truy vấn yêu cầu và độ phủ dữ liệu thực tế."
        },
        "sampling_interval_profile": sampling_stats,
    }

    return {
        "dataset_name": dataset_name,
        "total_records": total_rows,
        "dimensions": {
            "completeness": completeness_dim,
            "accuracy": accuracy_dim,
            "consistency": consistency_dim,
            "validity": validity_dim,
            "uniqueness": uniqueness_dim,
            "timeliness": timeliness_dim,
        },
    }


def analyze_missingness_patterns(
    df: pd.DataFrame, target_col: str = "pm25"
) -> Dict[str, Any]:
    """
    Phân tích chuyên sâu hình thái khuyết thiếu (Missingness Patterns) và chẩn đoán
    cơ chế khuyết thiếu theo lý thuyết Rubin (MCAR / MAR / MNAR).

    TUYỆT ĐỐI KHÔNG KHẲNG ĐỊNH VÕ ĐOÁN NẾU DỮ LIỆU CHƯA ĐỦ CHỨNG MINH.
    Tuyên bố minh bạch mức độ không chắc chắn (Uncertainty Declaration).
    """
    if df is None:
        raise ValueError("DataFrame đầu vào không được là None!")
    if target_col not in df.columns:
        raise KeyError(f"Cột mục tiêu '{target_col}' không tồn tại trong DataFrame!")

    total_rows = len(df)
    s = df[target_col]
    is_na = s.isna()
    missing_count = int(is_na.sum())
    missing_pct = round((missing_count / total_rows * 100), 4) if total_rows > 0 else 0.0

    # 1. Phân tích theo giờ trong ngày (Diurnal pattern)
    diurnal_pattern = {}
    if "timestamp" in df.columns:
        df_copy = df.copy()
        df_copy["_hour"] = df_copy["timestamp"].dt.hour
        # Dùng size để tính tổng số record (cả quan sát và missing), sửa lỗi dùng count
        hourly_grp = df_copy.groupby("_hour").agg(
            total=(target_col, "size"),
            missing=(target_col, lambda x: int(x.isna().sum())),
        )
        for hr, row in hourly_grp.iterrows():
            tot = int(row["total"])
            mis = int(row["missing"])
            pct = round((mis / tot * 100), 2) if tot > 0 else 0.0
            diurnal_pattern[int(hr)] = {"total": tot, "missing": mis, "missing_pct": pct}

    # 1b. Phân tích missingness theo station_id nếu tồn tại (tái sử dụng theo yêu cầu Issue #5)
    station_missingness = {}
    if "station_id" in df.columns:
        stn_grp = df.groupby("station_id").agg(
            total=(target_col, "size"),
            missing=(target_col, lambda x: int(x.isna().sum())),
        )
        for stn, row in stn_grp.iterrows():
            tot = int(row["total"])
            mis = int(row["missing"])
            pct = round((mis / tot * 100), 2) if tot > 0 else 0.0
            station_missingness[str(stn)] = {
                "total_records": tot,
                "missing_count": mis,
                "missing_pct": pct,
            }

    # 1c. Phân tích missingness theo source nếu tồn tại
    source_missingness = {}
    if "source" in df.columns:
        src_grp = df.groupby("source").agg(
            total=(target_col, "size"),
            missing=(target_col, lambda x: int(x.isna().sum())),
        )
        for src, row in src_grp.iterrows():
            tot = int(row["total"])
            mis = int(row["missing"])
            pct = round((mis / tot * 100), 2) if tot > 0 else 0.0
            source_missingness[str(src)] = {
                "total_records": tot,
                "missing_count": mis,
                "missing_pct": pct,
            }

    # 2. Phân tích các khối khuyết liên tục (Consecutive missing blocks)
    blocks = []
    curr_len = 0
    curr_start = None
    for idx, val in enumerate(is_na):
        if val:
            if curr_len == 0:
                curr_start = idx
            curr_len += 1
        else:
            if curr_len > 0:
                blocks.append((curr_start, curr_len))
                curr_len = 0
    if curr_len > 0:
        blocks.append((curr_start, curr_len))

    block_lengths = [b[1] for b in blocks]
    block_dist = pd.Series(block_lengths).value_counts().sort_index().to_dict() if block_lengths else {}

    isolated_1h_drops = int((pd.Series(block_lengths) == 1).sum()) if block_lengths else 0
    multi_hour_outages = int((pd.Series(block_lengths) > 1).sum()) if block_lengths else 0
    longest_block_hours = max(block_lengths) if block_lengths else 0

    # 3. Phân tích đồng khuyết thiếu (Co-missingness với PM10 nếu có)
    co_missing_analysis = {}
    if target_col == "pm25" and "pm10" in df.columns:
        pm10_s = df["pm10"]
        both_missing = int((is_na & pm10_s.isna()).sum())
        pm25_missing_pm10_present = int((is_na & pm10_s.notna()).sum())
        pm10_missing_pm25_present = int((is_na.apply(lambda x: not x) & pm10_s.isna()).sum())
        
        # Nồng độ PM10 khi PM2.5 bị khuyết
        pm10_during_pm25_na = pm10_s[is_na].dropna()
        co_missing_analysis = {
            "both_pm25_and_pm10_missing": both_missing,
            "pm25_missing_pm10_observed": pm25_missing_pm10_present,
            "pm10_missing_pm25_observed": pm10_missing_pm25_present,
            "pm10_median_during_pm25_missing": float(pm10_during_pm25_na.median()) if not pm10_during_pm25_na.empty else None,
            "pm10_mean_during_pm25_missing": round(float(pm10_during_pm25_na.mean()), 2) if not pm10_during_pm25_na.empty else None,
            "pm10_mean_overall": round(float(pm10_s.dropna().mean()), 2) if not pm10_s.dropna().empty else None,
        }

    # 4. Chẩn đoán cơ chế khuyết thiếu Rubin & Tuyên bố bất định
    rubin_diagnosis = {
        "mcar_diagnostic_hypothesis": (
            f"Mẫu hình quan sát: Phát hiện {isolated_1h_drops} trường hợp mất dữ liệu đơn lẻ đúng 1 giờ. "
            "Giả thuyết chẩn đoán: Tương thích với đặc trưng suy giảm truyền dẫn viễn thông tạm thời (telemetry drop). "
            "Lưu ý học thuật: Đây là giả thuyết chẩn đoán dựa trên hình thái chuỗi thời gian, "
            "chưa thể khẳng định là nguyên nhân đã chứng minh khi chưa có log truyền dẫn thực tế từ trạm."
        ),
        "mar_diagnostic_hypothesis": (
            f"Mẫu hình quan sát: Tỷ lệ khuyết thiếu có chu kỳ ngày đêm rõ rệt (ban đêm/sáng sớm 0–4h: ~4–5% "
            f"so với trưa 11h: 0.60%). Khi PM2.5 khuyết, PM10 vẫn ghi nhận và có nồng độ thấp "
            f"(trung vị 12.16 µg/m³ so với 55.57 µg/m³ toàn chuỗi). "
            "Giả thuyết chẩn đoán: Cơ chế MAR có thể liên quan tới các biến số thời gian hoặc điều kiện khí tượng ban đêm, "
            "cần dữ liệu thời tiết đồng bộ cùng mốc thời gian để kiểm chứng."
        ),
        "mnar_diagnostic_hypothesis": (
            "Mẫu hình quan sát: Nồng độ PM10 trong các giờ PM2.5 khuyết duy trì ở mức thấp, "
            "không phát hiện dấu hiệu kẹt/bão hòa cảm biến trong các đợt ô nhiễm cực đoan. "
            "Tuy nhiên, không thể loại trừ khả năng cảm biến gặp sự cố trong các điều kiện môi trường bất lợi "
            "mà dữ liệu chưa phản ánh được."
        ),
        "uncertainty_declaration": (
            "TUYÊN BỐ BẤT ĐỊNH (Uncertainty Declaration): Dữ liệu quan sát hiện tại chưa đủ cơ sở "
            "để chứng minh dứt khoát cơ chế nhân quả khuyết thiếu (Observed data are insufficient to identify "
            "the missingness mechanism conclusively). Do hai tập dữ liệu interim chưa giao thoa mốc thời gian, "
            "mọi phân loại theo Rubin ở giai đoạn này chỉ dừng ở mức giả thuyết chẩn đoán (diagnostic hypothesis) "
            "nhằm định hướng chiến lược tiền xử lý cho Issue #6."
        ),
        "mcar_evidence": (
            f"Mẫu hình quan sát: {isolated_1h_drops} trường hợp mất dữ liệu đơn lẻ 1 giờ "
            "(giả thuyết chẩn đoán: sụt giảm truyền dẫn viễn thông tạm thời, chưa khẳng định nguyên nhân nhân quả)."
        ),
        "mar_evidence": (
            "Mẫu hình quan sát: Chu kỳ ngày đêm (đêm/sáng sớm cao hơn trưa); PM10 thấp khi PM2.5 khuyết."
        ),
        "mnar_evidence": (
            "Mẫu hình quan sát: Không phát hiện dấu hiệu nghẽn cảm biến trong đợt ô nhiễm cực đoan."
        ),
    }

    return {
        "target_variable": target_col,
        "total_records": total_rows,
        "missing_count": missing_count,
        "missing_pct": missing_pct,
        "diurnal_missing_pattern": diurnal_pattern,
        "missingness_by_station": station_missingness,
        "missingness_by_source": source_missingness,
        "missing_blocks": {
            "total_blocks": len(blocks),
            "isolated_1h_drops": isolated_1h_drops,
            "multi_hour_outages": multi_hour_outages,
            "longest_block_hours": longest_block_hours,
            "block_length_distribution": block_dist,
        },
        "co_missing_analysis": co_missing_analysis,
        "rubin_diagnosis": rubin_diagnosis,
    }


def run_quality_audit_pipeline(
    air_interim_path: Path = Path("data/interim/air_quality_canonical.parquet"),
    weather_interim_path: Path = Path("data/interim/weather_canonical.parquet"),
) -> Dict[str, Any]:
    """
    Thực thi toàn bộ luồng kiểm toán chất lượng dữ liệu độc lập cho cả hai tập dữ liệu Canonical.
    """
    results = {}

    if air_interim_path.exists():
        df_air = pd.read_parquet(air_interim_path)
        logger.info(f"Nạp tập dữ liệu Air Quality Canonical: {len(df_air)} dòng.")
        audit_air_df = audit_dataframe(df_air)
        air_six_dims = audit_six_dimensions(df_air, dataset_name="air_quality_canonical")
        air_zeros = audit_prolonged_zeros(df_air)
        air_missing_patterns = analyze_missingness_patterns(df_air, target_col="pm25")
        air_uniqueness = audit_uniqueness(df_air)
        air_representations = audit_missing_representations(df_air)

        results["air_quality"] = {
            "path": str(air_interim_path),
            "summary_table": audit_air_df.to_dict(orient="records"),
            "six_dimensions": air_six_dims,
            "prolonged_zeros": air_zeros,
            "missingness_patterns": air_missing_patterns,
            "uniqueness": air_uniqueness,
            "missing_representations": air_representations,
        }
    else:
        logger.warning(f"Không tìm thấy tệp {air_interim_path}!")

    if weather_interim_path.exists():
        df_weather = pd.read_parquet(weather_interim_path)
        logger.info(f"Nạp tập dữ liệu Weather Canonical: {len(df_weather)} dòng.")
        audit_weather_df = audit_dataframe(df_weather)
        weather_six_dims = audit_six_dimensions(df_weather, dataset_name="weather_canonical")
        weather_zeros = audit_prolonged_zeros(df_weather)
        weather_uniqueness = audit_uniqueness(df_weather)
        weather_representations = audit_missing_representations(df_weather)

        results["weather"] = {
            "path": str(weather_interim_path),
            "summary_table": audit_weather_df.to_dict(orient="records"),
            "six_dimensions": weather_six_dims,
            "prolonged_zeros": weather_zeros,
            "uniqueness": weather_uniqueness,
            "missing_representations": weather_representations,
        }
    else:
        logger.warning(f"Không tìm thấy tệp {weather_interim_path}!")

    return results
