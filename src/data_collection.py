"""
Module thu thập và chuẩn hóa dữ liệu chất lượng không khí & khí tượng Hà Nội.

Tuân thủ:
- Milestone 1 / GitHub Issue #3, #4 & #19.
- Quyết định rà soát nguồn dữ liệu (Đính chính: Loại bỏ OpenAQ 2178, xác thực trạm Hà Nội 4946811 & AirNow DOS).
- Canonical Data Schema trong docs/data_dictionary.md.
- Nguyên tắc an toàn dữ liệu chuỗi thời gian trong .agents/rules/data.md.
- Nguyên tắc kỹ thuật & không over-engineering trong .agents/rules/project.md.
"""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Bounding box Hà Nội theo docs/data_dictionary.md & metadata.json
HANOI_BBOX = {
    "lat_min": 20.50,
    "lat_max": 21.60,
    "lon_min": 105.30,
    "lon_max": 106.10,
}

CANONICAL_TIMEZONE = "Asia/Ho_Chi_Minh"
CANONICAL_UTC_OFFSET_HOURS = 7  # Việt Nam không quan sát giờ mùa hè (no DST) -> UTC+7 quanh năm.

# Danh mục cột chuẩn hóa cho dữ liệu khí tượng bề mặt (Issue #4 / docs/data_dictionary.md)
WEATHER_CANONICAL_COLUMNS = [
    "timestamp",
    "temperature",
    "relative_humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "surface_pressure",
]

# Giới hạn vật lý khí tượng bề mặt Hà Nội theo docs/data_dictionary.md & .agents/skills/data-quality/SKILL.md
WEATHER_PHYSICAL_BOUNDS = {
    "temperature": {"min": 0.0, "max": 50.0, "unit": "°C"},
    "relative_humidity": {"min": 0.0, "max": 100.0, "unit": "%"},
    "wind_speed": {"min": 0.0, "max": 60.0, "unit": "m/s"},
    "wind_direction": {"min": 0.0, "max": 360.0, "unit": "degrees"},
    "precipitation": {"min": 0.0, "max": 300.0, "unit": "mm"},
    "surface_pressure": {"min": 950.0, "max": 1050.0, "unit": "hPa"},
}

# Ngưỡng tỷ lệ khuyết thiếu khí tượng mà pipeline thực thi phải đạt.
# Issue #19 (docs/source_profiling_decision.md §14.2) yêu cầu kiểm định dữ liệu 6 biến
# khí tượng không có giá trị khuyết thiếu trước khi lưu. Đây là ngưỡng tường minh của
# pipeline; validate_weather_canonical() mặc định chỉ BÁO CÁO, không ép ngưỡng.
WEATHER_PIPELINE_MAX_MISSING_PCT = 0.0

# Mã lỗi ngụy trang (disguised missing codes) do nhà cung cấp dùng để mã hóa giá trị khuyết thiếu.
# Giá trị đo hợp lệ bằng 0.0 KHÔNG nằm trong danh sách này và luôn được giữ nguyên.
WEATHER_SENTINEL_CODES = (-999.0, -9999.0)

# Tọa độ truy vấn mặc định: tâm lõi đô thị Hà Nội (Issue #19 / docs/source_profiling_decision.md §14.2).
# API Open-Meteo tự ánh xạ sang điểm lưới ERA5 gần nhất (COORDS_WEATHER_ERA5).
WEATHER_QUERY_COORDS = (21.0285, 105.8542)

# Định danh trạm chuẩn hóa (Canonical Station Identifiers)
DISQUALIFIED_OPENAQ_LOCATION_ID = 2178  # Del Norte, Albuquerque, NM, USA -> LOẠI BỎ HOÀN TOÀN
HANOI_OPENAQ_LOCATION_ID = 4946811      # Trạm 556 Nguyễn Văn Cừ, Long Biên, Hà Nội
STATION_OPENAQ_HANOI = "VN001_HANOI_556_NGUYEN_VAN_CU"
LOCATION_OPENAQ_HANOI = "556 Nguyễn Văn Cừ"
COORDS_OPENAQ_HANOI = (21.0491, 105.8831)

STATION_AIRNOW_HANOI = "VN002_HANOI_US_EMBASSY"
LOCATION_AIRNOW_HANOI = "US Diplomatic Post: Hanoi"
COORDS_AIRNOW_HANOI = (21.0215, 105.8184)

STATION_WEATHER_ERA5 = "ERA5_HANOI_GRID_2105_10590"
LOCATION_WEATHER_ERA5 = "Hanoi ERA5 Grid (21.0545N, 105.8985E)"
COORDS_WEATHER_ERA5 = (21.05448, 105.89848)


def compute_file_sha256(filepath: Path) -> str:
    """Tính toán mã băm SHA-256 của tệp để bảo toàn tính toàn vẹn và provenance."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def clean_air_quality_values(val: Any) -> float:
    """
    Làm sạch giá trị đo ô nhiễm không khí theo đúng các quy tắc chất lượng dữ liệu:
    - -999, -9999 -> NaN (bóc trần mã lỗi ngụy trang).
    - < 0 -> NaN (giá trị âm phi vật lý đối với nồng độ hạt).
    - 0.0 -> giữ nguyên 0.0 (giá trị đo hợp lệ, tuyệt đối không biến thành NaN).
    - Tuyệt đối không fillna(0) để thay thế missing data.
    """
    if pd.isna(val):
        return np.nan
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return np.nan

    if fval in (-999.0, -9999.0, -999, -9999):
        return np.nan
    if fval < 0.0:
        return np.nan
    return fval


def clean_weather_values(val: Any, var_name: Optional[str] = None) -> float:
    """
    Làm sạch giá trị đo khí tượng theo đúng các quy tắc chất lượng dữ liệu:
    - Bóc trần mã lỗi ngụy trang (-999, -9999, "NaN", "None", "") -> NaN.
    - Bảo toàn giá trị 0.0 hợp lệ (lượng mưa 0.0 mm, tốc độ gió 0.0 m/s là hiện tượng thực tế, không biến thành NaN).
    - Tuyệt đối không fillna(0) để thay thế missing data (no silent zero imputation).
    - Phát hiện và chuyển đổi các giá trị vi phạm quy luật vật lý hiển nhiên thành NaN:
      * Tốc độ gió âm (< 0 m/s) -> NaN
      * Lượng mưa âm (< 0 mm) -> NaN
      * Độ ẩm ngoài dải [0, 100]% -> NaN
      * Hướng gió ngoài [0, 360] -> nếu âm gán NaN; nếu > 360 chuẩn hóa modulo 360.
      * Nhiệt độ ngoài [0, 50]°C hoặc áp suất ngoài [950, 1050] hPa -> NaN
    """
    if pd.isna(val):
        return np.nan
    try:
        fval = float(val)
    except (ValueError, TypeError):
        return np.nan

    # Bóc trần mã lỗi ngụy trang
    if fval in (-999.0, -9999.0, -999, -9999):
        return np.nan

    # Kiểm tra giới hạn vật lý theo từng biến khí tượng
    if var_name:
        if var_name in ("wind_speed", "precipitation") and fval < 0.0:
            return np.nan
        if var_name == "relative_humidity" and (fval < 0.0 or fval > 100.0):
            return np.nan
        if var_name == "wind_direction":
            if fval < 0.0:
                return np.nan
            if fval > 360.0:
                fval = fval % 360.0
        if var_name == "temperature" and (fval < 0.0 or fval > 50.0):
            return np.nan
        if var_name == "surface_pressure" and (fval < 950.0 or fval > 1050.0):
            return np.nan

    return fval


def is_sentinel_code(val: Any) -> bool:
    """
    Kiểm tra một giá trị thô có phải mã lỗi ngụy trang (-999 / -9999) hay không.
    Giá trị 0.0 hợp lệ KHÔNG phải sentinel.
    """
    if pd.isna(val):
        return False
    try:
        return float(val) in WEATHER_SENTINEL_CODES
    except (ValueError, TypeError):
        return False


def summarize_weather_cleaning(
    raw_values: Dict[str, List[Any]], cleaned_values: Dict[str, List[float]]
) -> Dict[str, Dict[str, int]]:
    """
    Thống kê nguyên nhân các giá trị thô bị chuyển thành NaN ở LỚP LÀM SẠCH (cleaning),
    phân biệt rõ ba trường hợp:
      - `disguised_missing`: mã lỗi ngụy trang -999 / -9999.
      - `out_of_bounds`     : giá trị đọc được nhưng vi phạm giới hạn vật lý đã công bố.
      - `unparseable`       : không chuyển được sang số (None, chuỗi rỗng, ...).

    Mục đích: lớp cleaning KHÔNG được "giấu" vi phạm giới hạn vật lý.
    validate_weather_canonical() dựa vào bảng thống kê này để báo cáo trung thực
    số lượng giá trị đã bị loại bỏ, thay vì báo `bounds_violation_count = 0` một cách giả định.
    """
    report: Dict[str, Dict[str, int]] = {}
    for var_name, raw_list in raw_values.items():
        cleaned_list = cleaned_values.get(var_name, [])
        stats = {"disguised_missing": 0, "out_of_bounds": 0, "unparseable": 0}
        for raw_val, clean_val in zip(raw_list, cleaned_list):
            if clean_val is None or not np.isnan(clean_val):
                continue  # giá trị được giữ lại (bao gồm cả 0.0 hợp lệ)
            if pd.isna(raw_val):
                continue  # đã là NaN ngay từ nguồn, không phải cleaning loại bỏ
            if is_sentinel_code(raw_val):
                stats["disguised_missing"] += 1
                continue
            try:
                float(raw_val)
            except (ValueError, TypeError):
                stats["unparseable"] += 1
                continue
            stats["out_of_bounds"] += 1
        report[var_name] = stats
    return report


def filter_hanoi_bounds(
    df: pd.DataFrame,
    lat_col: Optional[str] = None,
    lon_col: Optional[str] = None,
    bbox: Optional[Dict[str, float]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Lọc không gian từng bản ghi theo Bounding Box Hà Nội [20.50, 21.60]N, [105.30, 106.10]E.
    
    Yêu cầu kỹ thuật:
    1. Kiểm tra từng record.
    2. Loại bỏ record nằm ngoài bounding box.
    3. Không sửa raw coordinates.
    4. Trả về DataFrame đã lọc và thống kê: raw_records, filtered_out_records, retained_records.
    """
    if bbox is None:
        bbox = HANOI_BBOX

    if df.empty:
        return df.copy(), {
            "raw_records": 0,
            "filtered_out_records": 0,
            "retained_records": 0,
            "bounding_box": bbox,
            "all_within_bounds": True,
            "retained_pct": 0.0,
        }

    # Tự động nhận diện tên cột tọa độ nếu không chỉ định
    if lat_col is None:
        for c in ["lat", "latitude", "Lat", "Latitude"]:
            if c in df.columns:
                lat_col = c
                break
    if lon_col is None:
        for c in ["lon", "longitude", "Lon", "Longitude"]:
            if c in df.columns:
                lon_col = c
                break

    if lat_col is None or lon_col is None or lat_col not in df.columns or lon_col not in df.columns:
        raise ValueError(f"Không tìm thấy cột tọa độ trong DataFrame! Các cột hiện có: {list(df.columns)}")

    raw_count = len(df)
    is_valid_lat = (df[lat_col] >= bbox["lat_min"]) & (df[lat_col] <= bbox["lat_max"])
    is_valid_lon = (df[lon_col] >= bbox["lon_min"]) & (df[lon_col] <= bbox["lon_max"])
    mask_in_bounds = is_valid_lat & is_valid_lon & df[lat_col].notna() & df[lon_col].notna()

    df_filtered = df[mask_in_bounds].copy()
    retained_count = len(df_filtered)
    filtered_out_count = raw_count - retained_count

    stats = {
        "raw_records": raw_count,
        "filtered_out_records": filtered_out_count,
        "retained_records": retained_count,
        "bounding_box": bbox,
        "all_within_bounds": bool(filtered_out_count == 0),
        "retained_pct": round(float(retained_count / raw_count * 100), 2) if raw_count > 0 else 0.0,
    }

    if filtered_out_count > 0:
        logger.warning(
            f"Geographic Filtering: Đã loại bỏ {filtered_out_count}/{raw_count} bản ghi ngoài Bounding Box Hà Nội!"
        )
    else:
        logger.info(
            f"Geographic Filtering: 100% bản ghi ({retained_count}/{raw_count}) nằm trong Bounding Box Hà Nội."
        )

    return df_filtered, stats


def assert_canonical_within_hanoi(
    df: pd.DataFrame,
    station_coords: Optional[Dict[str, Tuple[float, float]]] = None,
) -> None:
    """
    Assertion bảo đảm 100% canonical records nằm trong Hanoi bounding box.
    Nếu còn record ngoài bbox thì pipeline fail rõ ràng (AssertionError/ValueError).
    """
    known_coords = {
        STATION_OPENAQ_HANOI: COORDS_OPENAQ_HANOI,
        STATION_AIRNOW_HANOI: COORDS_AIRNOW_HANOI,
        STATION_WEATHER_ERA5: COORDS_WEATHER_ERA5,
    }
    if station_coords:
        known_coords.update(station_coords)

    # 1. Kiểm tra nếu có cột tọa độ trực tiếp
    for lat_c, lon_c in [("latitude", "longitude"), ("lat", "lon")]:
        if lat_c in df.columns and lon_c in df.columns:
            in_lat = (df[lat_c] >= HANOI_BBOX["lat_min"]) & (df[lat_c] <= HANOI_BBOX["lat_max"])
            in_lon = (df[lon_c] >= HANOI_BBOX["lon_min"]) & (df[lon_c] <= HANOI_BBOX["lon_max"])
            in_box = in_lat & in_lon
            if not in_box.all():
                out_cnt = (~in_box).sum()
                raise AssertionError(f"Phát hiện {out_cnt} bản ghi canonical nằm ngoài Bounding Box Hà Nội!")

    # 2. Kiểm tra theo trạm quan trắc (station_id)
    if "station_id" in df.columns:
        for sid in df["station_id"].unique():
            if sid not in known_coords:
                raise ValueError(f"Mã trạm không xác định trong canonical dataset: {sid}. Không thể thẩm định địa lý!")
            lat, lon = known_coords[sid]
            in_lat = HANOI_BBOX["lat_min"] <= lat <= HANOI_BBOX["lat_max"]
            in_lon = HANOI_BBOX["lon_min"] <= lon <= HANOI_BBOX["lon_max"]
            if not (in_lat and in_lon):
                raise AssertionError(f"Trạm canonical {sid} tại ({lat}, {lon}) nằm ngoài Bounding Box Hà Nội!")


def validate_canonical_uniqueness(
    df: pd.DataFrame, key_cols: List[str] = ["station_id", "timestamp"]
) -> None:
    """
    Kiểm tra tính duy nhất của khóa quan trắc (station_id, timestamp).
    Fail-fast: Ném lỗi ValueError nếu phát hiện trùng lặp khóa.
    """
    duplicates_mask = df.duplicated(subset=key_cols, keep=False)
    num_dups = duplicates_mask.sum()
    if num_dups > 0:
        dup_sample = df[duplicates_mask].head(6)
        raise ValueError(
            f"Data Quality Violation: Phát hiện {num_dups} bản ghi trùng lặp khóa quan trắc {key_cols}!\n"
            f"Mẫu bản ghi vi phạm:\n{dup_sample}"
        )


def validate_weather_canonical(
    df: pd.DataFrame,
    bounds: Optional[Dict[str, Dict[str, Any]]] = None,
    check_continuity: bool = True,
    max_missing_pct: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Kiểm định chất lượng dữ liệu khí tượng chuẩn hóa theo Acceptance Criteria của Issue #4.
    Hàm này CHỈ ĐỌC (read-only): không gán, không điền, không sắp xếp lại dữ liệu đầu vào.

    Phân biệt rõ ba mức kết quả:
      1. VALIDATION FAILURE (ném ValueError/TypeError):
         - thiếu cột canonical hoặc sai kiểu dữ liệu;
         - `timestamp` không phải datetime tz-aware, hoặc sai múi giờ
           (bắt buộc đúng `Asia/Ho_Chi_Minh` theo convention dự án);
         - `timestamp` trùng lặp hoặc không tăng đơn điệu;
         - giá trị vượt giới hạn vật lý;
         - tỷ lệ khuyết thiếu vượt ngưỡng `max_missing_pct`.
      2. VALIDATION WARNING (ghi cảnh báo + đánh dấu trong report, KHÔNG ném lỗi):
         - chuỗi giờ bị gián đoạn. Khi đó `is_valid` = False để báo cáo trung thực.
      3. CLEANING (KHÔNG thuộc hàm này): bóc trần mã lỗi ngụy trang và loại giá trị
         vi phạm giới hạn vật lý. Hoạt động này được đếm minh bạch qua
         `summarize_weather_cleaning()` và gắn vào `df.attrs["weather_cleaning"]`.
    """
    if bounds is None:
        bounds = WEATHER_PHYSICAL_BOUNDS

    # 1. Kiểm tra sự hiện diện của các cột bắt buộc
    missing_cols = [c for c in WEATHER_CANONICAL_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Canonical Weather DataFrame thiếu cột bắt buộc: {missing_cols}")

    # Kiểm tra timezone: bắt buộc datetime64 tz-aware với múi giờ canonical
    # Asia/Ho_Chi_Minh (UTC+7). Chấp nhận cả named zone lẫn fixed offset +07:00
    # vì cả hai biểu diễn cùng một múi giờ; nhưng tz-naive hoặc sai offset là vi phạm.
    ts_dtype = df["timestamp"].dtype
    if not isinstance(ts_dtype, pd.DatetimeTZDtype):
        raise ValueError(
            "Cột 'timestamp' trong Weather Canonical phải có kiểu datetime64 tz-aware "
            f"(Asia/Ho_Chi_Minh), hiện tại là {ts_dtype}!"
        )
    sample_offset = df["timestamp"].iloc[0].utcoffset() if not df.empty else None
    expected_offset = timedelta(hours=CANONICAL_UTC_OFFSET_HOURS)
    if sample_offset is not None and sample_offset != expected_offset:
        raise ValueError(
            f"Cột 'timestamp' phải dùng múi giờ {CANONICAL_TIMEZONE} (UTC+7) theo convention "
            f"dự án, hiện tại là {ts_dtype.tz} (offset {sample_offset})!"
        )

    # Kiểm tra kiểu dữ liệu float64 cho 6 biến khí tượng
    for col in WEATHER_CANONICAL_COLUMNS[1:]:
        if not np.issubdtype(df[col].dtype, np.floating):
            raise TypeError(f"Cột khí tượng '{col}' phải có kiểu float64, hiện tại là {df[col].dtype}!")

    # 2. Kiểm tra tính duy nhất của khóa quan trắc
    validate_canonical_uniqueness(df, key_cols=["timestamp"])

    # 3. Kiểm tra tính tăng đơn điệu và liên tục theo giờ
    if not df["timestamp"].is_monotonic_increasing:
        raise ValueError("Chuỗi thời gian khí tượng không được sắp xếp tăng đơn điệu!")

    warnings: List[str] = []
    is_continuous = True
    gap_count = 0
    if check_continuity and len(df) > 1:
        step_diffs = df["timestamp"].diff().dropna()
        gap_mask = step_diffs != np.timedelta64(1, "h")
        gap_count = int(gap_mask.sum())
        if gap_count > 0:
            is_continuous = False
            message = f"Phát hiện {gap_count} khoảng gián đoạn thời gian trong chuỗi khí tượng!"
            warnings.append(message)
            logger.warning(message)

    # 4. Kiểm tra giới hạn vật lý
    bounds_violations = {}
    var_stats = {}
    for col, b_info in bounds.items():
        if col in df.columns:
            series = df[col].dropna()
            b_min = b_info["min"]
            b_max = b_info["max"]
            v_low = int((series < b_min).sum())
            v_high = int((series > b_max).sum())
            if v_low > 0 or v_high > 0:
                bounds_violations[col] = {
                    "below_min": v_low,
                    "above_max": v_high,
                    "bounds": [b_min, b_max],
                }
            var_stats[col] = {
                "count": len(series),
                "missing": int(df[col].isna().sum()),
                "missing_pct": round(float(df[col].isna().mean() * 100), 2),
                "min": float(series.min()) if not series.empty else None,
                "max": float(series.max()) if not series.empty else None,
                "mean": round(float(series.mean()), 2) if not series.empty else None,
                "unit": b_info.get("unit", ""),
            }

    if bounds_violations:
        raise ValueError(
            f"Phát hiện vi phạm giới hạn vật lý trong dữ liệu khí tượng:\n{bounds_violations}"
        )

    # 5. Báo cáo minh bạch hoạt động của lớp cleaning (không phải validation failure)
    cleaning_stats = df.attrs.get("weather_cleaning", {}) or {}
    cleaning_totals = {
        key: int(sum(int(v.get(key, 0)) for v in cleaning_stats.values()))
        for key in ("disguised_missing", "out_of_bounds", "unparseable")
    }
    if cleaning_totals["out_of_bounds"] > 0:
        message = (
            f"Lớp cleaning đã loại bỏ {cleaning_totals['out_of_bounds']} giá trị vi phạm giới hạn "
            "vật lý (chuyển thành NaN) — chi tiết tại df.attrs['weather_cleaning']."
        )
        warnings.append(message)
        logger.warning(message)

    # 6. Ngưỡng tỷ lệ khuyết thiếu (chỉ kiểm tra khi caller truyền ngưỡng tường minh)
    max_missing_observed = max((s["missing_pct"] for s in var_stats.values()), default=0.0)
    if max_missing_pct is not None and max_missing_observed > max_missing_pct:
        worst_col = max(var_stats, key=lambda c: var_stats[c]["missing_pct"])
        raise ValueError(
            f"Tỷ lệ khuyết thiếu tối đa {max_missing_observed}% vượt ngưỡng cho phép "
            f"{max_missing_pct}% (biến '{worst_col}'). Nguyên nhân lớp cleaning đã ghi nhận: "
            f"{cleaning_totals}."
        )

    report = {
        "is_valid": is_continuous,
        "validation_status": "passed" if is_continuous else "passed_with_warnings",
        "warnings": warnings,
        "timezone": str(ts_dtype.tz),
        "utc_offset_hours": (
            sample_offset.total_seconds() / 3600.0 if sample_offset is not None else None
        ),
        "total_records": len(df),
        "min_timestamp": str(df["timestamp"].min()) if not df.empty else None,
        "max_timestamp": str(df["timestamp"].max()) if not df.empty else None,
        "is_continuous_hourly": is_continuous,
        "gap_count": gap_count,
        "max_missing_pct": max_missing_observed,
        "missing_pct_threshold": max_missing_pct,
        "cleaning_totals": cleaning_totals,
        "variables_summary": var_stats,
    }
    return report


def resolve_station_metadata(
    source_type: str, source_identifier: Any
) -> Tuple[str, str, Tuple[float, float]]:
    """
    Ánh xạ source/identifier sang (station_id, location_name, (latitude, longitude)).
    Reject / raise error nếu không xác định được trạm hợp lệ tại Hà Nội.
    """
    if source_type == "openaq":
        loc_id = int(source_identifier)
        if loc_id == HANOI_OPENAQ_LOCATION_ID:
            return STATION_OPENAQ_HANOI, LOCATION_OPENAQ_HANOI, COORDS_OPENAQ_HANOI
        elif loc_id == DISQUALIFIED_OPENAQ_LOCATION_ID:
            raise ValueError(
                "OpenAQ location_id=2178 (Del Norte, Albuquerque, NM) đã bị loại bỏ/disqualified. "
                "Tuyệt đối không gán mã trạm Hà Nội cho location 2178!"
            )
        else:
            raise ValueError(f"OpenAQ location_id={loc_id} chưa được xác thực tại Hà Nội!")

    elif source_type == "airnow":
        site_str = str(source_identifier).strip().lower()
        if "hanoi" in site_str:
            return STATION_AIRNOW_HANOI, LOCATION_AIRNOW_HANOI, COORDS_AIRNOW_HANOI
        else:
            raise ValueError(f"AirNow Site '{source_identifier}' không thuộc Hà Nội!")

    elif source_type == "open_meteo":
        return STATION_WEATHER_ERA5, LOCATION_WEATHER_ERA5, COORDS_WEATHER_ERA5

    raise ValueError(f"Nguồn dữ liệu không xác định: {source_type}")


class OpenAQAdapter:
    """
    Adapter thu thập và chuẩn hóa dữ liệu ô nhiễm không khí OpenAQ cho trạm Hà Nội:
    Location ID = 4946811 (556 Nguyễn Văn Cừ, Long Biên, Hà Nội - NCEM / VEA).
    """

    def __init__(
        self,
        location_id: int = HANOI_OPENAQ_LOCATION_ID,
        raw_dir: Path = Path("data/raw"),
        interim_dir: Path = Path("data/interim"),
    ):
        if location_id == DISQUALIFIED_OPENAQ_LOCATION_ID:
            raise ValueError(
                f"Location ID {DISQUALIFIED_OPENAQ_LOCATION_ID} (Del Norte, Albuquerque, NM) đã bị loại bỏ/disqualified. "
                f"Vui lòng sử dụng trạm Hà Nội thực tế: location_id={HANOI_OPENAQ_LOCATION_ID}."
            )
        self.location_id = location_id
        self.station_id, self.location_name, self.coordinates = resolve_station_metadata(
            "openaq", self.location_id
        )
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.interim_dir.mkdir(parents=True, exist_ok=True)

    def _list_s3_keys(self) -> List[str]:
        """Lấy danh sách toàn bộ các khóa tệp S3 lưu trữ cho location_id."""
        url = f"https://openaq-data-archive.s3.amazonaws.com/?prefix=records/csv.gz/locationid={self.location_id}/"
        req = urllib.request.Request(url, headers={"User-Agent": "HanoiAirPollutionResearch/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
        keys = [elem.text for elem in root.findall(".//s3:Key", ns) if elem.text is not None]
        return sorted(keys)

    def _fetch_single_s3_file(self, key: str) -> Optional[pd.DataFrame]:
        """Tải và giải nén một tệp CSV.gz từ OpenAQ S3 public archive."""
        url = f"https://openaq-data-archive.s3.amazonaws.com/{key}"
        req = urllib.request.Request(url, headers={"User-Agent": "HanoiAirPollutionResearch/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    with gzip.GzipFile(fileobj=io.BytesIO(resp.read())) as gz:
                        return pd.read_csv(gz)
        except Exception as e:
            logger.warning(f"Không thể tải tệp S3 {key}: {e}")
            return None
        return None

    def fetch_raw_data(
        self,
        raw_output_name: str = "openaq_raw_4946811.parquet",
        max_workers: int = 25,
        force_reload: bool = False,
    ) -> Tuple[pd.DataFrame, Path]:
        """
        Thu thập toàn bộ dữ liệu thô từ OpenAQ S3 public archive cho trạm 4946811.
        Payload nguồn được lưu nguyên trạng vào data/raw/ (không chỉnh sửa thủ công);
        mọi biến đổi diễn ra ở lớp chuẩn hóa. Tệp đã có sẽ được nạp lại thay vì
        tải lại từ API, trừ khi `force_reload=True`.
        """
        raw_path = self.raw_dir / raw_output_name
        if not force_reload and raw_path.exists() and raw_path.stat().st_size > 0:
            logger.info(f"Tệp thô OpenAQ đã tồn tại tại {raw_path}. Đang nạp lại nguyên trạng (không tải lại)...")
            df_raw = pd.read_parquet(raw_path)
            return df_raw, raw_path

        keys = self._list_s3_keys()
        if not keys:
            raise RuntimeError(f"Không tìm thấy tệp nào trên S3 cho location_id={self.location_id}!")

        logger.info(
            f"Bắt đầu tải {len(keys)} tệp dữ liệu thô OpenAQ S3 cho location_id={self.location_id}..."
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(self._fetch_single_s3_file, keys))

        daily_dfs = [d for d in results if d is not None and not d.empty]
        if not daily_dfs:
            raise RuntimeError(f"Không tải được bản ghi nào cho location_id={self.location_id}!")

        df_raw = pd.concat(daily_dfs, ignore_index=True)
        df_raw.to_parquet(raw_path, index=False, engine="pyarrow", compression="snappy")
        logger.info(
            f"Đã lưu dữ liệu thô OpenAQ 4946811 vào {raw_path} ({len(df_raw)} dòng thô, {len(df_raw.columns)} cột)."
        )
        return df_raw, raw_path

    def to_canonical(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Chuẩn hóa dữ liệu thô OpenAQ sang Canonical Schema:
        1. Lọc địa lý (filter_hanoi_bounds) TRƯỚC canonicalization.
        2. Phân giải metadata trạm đúng quy chuẩn (resolve_station_metadata).
        3. Parse datetime tz-aware Asia/Ho_Chi_Minh (UTC+7).
        4. Làm sạch giá trị (-999, -9999, < 0 -> NaN; 0.0 giữ nguyên).
        5. Tổng hợp chuỗi telemetry dưới giờ (sub-hourly) thành trung bình theo giờ (hourly aggregation).
        6. Kiểm tra tính duy nhất của khóa (station_id, timestamp).
        7. Assertion 100% canonical records nằm trong Bounding Box Hà Nội.
        """
        # 1. Lọc không gian trước canonicalization
        df_geo, geo_stats = filter_hanoi_bounds(df_raw)
        if df_geo.empty:
            raise ValueError("Toàn bộ bản ghi đã bị lọc bỏ do nằm ngoài Bounding Box Hà Nội!")

        df = df_geo.copy()

        # 2. Phân giải metadata trạm
        station_id, location_name, coords = resolve_station_metadata("openaq", self.location_id)

        # 3. Parse datetime
        df["dt_parsed"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
        df = df.dropna(subset=["dt_parsed"]).copy()
        df["timestamp_raw"] = df["dt_parsed"].dt.tz_convert(CANONICAL_TIMEZONE)
        df["timestamp"] = df["timestamp_raw"].dt.floor("h")

        # 4. Lọc các thông số ô nhiễm quan tâm (pm25, pm10)
        df_pollutants = df[df["parameter"].isin(["pm25", "pm10"])].copy()
        df_pollutants["val_clean"] = df_pollutants["value"].apply(clean_air_quality_values)

        # 5. Tổng hợp trung bình theo giờ (hourly aggregation) cho từng thông số
        df_agg = (
            df_pollutants.groupby(["timestamp", "parameter"])["val_clean"]
            .mean()
            .unstack()
            .reset_index()
        )

        for param in ["pm25", "pm10"]:
            if param not in df_agg.columns:
                df_agg[param] = np.nan

        df_agg["station_id"] = station_id
        df_agg["location"] = location_name

        # Sắp xếp tuyến tính
        df_canonical = df_agg[
            ["timestamp", "station_id", "location", "pm25", "pm10"]
        ].sort_values("timestamp").reset_index(drop=True)

        # 6. Kiểm tra trùng lặp khóa
        validate_canonical_uniqueness(df_canonical, key_cols=["station_id", "timestamp"])

        # 7. Assertion đảm bảo 100% bản ghi nằm trong Hà Nội
        assert_canonical_within_hanoi(df_canonical, {station_id: coords})

        return df_canonical


class AirNowDOSAdapter:
    """
    Adapter nạp và chuẩn hóa dữ liệu ô nhiễm không khí lịch sử từ AirNow DOS CSV:
    Trạm: Đại sứ quán Hoa Kỳ tại Hà Nội (Site == "Hanoi", Met One BAM-1020 FEM).
    """

    def __init__(
        self,
        csv_path: Optional[Union[str, Path]] = None,
        raw_dir: Path = Path("data/raw"),
        interim_dir: Path = Path("data/interim"),
    ):
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.csv_path = Path(csv_path) if csv_path else self.raw_dir / "airnow_hanoi_2023.csv"
        self.station_id, self.location_name, self.coordinates = resolve_station_metadata(
            "airnow", "Hanoi"
        )

    def load_and_canonicalize(self, csv_file: Optional[Union[str, Path]] = None) -> pd.DataFrame:
        """
        Nạp tệp AirNow DOS Historical CSV và chuẩn hóa sang Canonical Schema.
        """
        target_file = Path(csv_file) if csv_file else self.csv_path
        if not target_file.exists():
            raise FileNotFoundError(
                f"Tệp AirNow DOS CSV không tồn tại tại {target_file}. "
                "Theo tài liệu Issue #19, tệp lịch sử AirNow yêu cầu tài khoản tổ chức/State Dept để tải trực tiếp."
            )

        df_raw = pd.read_csv(target_file)
        df_raw.columns = [c.strip() for c in df_raw.columns]

        # Kiểm tra cột bắt buộc
        req_cols = ["Site", "Parameter", "Date (LST)", "Value"]
        for c in req_cols:
            if c not in df_raw.columns:
                raise ValueError(f"Tệp AirNow CSV thiếu cột bắt buộc '{c}'! Các cột hiện có: {list(df_raw.columns)}")

        # Lọc trạm Hanoi và thông số PM2.5
        df_site = df_raw[df_raw["Site"].astype(str).str.strip().str.lower() == "hanoi"].copy()
        if df_site.empty:
            raise ValueError("Không tìm thấy bản ghi Site == 'Hanoi' trong tệp AirNow CSV!")

        df_pm25 = df_site[df_site["Parameter"].astype(str).str.strip().str.upper() == "PM2.5"].copy()

        # Parse timestamp (Date (LST) là giờ địa phương UTC+7)
        df_pm25["timestamp"] = pd.to_datetime(df_pm25["Date (LST)"], errors="coerce")
        df_pm25 = df_pm25.dropna(subset=["timestamp"]).copy()
        if df_pm25["timestamp"].dt.tz is None:
            df_pm25["timestamp"] = df_pm25["timestamp"].dt.tz_localize(CANONICAL_TIMEZONE)
        else:
            df_pm25["timestamp"] = df_pm25["timestamp"].dt.tz_convert(CANONICAL_TIMEZONE)

        # Làm sạch giá trị (-999 -> NaN, 0.0 giữ nguyên)
        df_pm25["pm25"] = df_pm25["Value"].apply(clean_air_quality_values)
        df_pm25["pm10"] = np.nan
        df_pm25["station_id"] = self.station_id
        df_pm25["location"] = self.location_name

        df_canonical = df_pm25[
            ["timestamp", "station_id", "location", "pm25", "pm10"]
        ].sort_values("timestamp").reset_index(drop=True)

        # Kiểm tra tính duy nhất và không gian
        validate_canonical_uniqueness(df_canonical, key_cols=["station_id", "timestamp"])
        assert_canonical_within_hanoi(df_canonical, {self.station_id: self.coordinates})

        return df_canonical


class OpenMeteoAdapter:
    """
    Adapter thu thập và chuẩn hóa dữ liệu khí tượng bề mặt ERA5 từ Open-Meteo.

    Vai trò nguồn: PRIMARY khí tượng theo Quyết Định Cổng Nguồn tại Issue #19
    (xem docs/source_profiling_decision.md §12.2). NOAA ISD 48820 chỉ là FALLBACK và
    không được kích hoạt khi Open-Meteo đã đáp ứng yêu cầu.
    """

    def __init__(
        self,
        latitude: float = WEATHER_QUERY_COORDS[0],
        longitude: float = WEATHER_QUERY_COORDS[1],
        timezone: str = CANONICAL_TIMEZONE,
        raw_dir: Path = Path("data/raw"),
        interim_dir: Path = Path("data/interim"),
    ):
        # AC3 (Issue #4): tọa độ khí tượng bắt buộc phải nằm trong địa bàn Hà Nội.
        # Kiểm tra NGAY TẠI CONSTRUCTOR để không phát tải cho vị trí ngoài Hà Nội.
        in_lat = HANOI_BBOX["lat_min"] <= latitude <= HANOI_BBOX["lat_max"]
        in_lon = HANOI_BBOX["lon_min"] <= longitude <= HANOI_BBOX["lon_max"]
        if not (in_lat and in_lon):
            raise ValueError(
                f"Tọa độ truy vấn khí tượng ({latitude}, {longitude}) nằm NGOÀI Bounding Box Hà Nội "
                f"{HANOI_BBOX}! Issue #4 yêu cầu vị trí khí tượng tương thích chính xác với Hà Nội."
            )
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.interim_dir.mkdir(parents=True, exist_ok=True)

    def build_request_url(self, start_date: str, end_date: str) -> str:
        """
        Dựng URL truy vấn Open-Meteo Historical Archive cho dải ngày được yêu cầu.
        Tách riêng để metadata.json có thể ghi lại đúng URL thực thi (provenance).
        """
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure",
            "wind_speed_unit": "ms",
            "timezone": self.timezone,
        }
        encoded_params = urllib.parse.urlencode(params)
        return f"https://archive-api.open-meteo.com/v1/archive?{encoded_params}"

    def fetch_raw_data(
        self,
        start_date: str,
        end_date: str,
        raw_output_name: Optional[str] = None,
        force_reload: bool = False,
    ) -> Tuple[Dict[str, Any], Path]:
        """
        Gọi Open-Meteo Historical Archive API, lấy 6 biến khí tượng Canonical.

        `start_date` / `end_date` là THAM SỐ BẮT BUỘC (không có giá trị mặc định):
        theo Issue #4, dải thời gian khí tượng phải được suy diễn động từ độ phủ
        thực tế của chuỗi chất lượng không khí, tuyệt đối không áp đặt trước một
        khung thời gian lịch sử cố định.

        Payload trả về từ API được ghi nguyên trạng vào data/raw/ (không biến đổi
        giá trị nào trước khi lưu); mọi biến đổi diễn ra ở lớp cleaning/canonical.
        """
        if not start_date or not end_date:
            raise ValueError(
                "start_date và end_date là bắt buộc. Issue #4 yêu cầu dải thời gian khí tượng "
                "được suy diễn động từ độ phủ thực tế của dữ liệu chất lượng không khí, "
                "không được dùng khung thời gian lịch sử cố định."
            )
        if raw_output_name is None:
            raw_output_name = f"open_meteo_raw_{start_date}_{end_date}.json"

        raw_path = self.raw_dir / raw_output_name
        if not force_reload and raw_path.exists() and raw_path.stat().st_size > 0:
            logger.info(
                f"Tệp thô Open-Meteo đã tồn tại tại {raw_path}. Đang nạp lại nguyên trạng "
                "(không gọi lại API) để bảo toàn dữ liệu thô đã lưu."
            )
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            return raw_json, raw_path

        url = self.build_request_url(start_date, end_date)

        logger.info(f"Bắt đầu tải dữ liệu thời tiết Open-Meteo ERA5 từ {start_date} đến {end_date}...")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "HanoiAirPollutionResearch/1.0 (academic; INFO3020)"},
        )

        with urllib.request.urlopen(req, timeout=45) as response:
            if response.status != 200:
                raise RuntimeError(f"Open-Meteo API trả về mã lỗi HTTP {response.status}")
            raw_content = response.read().decode("utf-8")
            raw_json = json.loads(raw_content)

        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_json, f, indent=2, ensure_ascii=False)

        num_hours = len(raw_json.get("hourly", {}).get("time", []))
        logger.info(f"Đã lưu dữ liệu thô Open-Meteo vào {raw_path} ({num_hours} mốc giờ).")

        return raw_json, raw_path

    def to_canonical(self, raw_data: Dict[str, Any], validate: bool = True) -> pd.DataFrame:
        """
        Chuẩn hóa payload Open-Meteo sang Canonical Schema:
        - timestamp: datetime64[ns, Asia/Ho_Chi_Minh]
        - 6 biến khí tượng kiểu float64 theo docs/data_dictionary.md.
        - Làm sạch mã ngụy trang và bảo toàn số 0 hợp lệ.
        - Kiểm tra tính duy nhất, vị trí điểm lưới, và kiểm định chất lượng toàn diện.
        """
        hourly = raw_data.get("hourly", {})
        if not hourly or "time" not in hourly:
            raise ValueError("Payload Open-Meteo không chứa cấu trúc 'hourly.time' hợp lệ!")

        # Ánh xạ biến canonical -> tên trường tại nhà cung cấp (theo docs/data_dictionary.md §4.3)
        provider_fields = {
            "temperature": "temperature_2m",
            "relative_humidity": "relative_humidity_2m",
            "wind_speed": "wind_speed_10m",
            "wind_direction": "wind_direction_10m",
            "precipitation": "precipitation",
            "surface_pressure": "surface_pressure",
        }
        raw_by_var = {var: list(hourly.get(field, [])) for var, field in provider_fields.items()}
        n_hours = len(hourly["time"])
        short_vars = [var for var, vals in raw_by_var.items() if len(vals) != n_hours]
        if short_vars:
            raise ValueError(
                f"Payload Open-Meteo thiếu hoặc thiếu độ dài dữ liệu cho các biến {short_vars} "
                f"(mong đợi {n_hours} mốc giờ như 'time')."
            )

        # Lớp CLEANING: bóc trần mã lỗi ngụy trang, loại giá trị vi phạm giới hạn vật lý,
        # tuyệt đối giữ nguyên giá trị 0.0 hợp lệ. Không có fillna(0).
        cleaned_by_var = {
            var: [clean_weather_values(v, var) for v in vals] for var, vals in raw_by_var.items()
        }
        cleaning_stats = summarize_weather_cleaning(raw_by_var, cleaned_by_var)

        df = pd.DataFrame({"timestamp": pd.to_datetime(hourly["time"]), **cleaned_by_var})

        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(self.timezone)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(self.timezone)

        # Đảm bảo kiểu float64 cho toàn bộ 6 biến khí tượng
        for col in WEATHER_CANONICAL_COLUMNS[1:]:
            df[col] = df[col].astype("float64")

        df_canonical = df[WEATHER_CANONICAL_COLUMNS].sort_values("timestamp").reset_index(drop=True)

        # Minh bạch hóa lớp cleaning: validate_weather_canonical() sẽ báo cáo đây,
        # tránh việc giá trị bị loại bỏ âm thầm mà báo cáo vẫn ghi "0 vi phạm".
        df_canonical.attrs["weather_cleaning"] = cleaning_stats

        # Kiểm tra tính duy nhất của timestamp
        validate_canonical_uniqueness(df_canonical, key_cols=["timestamp"])

        # Kiểm tra tọa độ điểm lưới ERA5 phản hồi (AC3).
        # Bắt buộc payload phải kèm tọa độ: nếu API không trả về thì KHÔNG được
        # âm thầm thay bằng hằng số nội bộ, vì như vậy assertion sẽ tự động pass.
        if raw_data.get("latitude") is None or raw_data.get("longitude") is None:
            raise ValueError(
                "Payload Open-Meteo không trả về tọa độ điểm lưới (latitude/longitude). "
                "Không thể kiểm chứng phạm vi địa lý Hà Nội (AC3) — dừng pipeline."
            )
        grid_lat = raw_data["latitude"]
        grid_lon = raw_data["longitude"]
        assert (
            HANOI_BBOX["lat_min"] <= grid_lat <= HANOI_BBOX["lat_max"]
            and HANOI_BBOX["lon_min"] <= grid_lon <= HANOI_BBOX["lon_max"]
        ), f"Điểm lưới ERA5 ({grid_lat}, {grid_lon}) nằm ngoài Bounding Box Hà Nội!"

        # Kiểm định chất lượng toàn diện nếu validate=True
        if validate:
            validate_weather_canonical(df_canonical)

        return df_canonical


def run_collection_pipeline(
    study_window_start: Optional[str] = None,
    study_window_end: Optional[str] = None,
    airnow_csv_path: Optional[Union[str, Path]] = None,
    save_interim: bool = True,
    metadata_path: Path = Path("data/raw/metadata.json"),
    raw_dir: Path = Path("data/raw"),
    interim_dir: Path = Path("data/interim"),
) -> Dict[str, Any]:
    """
    Hàm thực thi toàn bộ pipeline thu thập và chuẩn hóa dữ liệu ô nhiễm & khí tượng:
    1. Thu thập dữ liệu thô OpenAQ trạm chuẩn Hà Nội (4946811) từ S3 archive.
    2. Xác định cửa sổ truy vấn khí tượng đồng bộ động từ chuỗi ô nhiễm thực tế (nếu không truyền explicit window).
    3. Thu thập dữ liệu thô Open-Meteo ERA5 từ API theo requested query window đồng bộ.
    4. Kiểm tra và tích hợp AirNow DOS Historical Adapter (xác định trạng thái thực tế, không tạo dữ liệu giả).
    5. Lọc không gian Bounding Box Hà Nội từng record và chuẩn hóa sang Canonical Schema.
    6. Xác thực địa lý, bảo đảm 100% bản ghi nằm trong Hà Nội, kiểm tra duplicate key.
    7. Lưu canonical interim files vào data/interim/.
    8. Cập nhật metadata.json với execution metrics thực tế (phân biệt rõ requested study window vs actual source coverage).
    """
    t_start = time.time()
    raw_dir = Path(raw_dir)
    interim_dir = Path(interim_dir)
    metadata_path = Path(metadata_path)
    openaq_adapter = OpenAQAdapter(
        location_id=HANOI_OPENAQ_LOCATION_ID,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
    )
    weather_adapter = OpenMeteoAdapter(
        raw_dir=raw_dir,
        interim_dir=interim_dir,
    )

    # 1. OpenAQ 4946811 Ingestion & Canonicalization
    df_openaq_raw, openaq_raw_path = openaq_adapter.fetch_raw_data()
    _, geo_filter_stats = filter_hanoi_bounds(df_openaq_raw)
    df_air_canonical = openaq_adapter.to_canonical(df_openaq_raw)

    # 2. Xác định cửa sổ truy vấn khí tượng: đồng bộ động từ chuỗi ô nhiễm thực tế nếu không truyền tham số cứng
    if study_window_start is None:
        query_start = df_air_canonical["timestamp"].min().strftime("%Y-%m-%d")
    else:
        query_start = study_window_start

    if study_window_end is None:
        query_end = df_air_canonical["timestamp"].max().strftime("%Y-%m-%d")
    else:
        query_end = study_window_end

    logger.info(
        f"Cửa sổ truy vấn khí tượng Open-Meteo ERA5: {query_start} -> {query_end} "
        f"({'đồng bộ động từ chuỗi OpenAQ' if study_window_start is None and study_window_end is None else 'theo tham số caller'})"
    )

    # 3. Open-Meteo Ingestion & Canonicalization
    weather_raw_json, weather_raw_path = weather_adapter.fetch_raw_data(
        start_date=query_start, end_date=query_end
    )
    df_weather_canonical = weather_adapter.to_canonical(weather_raw_json)
    weather_validation = validate_weather_canonical(
        df_weather_canonical, max_missing_pct=WEATHER_PIPELINE_MAX_MISSING_PCT
    )

    # Kiểm tra giao thoa thời gian (Temporal Overlap) giữa Air Quality và Weather
    df_overlap = pd.merge(df_air_canonical, df_weather_canonical, on="timestamp", how="inner")
    if len(df_overlap) == 0:
        raise AssertionError("Tập giao thoa thời gian giữa chất lượng không khí và khí tượng bị rỗng!")
    if len(df_overlap) > len(df_air_canonical):
        raise AssertionError(
            f"Row explosion: số bản ghi giao thoa ({len(df_overlap)}) vượt quá dữ liệu không khí ({len(df_air_canonical)})!"
        )

    # 4. AirNow DOS Historical Adapter Check & Ingestion
    airnow_adapter = AirNowDOSAdapter(
        csv_path=airnow_csv_path,
        raw_dir=raw_dir,
        interim_dir=interim_dir,
    )
    df_airnow_canonical = None
    if airnow_adapter.csv_path.exists() and airnow_adapter.csv_path.stat().st_size > 0:
        logger.info(f"Phát hiện tệp AirNow DOS tại {airnow_adapter.csv_path}. Đang tiến hành nạp và chuẩn hóa...")
        df_airnow_canonical = airnow_adapter.load_and_canonicalize()
        airnow_sha256 = compute_file_sha256(airnow_adapter.csv_path)
        actual_min_airnow = str(df_airnow_canonical["timestamp"].min())
        actual_max_airnow = str(df_airnow_canonical["timestamp"].max())
        airnow_summary = {
            "canonical_station_id": airnow_adapter.station_id,
            "station_name": airnow_adapter.location_name,
            "adapter_status": "implemented",
            "ingestion_status": "executed",
            "role": "primary_historical_source",
            "raw_file": str(airnow_adapter.csv_path).replace("\\", "/"),
            "raw_sha256": airnow_sha256,
            "canonical_records": len(df_airnow_canonical),
            "actual_min_timestamp": actual_min_airnow,
            "actual_max_timestamp": actual_max_airnow,
            "actual_source_coverage": {
                "actual_min_timestamp": actual_min_airnow,
                "actual_max_timestamp": actual_max_airnow,
                "coverage_derivation": "computed_directly_from_dataframe_timestamps",
            },
        }
    else:
        logger.info(
            f"Tệp AirNow DOS ({airnow_adapter.csv_path}) chưa có trên ổ đĩa. "
            "AirNowDOSAdapter duy trì trạng thái: implemented / pending raw input (không tạo dữ liệu giả)."
        )
        airnow_summary = {
            "canonical_station_id": STATION_AIRNOW_HANOI,
            "station_name": LOCATION_AIRNOW_HANOI,
            "adapter_status": "implemented",
            "ingestion_status": "not_executed_pending_raw_input",
            "role": "historical_source_fallback",
            "raw_input": "unavailable_in_current_execution",
            "note": "AirNowDOSAdapter is implemented in src/data_collection.py. Ingestion is pending valid raw CSV from AirNow-Tech / State Dept due to access restrictions.",
        }

    # 4. Lưu interim canonical files
    air_interim_path = None
    weather_interim_path = None
    if save_interim:
        air_interim_path = openaq_adapter.interim_dir / "air_quality_canonical.parquet"
        weather_interim_path = weather_adapter.interim_dir / "weather_canonical.parquet"
        df_air_canonical.to_parquet(air_interim_path, index=False, compression="snappy")
        df_weather_canonical.to_parquet(weather_interim_path, index=False, compression="snappy")
        logger.info(f"Đã lưu canonical interim files: {air_interim_path} và {weather_interim_path}")

    # 5. Tính toán mã băm SHA-256
    openaq_sha256 = compute_file_sha256(openaq_raw_path)
    weather_sha256 = compute_file_sha256(weather_raw_path)

    # 6. Phân định rõ Requested Window vs Actual Source Coverage
    # actual timestamps được tính toán TRỰC TIẾP từ chuỗi thời gian trong DataFrame sau ingestion
    actual_min_openaq = str(df_air_canonical["timestamp"].min())
    actual_max_openaq = str(df_air_canonical["timestamp"].max())
    actual_min_weather = str(df_weather_canonical["timestamp"].min())
    actual_max_weather = str(df_weather_canonical["timestamp"].max())

    # 6.1 Chỉ số khí tượng ĐƯỢC TÍNH TOÁN từ dữ liệu thực tế (không hardcode)
    weather_missing_pct = {
        col: round(float(df_weather_canonical[col].isna().mean() * 100), 2)
        for col in WEATHER_CANONICAL_COLUMNS[1:]
    }
    weather_max_missing_pct = max(weather_missing_pct.values()) if weather_missing_pct else 0.0
    air_quality_coverage_pct = round(float(len(df_overlap) / len(df_air_canonical) * 100), 2)
    sync_status = (
        "synchronized_100_percent"
        if air_quality_coverage_pct >= 100.0
        else f"partial_coverage_{air_quality_coverage_pct:.2f}pct"
    )
    weather_request_url = weather_adapter.build_request_url(query_start, query_end)
    cleaning_totals = weather_validation["cleaning_totals"]

    summary = {
        "execution_time_seconds": round(time.time() - t_start, 2),
        "requested_study_window": {
            "start": query_start,
            "end": query_end,
            "derived_dynamically_from_air_quality": bool(study_window_start is None and study_window_end is None),
            "note": "Tham số truy vấn phạm vi phân tích khí tượng ERA5.",
        },
        "openaq": {
            "source_location_id": HANOI_OPENAQ_LOCATION_ID,
            "station_id": STATION_OPENAQ_HANOI,
            "station_name": LOCATION_OPENAQ_HANOI,
            "coordinates": COORDS_OPENAQ_HANOI,
            "raw_file": str(openaq_raw_path),
            "sha256": openaq_sha256,
            "raw_records_total": len(df_openaq_raw),
            "geographic_filtering": geo_filter_stats,
            "canonical_records": len(df_air_canonical),
            "pm25_valid_observations": int(df_air_canonical["pm25"].notna().sum()),
            "pm25_missing_observations": int(df_air_canonical["pm25"].isna().sum()),
            "pm25_missing_rate_pct": round(float(df_air_canonical["pm25"].isna().mean() * 100), 2),
            "pm10_valid_observations": int(df_air_canonical["pm10"].notna().sum()),
            "pm10_missing_observations": int(df_air_canonical["pm10"].isna().sum()),
            "pm10_missing_rate_pct": round(float(df_air_canonical["pm10"].isna().mean() * 100), 2),
            "actual_source_coverage": {
                "actual_min_timestamp": actual_min_openaq,
                "actual_max_timestamp": actual_max_openaq,
                "coverage_derivation": "computed_directly_from_dataframe_timestamps",
                "coverage_note": "Trạm 4946811 được OpenAQ tích hợp từ tháng 07/2025; cung cấp chuỗi đo vận hành thực tế tại Hà Nội.",
            },
        },
        "open_meteo": {
            "model": "ECMWF ERA5 Reanalysis",
            "role": "primary_weather_source",
            "source_endpoint": "https://archive-api.open-meteo.com/v1/archive",
            "request_url": weather_request_url,
            "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
            "requested_query_window": {
                "start_date": query_start,
                "end_date": query_end,
                "derived_dynamically": bool(study_window_start is None and study_window_end is None),
            },
            "raw_file": str(weather_raw_path),
            "sha256": weather_sha256,
            "canonical_records": len(df_weather_canonical),
            "missing_rates_pct": weather_missing_pct,
            "max_missing_pct": weather_max_missing_pct,
            "actual_source_coverage": {
                "actual_min_timestamp": actual_min_weather,
                "actual_max_timestamp": actual_max_weather,
                "coverage_derivation": "computed_directly_from_dataframe_timestamps",
                "coverage_note": (
                    "Tính trực tiếp từ chuỗi thời gian thực tế trong DataFrame sau chuẩn hóa; "
                    f"tỷ lệ khuyết thiếu lớn nhất đo được = {weather_max_missing_pct}%."
                ),
            },
            "cleaning_totals": cleaning_totals,
            "validation": weather_validation,
        },
        "airnow": airnow_summary,
        "temporal_integration": {
            "status": sync_status,
            "overlap_records": len(df_overlap),
            "overlap_min_timestamp": str(df_overlap["timestamp"].min()),
            "overlap_max_timestamp": str(df_overlap["timestamp"].max()),
            "air_quality_coverage_pct": air_quality_coverage_pct,
            "row_explosion_detected": False,
        },
    }

    # 7. Cập nhật data/raw/metadata.json
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            meta["schema_version"] = "1.2.0"
            meta["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
            meta["collection_pipeline_execution"] = {
                "executed_issue": "#3 & #4 – Pipeline thu thập và chuẩn hóa dữ liệu chất lượng không khí & khí tượng bề mặt Hà Nội",
                "status": "completed",
                "execution_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "requested_study_window": {
                    "start": f"{query_start}T00:00:00+07:00",
                    "end": f"{query_end}T23:00:00+07:00",
                    "derived_dynamically_from_air_quality": bool(study_window_start is None and study_window_end is None),
                    "note": "Tham số truy vấn phạm vi phân tích khí tượng ERA5.",
                },
                "disqualification_audit": {
                    "disqualified_location_id": DISQUALIFIED_OPENAQ_LOCATION_ID,
                    "reason": "Albuquerque, NM, USA (35.1353N, -106.5847W). 100% purged and excluded from Hanoi analysis.",
                },
                "openaq_ingestion": {
                    "source_location_id": HANOI_OPENAQ_LOCATION_ID,
                    "canonical_station_id": STATION_OPENAQ_HANOI,
                    "station_name": LOCATION_OPENAQ_HANOI,
                    "coordinates": {
                        "latitude": COORDS_OPENAQ_HANOI[0],
                        "longitude": COORDS_OPENAQ_HANOI[1],
                    },
                    "raw_file": f"data/raw/{openaq_raw_path.name}",
                    "raw_sha256": openaq_sha256,
                    "raw_records_total": len(df_openaq_raw),
                    "filtered_out_records": geo_filter_stats["filtered_out_records"],
                    "canonical_records": len(df_air_canonical),
                    "pm25_valid_observations": summary["openaq"]["pm25_valid_observations"],
                    "pm25_missing_observations": summary["openaq"]["pm25_missing_observations"],
                    "pm25_missing_rate_pct": summary["openaq"]["pm25_missing_rate_pct"],
                    "actual_min_timestamp": actual_min_openaq,
                    "actual_max_timestamp": actual_max_openaq,
                    "actual_source_coverage": {
                        "actual_min_timestamp": actual_min_openaq,
                        "actual_max_timestamp": actual_max_openaq,
                        "coverage_derivation": "computed_directly_from_dataframe_timestamps",
                        "coverage_note": "Trạm 4946811 được OpenAQ tích hợp từ tháng 07/2025; không có dữ liệu 2023-2024 trên OpenAQ.",
                    },
                    "interim_file": "data/interim/air_quality_canonical.parquet",
                },
                "open_meteo_ingestion": {
                    "source_model": "ECMWF ERA5 Reanalysis",
                    "source_role": "primary_weather_source",
                    "source_endpoint": "https://archive-api.open-meteo.com/v1/archive",
                    "request_url": weather_request_url,
                    "license": "Creative Commons Attribution 4.0 International (CC BY 4.0)",
                    "attribution": "Weather data by Open-Meteo.com under CC BY 4.0, containing modified Copernicus Climate Change Service information (ERA5)",
                    "requested_query_window": {
                        "start_date": query_start,
                        "end_date": query_end,
                        "derived_dynamically": bool(study_window_start is None and study_window_end is None),
                        "derivation_rule": "derived_from_air_quality_canonical_min_max_timestamps",
                    },
                    "raw_file": f"data/raw/{weather_raw_path.name}",
                    "raw_file_committed_to_git": False,
                    "raw_file_gitignore_rule": "data/raw/*.json",
                    "raw_sha256": weather_sha256,
                    "raw_preservation": "stored_unchanged_no_manual_transformation",
                    "canonical_records": len(df_weather_canonical),
                    "missing_rate_all_variables": f"{weather_max_missing_pct:.2f}%",
                    "actual_min_timestamp": actual_min_weather,
                    "actual_max_timestamp": actual_max_weather,
                    "actual_source_coverage": {
                        "actual_min_timestamp": actual_min_weather,
                        "actual_max_timestamp": actual_max_weather,
                        "coverage_derivation": "computed_directly_from_dataframe_timestamps",
                    },
                    "data_quality_validation": {
                        "status": weather_validation["validation_status"],
                        "is_valid": weather_validation["is_valid"],
                        "warnings": weather_validation["warnings"],
                        "timezone": weather_validation["timezone"],
                        "is_continuous_hourly": weather_validation["is_continuous_hourly"],
                        "gap_count": weather_validation["gap_count"],
                        "max_missing_pct": weather_validation["max_missing_pct"],
                        "physical_bounds_checked": list(WEATHER_PHYSICAL_BOUNDS.keys()),
                        "physical_bounds_violations_in_canonical_output": 0,
                        "values_nulled_by_cleaning": cleaning_totals,
                        "validation_function_is_read_only": True,
                    },
                    "interim_file": "data/interim/weather_canonical.parquet",
                },
                "airnow_dos_ingestion": airnow_summary,
                "temporal_integration": {
                    "status": sync_status,
                    "overlap_records": len(df_overlap),
                    "overlap_min_timestamp": str(df_overlap["timestamp"].min()),
                    "overlap_max_timestamp": str(df_overlap["timestamp"].max()),
                    "air_quality_coverage_pct": air_quality_coverage_pct,
                    "row_explosion_detected": False,
                },
            }

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            logger.info(f"Đã cập nhật metadata.json tại {metadata_path} thành công!")
        except Exception as e:
            logger.warning(f"Không thể cập nhật metadata.json: {e}")

    logger.info("Hoàn tất pipeline thu thập và chuẩn hóa dữ liệu thành công!")
    return summary


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    summary_report = run_collection_pipeline()
    print("\n--- BÁO CÁO KẾT QUẢ THU THẬP ---")
    print(json.dumps(summary_report, indent=2, ensure_ascii=False))
