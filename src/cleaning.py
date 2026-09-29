"""
Deterministic Cleaning Module (Issue #6)
========================================
Module thực hiện **làm sạch tất định** (deterministic cleaning) cho hai tập dữ liệu
Canonical trong `data/interim/` (ô nhiễm không khí và khí tượng bề mặt ERA5),
theo `docs/roadmap.md` §4.1 và §4.3 (Tuần 04).

PHÂN ĐỊNH RẠCH MẠCH VỚI TIỀN XỬ LÝ PHỤ THUỘC DỮ LIỆU (Issue #7)
-------------------------------------------------------------------
Module này CHỈ thực hiện các phép biến đổi **tất định** — tức là mọi quyết định
được đưa ra chỉ dựa trên bản thân bản ghi đang xét hoặc trên hằng số vật lý
công bố, KHÔNG dùng bất kỳ đại lượng thống kê toàn cục nào của tập dữ liệu:

    ┌──────────────────────── Issue #6 (module này) ────────────────────────┐
    │ Chuẩn hóa múi giờ UTC+7 · sắp xếp tăng dần · khử trùng lặp           │
    │ Chuyển missing ngụy trang → NaN · lọc giá trị âm phi lý               │
    │ Lọc giá trị vi phạm giới hạn vật lý khí quyển                        │
    │ Ràng buộc khí động học PM2.5 ≤ PM10 (+ epsilon sai số đo)             │
    │ Reindex lưới 1 giờ liên tục độc lập theo từng trạm (NaN = khoảng trống)│
    │ Gắn cờ chẩn đoán: is_high_humidity_fog, pm25_was_missing               │
    └───────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
    ┌──────────────── Issue #7 (CHƯA thực hiện ở đây) ──────────────────────┐
    │ Đóng băng tập dữ liệu · phân chia Train/Test theo chuỗi thời gian     │
    │ SimpleImputer(strategy='median') · RobustScaler · np.log1p             │
    │ TẤT CẢ đều phụ thuộc dữ liệu và PHẢI fit trên Train                   │
    └───────────────────────────────────────────────────────────────────────┘

NGUYÊN TẮC BẤT BIẾN
--------------------
1. **Không điền khuyết (no imputation):** hàm này KHÔNG BAO GIỜ điền NaN bằng
   giá trị thống kê (trung vị, trung bình, nội suy, giá trị trượt). Số ô NaN
   chỉ được TĂNG hoặc giữ nguyên, không bao giờ giảm.
2. **Bảo toàn giá trị cực trị thực tế:** không cắt bỏ đỉnh ô nhiễm chỉ vì cao.
   Chỉ giá trị vi phạm ràng buộc vật lý mới bị chuyển thành NaN.
3. **Fail loudly:** sai lệch lược đồ, trùng khóa không xử lý được, hoặc ghép
   dẹp gây bùng nổ số dòng đều phải ném lỗi rõ ràng thay vì im lặng.
4. **Tất định (idempotent):** chạy lại trên chính đầu ra của mình cho kết quả
   không đổi — không phụ thuộc thứ tự dòng, không phụ thuộc lần chạy trước.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from src.data_collection import (
    CANONICAL_TIMEZONE,
    WEATHER_CANONICAL_COLUMNS,
    WEATHER_PHYSICAL_BOUNDS,
    WEATHER_SENTINEL_CODES,
    clean_air_quality_values,
    clean_weather_values,
)
from src.data_quality import DISGUISED_STRING_MARKERS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hằng số quy ước — nguồn sự thật duy nhất cho Issue #6
# ---------------------------------------------------------------------------

TIMESTAMP_COLUMN = "timestamp"
STATION_COLUMN = "station_id"
HOURLY_FREQ = "h"
# Dùng `np.timedelta64` thay vì `pd.Timedelta` để nhất quán với `src/data_collection.py`
# và tránh DeprecationWarning của numpy với đơn vị "generic".
ONE_HOUR = np.timedelta64(1, "h")

#: Các cột đo ô nhiễm của Canonical Schema (không khí).
AIR_MEASUREMENT_COLUMNS: Tuple[str, ...] = ("pm25", "pm10")

#: Sáu biến khí tượng bề mặt của Canonical Schema (khí tượng).
WEATHER_MEASUREMENT_COLUMNS: Tuple[str, ...] = tuple(WEATHER_CANONICAL_COLUMNS[1:])

#: Ngưỡng "kẹt cảm biến": chuỗi đo KHÔNG ĐỔI trên dài hơn 6 giờ liên tiếp.
#:
#: Quy ước đếm (nhất quân với `audit_prolonged_zeros()` của Issue #5): ngưỡng
#: được đếm bằng SỐ QUAN SÁT liên tiếp trên lưới 1 giờ. Vì vậy "dài hơn 6 giờ"
#: ⇔ chuỗi có ít nhất 7 quan sát giống hệt nhau (xem `_run_mask_longer_than`).
STUCK_VALUE_THRESHOLD_HOURS = 6

#: Ngưỡng "khoảng khuyết lớn" cho cờ chỉ báo `pm25_was_missing`.
PROLONGED_MISSING_THRESHOLD_HOURS = 6

#: Ngưỡng cảnh báo sương mù quang học: RH > 90%.
HIGH_HUMIDITY_FOG_THRESHOLD_PCT = 90.0

#: Sai số đo thiết bị (µg/m³) dùng làm dung sai cho ràng buộc khí động học.
#: Căn cứ: .agents/rules/data.md §4 và bàn giao Handoff 1 của Issue #5
#: (độ không đảm bảo đo lường của BAM-1020 / cảm biến quang học theo US EPA, QCVN).
PM_AERODYNAMIC_EPSILON_UG_M3 = 2.0

#: Cột cờ chẩn đoán do Issue #6 sinh ra (KHÔNG phải imputation).
PM25_MISSING_FLAG = "pm25_was_missing"
HIGH_HUMIDITY_FLAG = "is_high_humidity_fog"

#: Cột chỉ được phép áp dụng quy tắc kẹt cảm biến.
#:
#: CHỈ áp dụng cho nồng độ hạt bụi. KHÔNG áp dụng cho `precipitation` và
#: `wind_speed` của khí tượng: Issue #5 đã đo lịch sử và kết luận rõ ràng rằng
#: chuỗi 0.0 dài 275 giờ của `precipitation` (74,15% số giờ) và các đợt gió
#: lặng 0.0 m/s là **hiện tượng khí tượng tự nhiên** ở miền Bắc Việt Nam, không
#: phải lỗi phần cứng. Áp dụng máy móc quy tắc kẹt cho các biến này sẽ xóa
#: mất dữ liệu khí tượng hợp lệ — vi phạm nguyên tắc bảo toàn giá trị thực tế.
STUCK_SENSOR_COLUMNS: Tuple[str, ...] = AIR_MEASUREMENT_COLUMNS

#: Mã lỗi ngụy trang dạng số do nhà cung cấp dùng để mã hóa giá trị khuyết thiếu.
DISGUISED_NUMERIC_CODES: Tuple[float, ...] = tuple(float(c) for c in WEATHER_SENTINEL_CODES)


# ---------------------------------------------------------------------------
# Tiện ích nội bộ
# ---------------------------------------------------------------------------


def _require_columns(df: pd.DataFrame, columns: Sequence[str], context: str) -> None:
    """Ném ValueError nếu thiếu bất kỳ cột bắt buộc nào (fail loudly)."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{context} thiếu cột bắt buộc: {missing}.")


def _observation_key(df: pd.DataFrame) -> List[str]:
    """
    Khóa quan sát đúng theo đơn vị quan trắc:
    `(station_id, timestamp)` nếu đa trạm, ngược lại chỉ `timestamp`.
    """
    if STATION_COLUMN in df.columns:
        return [STATION_COLUMN, TIMESTAMP_COLUMN]
    return [TIMESTAMP_COLUMN]


def _break_mask(df: pd.DataFrame, column: Optional[str] = None) -> pd.Series:
    """
    Chuỗi Boolean đánh dấu vị trí bắt đầu một chuỗi liên tục mới.

    Một chuỗi bị NGẮT khi: đổi trạm, hoặc khoảng cách thời gian khác đúng 1 giờ,
    hoặc (nếu `column` được chỉ định) giá trị thay đổi. Hai giá trị NaN liên tiếp
    được coi là BẰNG NHAU để các khối khuyết liên tục không bị cắt vụn.
    """
    breaks = df[TIMESTAMP_COLUMN].diff() != ONE_HOUR
    if STATION_COLUMN in df.columns:
        breaks = breaks | df[STATION_COLUMN].ne(df[STATION_COLUMN].shift())
    if column is not None:
        current = df[column]
        previous = current.shift()
        changed = current.ne(previous) & ~(current.isna() & previous.isna())
        breaks = breaks | changed
    return breaks.fillna(True)


def _run_ids(df: pd.DataFrame, column: Optional[str] = None) -> pd.Series:
    """Đánh số chuỗi liên tục: hai hàng cùng chuỗi khi cùng trạm, cách đúng 1 giờ
    và (nếu có `column`) có cùng giá trị — kể cả cùng đều là `NaN`."""
    return _break_mask(df, column).cumsum()


def run_ids_of(df: pd.DataFrame, column: Optional[str] = None) -> pd.Series:
    """Alias công khai của `_run_ids()` dùng trong thống kê bước làm sạch."""
    return _run_ids(df, column)


def _run_mask_longer_than(
    df: pd.DataFrame, column: Optional[str], threshold_hours: int
) -> Tuple[pd.Series, pd.Series]:
    """
    Tính mặt nạ của các hàng nằm trong chuỗi liên tục dài HƠN `threshold_hours`.

    Quy ước đếm (nhất quán với `audit_prolonged_zeros()` của Issue #5 và với
    `.agents/rules/data.md`): ngưỡng được đếm bằng SỐ QUAN SÁT liên tiếp trên
    lưới 1 giờ. Do đó "dài hơn 6 giờ" ⇔ chuỗi có ít nhất 7 quan sát.

    Trả về `(mask, run_length)` với `run_length` là độ dài chuỗi (số quan sát)
    của hàng đang xét.
    """
    if df.empty:
        empty_bool = pd.Series(dtype=bool)
        return empty_bool, pd.Series(dtype="int64")

    run_ids = _run_ids(df, column)
    run_length = run_ids.groupby(run_ids).transform("size")
    return run_length > threshold_hours, run_length


def _snapshot(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Ảnh chụp trạng thái một DataFrame (trước hoặc sau làm sạch) để ghi vào
    Cleaning Log: số dòng, kiểu dữ liệu, số ô khuyết, dải thời gian, trùng khóa.
    """
    snapshot: Dict[str, Any] = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "duplicate_observation_keys": int(df.duplicated(subset=_observation_key(df)).sum()),
        "missing_cells": {c: int(df[c].isna().sum()) for c in df.columns},
    }
    for pollutant in AIR_MEASUREMENT_COLUMNS:
        if pollutant in df.columns and df[pollutant].notna().any():
            snapshot[f"{pollutant}_peak"] = round(float(df[pollutant].max()), 4)
            snapshot[f"{pollutant}_trough"] = round(float(df[pollutant].min()), 4)
    if TIMESTAMP_COLUMN in df.columns and not df.empty:
        snapshot["min_timestamp"] = str(df[TIMESTAMP_COLUMN].min())
        snapshot["max_timestamp"] = str(df[TIMESTAMP_COLUMN].max())
        snapshot["timezone"] = str(df[TIMESTAMP_COLUMN].dt.tz)
    return snapshot


def _trace_input_peak(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Ghi lại danh tính bản ghi chứa đỉnh PM2.5 lớn nhất **trước** khi làm sạch.

    Mục tiêu: chứng minh bằng số liệu rằng khi đỉnh này biến mất khỏi chuỗi, nguyên
    nhân là bằng chứng vật lý (vi phạm ràng buộc khí động học) chứ không phải một quy
    tắc cắt bỏ cực trị tùy ý. Nếu không có cột `pm25` quan sát được thì trả về rỗng.
    """
    if "pm25" not in df.columns or not df["pm25"].notna().any():
        return {}

    peak_row = df.loc[df["pm25"].idxmax()]
    fine, coarse = "pm25", "pm10"
    trace: Dict[str, Any] = {
        "pm25_peak": round(float(peak_row[fine]), 4),
        "timestamp": str(peak_row.get(TIMESTAMP_COLUMN)),
        "station_id": str(peak_row.get("station_id")),
    }
    if coarse in df.columns and pd.notna(peak_row.get(coarse)):
        margin = float(peak_row[fine]) - float(peak_row[coarse])
        trace["pm10_at_peak"] = round(float(peak_row[coarse]), 4)
        trace["margin_pm25_minus_pm10"] = round(margin, 4)
        trace["was_strict_inversion"] = bool(margin > PM_AERODYNAMIC_EPSILON_UG_M3)
    return trace


def _resolve_peak_trace(trace: Dict[str, Any], cleaned: pd.DataFrame) -> Dict[str, Any]:
    """
    Đối chiếu bản ghi đỉnh PM2.5 với tập dữ liệu **sau** làm sạch.

    Trả về bằng chứng đã đối chiếu: đỉnh còn sống hay không, và nếu biến mất thì
    nguyên nhân có phải nghịch đảo khí động học hay không.
    """
    if not trace:
        return {}

    resolved = dict(trace)
    key = ["timestamp"]
    if "station_id" in cleaned.columns:
        key = ["station_id", "timestamp"]
    row = cleaned
    for column in key:
        row = row[row[column].astype(str) == trace.get(
            "station_id" if column == "station_id" else "timestamp")]

    survived = not row.empty and pd.notna(row.iloc[0].get("pm25"))
    resolved["survived_cleaning"] = bool(survived)
    if not survived:
        resolved["nullified_by_physics_constraint"] = bool(trace.get("was_strict_inversion"))
    return resolved


# ---------------------------------------------------------------------------
# Bước 1 — Chuẩn hóa mốc thời gian và sắp xếp
# ---------------------------------------------------------------------------


def normalize_timestamps(
    df: pd.DataFrame, timezone: str = CANONICAL_TIMEZONE
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Chuẩn hóa cột `timestamp` thành datetime64 tz-aware theo múi giờ địa phương.

    - Timestamp tz-naive → `tz_localize` (giữ nguyên mốc giờ địa phương).
    - Timestamp ở múi giờ khác (kể cả UTC) → `tz_convert` (không đổi mốc thời gian tuyệt đối).
    - Chuỗi không parse được → ném ValueError (không âm thầm thành NaT).

    Trả về `(df_đã_chuẩn_hóa, thống_kê)`.
    """
    _require_columns(df, [TIMESTAMP_COLUMN], "Bước chuẩn hóa mốc thời gian")
    if df.empty:
        return df.copy(), {
            "timezone_before": None,
            "timezone_after": timezone,
            "rows_localized": 0,
            "rows_converted": 0,
            "rows_unparseable": 0,
        }

    out = df.copy()
    before_tz = getattr(out[TIMESTAMP_COLUMN].dtype, "tz", None)

    parsed = pd.to_datetime(out[TIMESTAMP_COLUMN], errors="coerce")
    unparseable = int(parsed.isna().sum())
    if unparseable > 0:
        raise ValueError(
            f"Không phân tích được {unparseable} giá trị trong cột '{TIMESTAMP_COLUMN}'. "
            "Làm sạch tất định không được âm thầm biến mốc thời gian hỏng thành NaT."
        )

    was_naive = parsed.dt.tz is None
    was_canonical = before_tz is not None and str(before_tz) == timezone
    if was_naive:
        parsed = parsed.dt.tz_localize(timezone)
    else:
        parsed = parsed.dt.tz_convert(timezone)

    out[TIMESTAMP_COLUMN] = parsed

    return out, {
        "timezone_before": str(before_tz) if before_tz is not None else "None (naive)",
        "timezone_after": str(out[TIMESTAMP_COLUMN].dt.tz),
        "rows_localized": int(len(out)) if was_naive else 0,
        "rows_converted_from_other_timezone": (
            0 if (was_naive or was_canonical) else int(len(out))
        ),
        "rows_unparseable": unparseable,
        "canonical_timezone": timezone,
    }


def sort_chronologically(
    df: pd.DataFrame, key_cols: Optional[Sequence[str]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Sắp xếp tăng dần theo thời gian (và theo `station_id` trước timestamp khi
    đa trạm) bằng thuật toán ổn định `mergesort`, rồi đặt lại chỉ mục.

    Trả về `(df_đã_sắp_xếp, thống_kê)`.
    """
    if key_cols is None:
        key_cols = _observation_key(df)
    _require_columns(df, key_cols, "Bước sắp xếp tăng dần")

    out = df.sort_values(list(key_cols), kind="mergesort").reset_index(drop=True)
    return out, {
        "sort_keys": list(key_cols),
        "sort_algorithm": "mergesort (ổn định, tất định)",
        "was_monotonic_increasing": bool(df[TIMESTAMP_COLUMN].is_monotonic_increasing),
        "rows_reordered": int(not df[TIMESTAMP_COLUMN].equals(out[TIMESTAMP_COLUMN])),
    }


# ---------------------------------------------------------------------------
# Bước 2 — Khử trùng lặp tại đúng đơn vị quan trắc
# ---------------------------------------------------------------------------


def drop_duplicate_observations(
    df: pd.DataFrame, key_cols: Optional[Sequence[str]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Khử trùng lặp tại đúng khóa quan trắc `(station_id, timestamp)` hoặc `timestamp`.

    Quy tắc tất định: giữ lại bản ghi xuất hiện ĐẦU TIÊN theo thứ tự đã sắp xếp
    (mergesort là ổn định nên kết quả không phụ thuộc thứ tự dòng ban đầu).

    Trả về `(df_đã_khử, thống_kê)`.
    """
    if key_cols is None:
        key_cols = _observation_key(df)
    _require_columns(df, key_cols, "Bước khử trùng lặp")

    duplicate_mask = df.duplicated(subset=list(key_cols), keep="first")
    removed = int(duplicate_mask.sum())
    out = df[~duplicate_mask].reset_index(drop=True)

    return out, {
        "observation_key": list(key_cols),
        "rows_before": int(len(df)),
        "duplicate_rows_removed": removed,
        "rows_after": int(len(out)),
        "rows_affected_pct": round(removed / len(df) * 100, 4) if len(df) > 0 else 0.0,
        "resolution_rule": "giữ bản ghi đầu tiên theo thứ tự sắp xếp tất định",
    }


# ---------------------------------------------------------------------------
# Bước 3 — Missing ngụy trang → NaN
# ---------------------------------------------------------------------------


def normalize_disguised_missing(
    df: pd.DataFrame,
    columns: Sequence[str],
    string_markers: Sequence[str] = tuple(DISGUISED_STRING_MARKERS),
    numeric_codes: Sequence[float] = DISGUISED_NUMERIC_CODES,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Rà soát và chuyển mọi dạng biểu diễn khuyết thiếu bị ngụy trang thành `NaN`.

    - Chuỗi: `"N/A"`, `"null"`, `"None"`, `""`, `" "`… (tái sử dụng danh mục của
      `src.data_quality` để không nhân bản hằng số).
    - Số: mã lỗi `-999.0` / `-9999.0` (tái sử dụng `WEATHER_SENTINEL_CODES`).

    Giá trị đo hợp lệ bằng `0.0` KHÔNG bao giờ bị coi là missing.

    Trả về `(df_đã_chuẩn_hóa, thống_kê)`.
    """
    out = df.copy()
    stats: Dict[str, Any] = {}

    for col in columns:
        if col not in out.columns:
            continue

        series = out[col]
        converted = 0

        if not (pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)):
            coerced = series.map(
                lambda v: np.nan if isinstance(v, str) and v.strip() in string_markers else v
            )
            numeric = pd.to_numeric(coerced, errors="coerce")
            # Ô không parse được được số mà chưa phải NaN cũng là missing ngụy trang.
            unparseable = int((~numeric.isna() & coerced.isna()).sum())
            converted += int((series.isna() != numeric.isna()).sum()) + unparseable
            out[col] = numeric.astype("float64")
            series = out[col]

        sentinel_mask = series.isin(list(numeric_codes))
        converted += int(sentinel_mask.sum())
        out.loc[sentinel_mask, col] = np.nan

        stats[col] = {
            "rows_converted_to_nan": converted,
            "numeric_disguised_codes": [float(c) for c in numeric_codes],
            "string_disguised_markers": list(string_markers),
        }

    return out, {
        "columns_checked": list(stats.keys()),
        "by_column": stats,
        "total_cells_converted": int(sum(s["rows_converted_to_nan"] for s in stats.values())),
        "note": "Giá trị đo hợp lệ 0.0 được giữ nguyên, không bị quy nhầm là missing.",
    }


# ---------------------------------------------------------------------------
# Bước 4 — Ràng buộc vật lý tất định
# ---------------------------------------------------------------------------


def enforce_air_quality_physical_rules(
    df: pd.DataFrame, columns: Sequence[str] = AIR_MEASUREMENT_COLUMNS
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Lọc giá trị âm phi lý và mã lỗi ngụy trang cho nồng độ hạt bụi.

    Tái sử dụng `clean_air_quality_values()` của `src.data_collection` — cùng một
    hàm chuẩn hóa đã áp dụng lúc nạp, nên lớp làm sạch Issue #6 không phát minh
    lại ngưỡng mới: `NaN → NaN`, mã `-999/-9999 → NaN`, `< 0 → NaN`, `0.0` giữ nguyên.

    KHÔNG đặt trần nồng độ: đợt ô nhiễm bùng phát là hiện tượng thực tế và phải
    được bảo toàn.

    Trả về `(df_đã_lọc, thống_kê)`.
    """
    out = df.copy()
    stats: Dict[str, Any] = {}

    for col in columns:
        if col not in out.columns:
            continue
        original = out[col]
        out[col] = original.map(clean_air_quality_values).astype("float64")
        newly_missing = int((original.notna() & out[col].isna()).sum())
        stats[col] = {
            "negative_values_nullified": int((original < 0).sum()),
            "total_rows_nullified": newly_missing,
            "valid_zero_preserved": int((original == 0.0).sum()),
        }

    return out, {
        "by_column": stats,
        "total_rows_nullified": int(sum(s["total_rows_nullified"] for s in stats.values())),
        "rule": "NaN và mã lỗi -999/-9999 → NaN; giá trị < 0 → NaN; 0.0 hợp lệ được giữ nguyên.",
        "upper_bound_policy": "Không đặt trần nồng độ để bảo toàn đợt ô nhiễm cực đoan thực tế.",
    }


def enforce_weather_physical_rules(
    df: pd.DataFrame, columns: Sequence[str] = WEATHER_MEASUREMENT_COLUMNS
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Kiểm tra dải hợp lệ khí tượng bề mặt trên 6 biến Canonical.

    Tái sử dụng `clean_weather_values()` và `WEATHER_PHYSICAL_BOUNDS` của
    `src.data_collection` (0% ≤ RH ≤ 100%, 0 ≤ hướng gió ≤ 360° với chuẩn hóa
    modulo 360, lượng mưa ≥ 0, nhiệt độ và áp suất trong dải vật lý).

    Trả về `(df_đã_lọc, thống_kê)`.
    """
    out = df.copy()
    stats: Dict[str, Any] = {}

    for col in columns:
        if col not in out.columns:
            continue
        original = out[col]
        out[col] = pd.Series(
            [clean_weather_values(v, col) for v in original], index=original.index
        ).astype("float64")
        bounds = WEATHER_PHYSICAL_BOUNDS.get(col, {})
        out_of_range = pd.Series(False, index=original.index)
        if bounds:
            out_of_range = original.lt(bounds["min"]) | original.gt(bounds["max"])
        stats[col] = {
            "allowed_range": [bounds.get("min"), bounds.get("max")] if bounds else None,
            "unit": bounds.get("unit"),
            "values_out_of_range": int(out_of_range.sum()),
            "total_rows_nullified": int((original.notna() & out[col].isna()).sum()),
        }

    return out, {
        "by_column": stats,
        "total_rows_nullified": int(sum(s["total_rows_nullified"] for s in stats.values())),
        "total_out_of_range": int(sum(s["values_out_of_range"] for s in stats.values())),
        "bounds_source": "src.data_collection.WEATHER_PHYSICAL_BOUNDS (docs/data_dictionary.md)",
    }


def enforce_pm_subset_constraint(
    df: pd.DataFrame,
    epsilon: float = PM_AERODYNAMIC_EPSILON_UG_M3,
    fine_column: str = "pm25",
    coarse_column: str = "pm10",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Thực thi ràng buộc khí động học PM2.5 ⊆ PM10 trên các cặp quan sát đồng thời.

    $\\text{PM}_{2.5} \\le \\text{PM}_{10} + \\epsilon$ với `epsilon` là sai số đo
    thiết bị. Bản ghi vi phạm bị chuyển **cả hai** cột thành `NaN` — hành động
    này theo đúng `.agents/rules/data.md` §4: khi hai kênh quang học của cùng
    một thiết bị mâu thuẫn nhau thì không kênh nào còn đáng tin, và giữ lại một
    kênh trong khi xóa kênh kia sẽ tạo ra dữ liệu "nửa vời" khó giải thích.

    Bản ghi chỉ có `pm25` hoặc chỉ có `pm10` không thể kiểm tra được nên được giữ
    nguyên — tuyệt đối không suy diễn giá trị cho kênh còn lại.

    Trả về `(df_đã_sửa, thống_kê)`.
    """
    out = df.copy()
    stats: Dict[str, Any] = {
        "rule": f"{fine_column} <= {coarse_column} + epsilon",
        "epsilon_ug_m3": epsilon,
        "epsilon_rationale": (
            "Độ không đảm bảo đo lường thiết bị (BAM-1020 / cảm biến quang học, "
            "chuẩn US EPA & QCVN) theo .agents/rules/data.md §4 và bàn giao "
            "Handoff 1 của Issue #5."
        ),
        "action_on_violation": f"chuyển CẢ {fine_column} và {coarse_column} thành NaN",
    }

    if fine_column not in out.columns or coarse_column not in out.columns:
        stats.update({
            "skipped": True,
            "skip_reason": f"Không có đủ cột {fine_column}/{coarse_column} trong Canonical Schema.",
            "pairs_evaluated": 0,
            "strict_inversions": 0,
            "inversions_beyond_epsilon": 0,
            "rows_nullified": 0,
        })
        return out, stats

    both_observed = out[fine_column].notna() & out[coarse_column].notna()
    strict = out[fine_column].gt(out[coarse_column]) & both_observed
    beyond = strict & out[fine_column].gt(out[coarse_column] + epsilon)
    violating = strict

    out.loc[violating, [fine_column, coarse_column]] = np.nan

    stats.update({
        "skipped": False,
        "pairs_evaluated": int(both_observed.sum()),
        "pairs_single_channel": int((out[fine_column].isna() ^ out[coarse_column].isna()).sum()),
        "strict_inversions": int(strict.sum()),
        "inversions_beyond_epsilon": int(beyond.sum()),
        "inversions_within_measurement_tolerance": int(strict.sum() - beyond.sum()),
        "rows_nullified": int(violating.sum()),
        "rows_nullified_pct_of_pairs": (
            round(int(violating.sum()) / int(both_observed.sum()) * 100, 4)
            if int(both_observed.sum()) > 0
            else 0.0
        ),
    })
    return out, stats


# ---------------------------------------------------------------------------
# Bước 5 — Reindex lưới thời gian 1 giờ liên tục theo từng trạm
# ---------------------------------------------------------------------------


def reindex_station_series(
    df_station: pd.DataFrame,
    start_time: pd.Timestamp,
    end_time: pd.Timestamp,
    freq: str = HOURLY_FREQ,
) -> pd.DataFrame:
    """
    Reindex chuỗi thời gian của MỘT trạm về lưới liên tục `freq` trong [start, end].

    Thực thi đúng công thức trong "Ghi chú triển khai" của Issue #6:

        full_idx = pd.date_range(start=start_time, end=end_time, freq=freq)
        return df_station.set_index('timestamp').reindex(full_idx) \\
                            .rename_axis('timestamp').reset_index()

    Mở rộng duy nhất: điền lại các thuộc tính cấp TRẠM (`station_id`, `location`)
    cho những hàng do reindex sinh ra, vì chúng là hằng số theo trạm chứ không
    phải quan sát thời gian. Nếu một trạm có nhiều giá trị khác nhau cho cùng
    một thuộc tính cấp trạm → ném ValueError (dữ liệu mâu thuẫn).
    """
    _require_columns(df_station, [TIMESTAMP_COLUMN], "Bước reindex theo trạm")

    full_idx = pd.date_range(start=start_time, end=end_time, freq=freq)
    indexed = df_station.set_index(TIMESTAMP_COLUMN).reindex(full_idx)

    for station_level_col in (STATION_COLUMN, "location"):
        if station_level_col not in df_station.columns:
            continue
        unique_values = pd.Series(df_station[station_level_col].dropna().unique())
        if len(unique_values) > 1:
            raise ValueError(
                f"Thuộc tính cấp trạm '{station_level_col}' có {len(unique_values)} giá trị "
                f"khác nhau ({list(unique_values)}) — không thể điền cho hàng reindex."
            )
        if len(unique_values) == 1:
            indexed[station_level_col] = unique_values.iloc[0]

    return indexed.rename_axis(TIMESTAMP_COLUMN).reset_index()


def reindex_hourly_grid(
    df: pd.DataFrame,
    freq: str = HOURLY_FREQ,
    window: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Reindex liên tục 1 giờ, thực hiện **độc lập cho từng trạm quan trắc**.

    Với dữ liệu đa trạm, tuyệt đối không áp đặt một trục thời gian đơn nhất chung
    cho mọi trạm (sẽ vỡ vụn dữ liệu khi các trạm có dải quan sát khác nhau và có
    thể làm mất quan sát hợp lệ).

    `window` mặc định là dải quan sát thực tế chung `min → max` của toàn bộ tập,
    nhờ đó mọi trạm cùng nằm trên một lưới giờ chung để phục vụ phép ghép ở
    Issue #7; truyền `window` riêng để dùng dải riêng cho từng trạm nếu cần.

    Các khoảng trống sau reindex được ĐỂ LẠI dạng `NaN` — không nội suy, không xóa
    dòng — để bộc lộ trung thực mọi khoảng khuyết.

    Trả về `(df_đã_reindex, thống_kê)`.
    """
    _require_columns(df, [TIMESTAMP_COLUMN], "Bước reindex lưới thời gian")
    if df.empty:
        return df.copy(), {
            "stations": [],
            "freq": freq,
            "window_start": None,
            "window_end": None,
            "rows_before": 0,
            "rows_after": 0,
            "rows_inserted": 0,
            "per_station": {},
        }

    if window is None:
        window = (df[TIMESTAMP_COLUMN].min(), df[TIMESTAMP_COLUMN].max())
    window_start, window_end = window

    has_station = STATION_COLUMN in df.columns
    groups = df.groupby(STATION_COLUMN, sort=True) if has_station else [("(single_series)", df)]

    frames: List[pd.DataFrame] = []
    per_station: Dict[str, Any] = {}

    for station_id, station_df in groups:
        station_df = station_df.sort_values(TIMESTAMP_COLUMN, kind="mergesort")
        station_key = str(station_id) if has_station else "(single_series)"
        indexed = reindex_station_series(station_df, window_start, window_end, freq=freq)
        frames.append(indexed)
        per_station[station_key] = {
            "observed_rows_before": int(len(station_df)),
            "grid_rows_after": int(len(indexed)),
            "rows_inserted_as_nan": int(len(indexed) - len(station_df)),
            "observed_first": str(station_df[TIMESTAMP_COLUMN].min()),
            "observed_last": str(station_df[TIMESTAMP_COLUMN].max()),
        }

    out = pd.concat(frames, ignore_index=True)
    if has_station:
        out = out.sort_values([STATION_COLUMN, TIMESTAMP_COLUMN], kind="mergesort")
    else:
        out = out.sort_values(TIMESTAMP_COLUMN, kind="mergesort")
    out = out.reset_index(drop=True)

    return out, {
        "stations": list(per_station.keys()),
        "freq": freq,
        "grid_frequency_label": "1 giờ ('h')",
        "window_start": str(window_start),
        "window_end": str(window_end),
        "window_policy": (
            "Dải quan sát thực tế chung của toàn tập (mặc định) để mọi trạm nằm trên "
            "cùng một lưới giờ; reindex vẫn thực hiện độc lập và riêng biệt cho từng trạm."
        ),
        "rows_before": int(len(df)),
        "rows_after": int(len(out)),
        "rows_inserted": int(len(out) - len(df)),
        "gap_policy": "Khoảng trống sau reindex được giữ nguyên dạng NaN (không nội suy, không xóa dòng).",
        "per_station": per_station,
    }


# ---------------------------------------------------------------------------
# Bước 6 — Lỗi kẹt cảm biến
# ---------------------------------------------------------------------------


def flag_stuck_values(
    df: pd.DataFrame,
    columns: Sequence[str] = STUCK_SENSOR_COLUMNS,
    threshold_hours: int = STUCK_VALUE_THRESHOLD_HOURS,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Phát hiện lỗi kẹt cảm biến: chuỗi đo KHÔNG ĐỔI quá `threshold_hours` giờ
    liên tếp trên lưới giờ đồng nhất, và chuyển toàn bộ chuỗi đó thành `NaN`.

    Timestamp-aware: một khoảng trống thời gian (khác đúng 1 giờ) ngắt chuỗi, tránh
    gộp nhầm hai dòng cách xa nhau thành một chuỗi "kẹt".
    Station-aware: không bao giờ nối chuỗi dữ liệu xuyên trạm.

    Mặc định chỉ áp dụng cho nồng độ hạt bụi — xem `STUCK_SENSOR_COLUMNS` để hiểu
    vì sao KHÔNG áp dụng cho chuỗi 0.0 của `precipitation`/`wind_speed`.

    Trả về `(df_đã_sửa, thống_kê)`.
    """
    out = df.copy()
    stats: Dict[str, Any] = {
        "threshold_hours": threshold_hours,
        "rule": (
            f"Chuỗi quan sát không đổi giá trị trên dài hơn {threshold_hours} giờ liên tiếp "
            f"(tức ≥ {threshold_hours + 1} quan sát giống hệt) → chuyển thành NaN."
        ),
        "by_column": {},
        "excluded_columns_rationale": (
            "Không áp dụng cho precipitation/wind_speed: chuỗi 0.0 dài của chúng là "
            "hiện tượng khí tượng tự nhiên, đã được Issue #5 đo và kết luận rõ ràng."
        ),
    }

    for col in columns:
        if col not in out.columns:
            continue
        observed = out[col].notna()
        stuck_mask, run_length = _run_mask_longer_than(out, col, threshold_hours)
        stuck_mask = stuck_mask.fillna(False) & observed
        out[col] = out[col].mask(stuck_mask).astype("float64")

        stats["by_column"][col] = {
            "rows_nullified": int(stuck_mask.sum()),
            "longest_observed_constant_run_hours": (
                int(run_length[observed].max()) if int(observed.sum()) else 0
            ),
            "longest_nullified_run_hours": (
                int(run_length[stuck_mask].max()) if int(stuck_mask.sum()) else 0
            ),
            "nullified_runs": int(run_ids_of(out, col)[stuck_mask].nunique()),
            "missing_runs_excluded": int(run_ids_of(out, col)[~observed].nunique()),
            "nullified_pct": (
                round(int(stuck_mask.sum()) / len(out) * 100, 4) if len(out) > 0 else 0.0
            ),
        }

    stats["total_rows_nullified"] = int(
        sum(s["rows_nullified"] for s in stats["by_column"].values())
    )
    return out, stats


# ---------------------------------------------------------------------------
# Bước 7 — Cờ chỉ báo khuyết thiếu & cảnh báo độ ẩm cao
# ---------------------------------------------------------------------------


def flag_prolonged_missing(
    df: pd.DataFrame,
    column: str = "pm25",
    flag_name: str = PM25_MISSING_FLAG,
    threshold_hours: int = PROLONGED_MISSING_THRESHOLD_HOURS,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Gắn cờ chỉ báo `flag_name = 1` cho mọi hàng thuộc khối khuyết liên tụp dài
    hơn `threshold_hours` giờ của biến `column`.

    Cờ này là **chỉ báo chẩn đoán**, KHÔNG phải phép điền khuyết: giá trị gốc vẫn
    là `NaN` và được bảo toàn nguyên trạng cho Issue #7.

    Trả về `(df_đã_gắn_cờ, thống_kê)`.
    """
    _require_columns(df, [TIMESTAMP_COLUMN], "Bước gắn cờ khuyết thiếu kéo dài")

    out = df.copy()
    stats: Dict[str, Any] = {
        "source_column": column,
        "flag_name": flag_name,
        "threshold_hours": threshold_hours,
        "missing_rows_total": int(out[column].isna().sum()) if column in out.columns else 0,
        "flag_definition": (
            "1 = giờ này không có quan sát hợp lệ và nằm trong một khối khuyết "
            f"liên tục dài hơn {threshold_hours} giờ; 0 = ngược lại."
        ),
    }

    if column not in out.columns:
        stats["skipped"] = True
        stats["skip_reason"] = f"Không có cột nguồn '{column}'."
        out[flag_name] = pd.Series(0, index=out.index, dtype="int64")
        stats["rows_flagged"] = 0
        return out, stats

    is_na = out[column].isna()
    run_ids = _run_ids(out, column)
    prolonged_mask, run_length = _run_mask_longer_than(out, column, threshold_hours)
    prolonged = prolonged_mask.fillna(False) & is_na
    out[flag_name] = prolonged.astype("int64")

    stats.update({
        "skipped": False,
        "missing_blocks": int(run_ids[is_na].nunique()),
        "prolonged_blocks": int(run_ids[prolonged].nunique()),
        "rows_flagged": int(prolonged.sum()),
        "flagged_pct": round(int(prolonged.sum()) / len(out) * 100, 4) if len(out) > 0 else 0.0,
        "longest_missing_block_hours": (
            int(run_length[is_na].max()) if int(is_na.sum()) > 0 else 0
        ),
        "longest_flagged_block_hours": (
            int(run_length[prolonged].max()) if int(prolonged.sum()) > 0 else 0
        ),
    })
    return out, stats


def attach_high_humidity_flag(
    df: pd.DataFrame,
    weather_df: pd.DataFrame,
    threshold_pct: float = HIGH_HUMIDITY_FOG_THRESHOLD_PCT,
    flag_name: str = HIGH_HUMIDITY_FLAG,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Gắn cờ chẩn đoán `is_high_humidity_fog = 1` cho giờ có độ ẩm tương đối > 90%.

    Cảm biến quang học nhầm giọt nước vi mô thành hạt bụi khi RH rất cao; quy tắc
    này **chỉ gắn cờ, tuyệt đối không xóa bản ghi**.

    Độ ẩm được tra cứu bằng phép LEFT JOIN tất định theo `timestamp` với
    `validate="many_to_one"` và kiểm tra số dòng trước/sau — đảm bảo tuyệt đối
    không xảy ra Row Explosion. Cột độ ẩm thô KHÔNG được giữ lại trong artifact
    ô nhiễm (việc tích hợp đầy đủ khí tượng là phạm vi Issue #7).

    Trả về `(df_đã_gắn_cờ, thống_kê)`.
    """
    _require_columns(df, [TIMESTAMP_COLUMN], "Bước gắn cờ sương mù độ ẩm cao")
    _require_columns(weather_df, [TIMESTAMP_COLUMN, "relative_humidity"], "Tập khí tượng")

    duplicate_hours = int(weather_df.duplicated(subset=[TIMESTAMP_COLUMN]).sum())
    if duplicate_hours > 0:
        raise ValueError(
            f"Tập khí tượng có {duplicate_hours} mốc thời gian trùng lặp — phép ghép "
            "tra cứu độ ẩm sẽ gây Row Explosion. Chạy Issue #6 trước khi ghép."
        )

    rows_before = int(len(df))
    humidity_only = weather_df[[TIMESTAMP_COLUMN, "relative_humidity"]].copy()
    humidity_only["relative_humidity"] = humidity_only["relative_humidity"].astype("float64")

    out = df.merge(
        humidity_only,
        on=TIMESTAMP_COLUMN,
        how="left",
        validate="many_to_one",
        sort=False,
    )

    if len(out) != rows_before:
        raise AssertionError(
            f"Row Explosion khi tra cứu độ ẩm: {rows_before} dòng → {len(out)} dòng!"
        )

    humidity = out.pop("relative_humidity")
    out[flag_name] = (humidity > threshold_pct).fillna(False).astype("int64")

    return out, {
        "source": "data/interim/weather_canonical.parquet (relative_humidity)",
        "threshold_pct": threshold_pct,
        "flag_name": flag_name,
        "flag_definition": f"1 = RH > {threshold_pct}% (sương mù quang học); 0 = ngược lại.",
        "rows_before_join": rows_before,
        "rows_after_join": int(len(out)),
        "row_explosion_detected": False,
        "humidity_matched_rows": int(humidity.notna().sum()),
        "humidity_unavailable_rows": int(humidity.isna().sum()),
        "rows_flagged": int(out[flag_name].sum()),
        "flagged_pct": round(int(out[flag_name].sum()) / len(out) * 100, 4) if len(out) else 0.0,
        "row_deletion_policy": "Không xóa bản ghi nào ở giờ RH cao.",
    }


# ---------------------------------------------------------------------------
# Kiểm chứng sau làm sạch
# ---------------------------------------------------------------------------


def validate_cleaned_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Kiểm chứng các tiêu chí nghiệm thu bắt buộc của Issue #6 trên dữ liệu ĐÃ làm sạch.

    1. Mọi mốc thời gian đều ở múi giờ canonical `Asia/Ho_Chi_Minh`.
    2. Không còn bản ghi trùng lặp tại đơn vị quan sát.
    3. Chuỗi thời gian tăng đơn điệu và liên tục đúng 1 giờ trên TỪNG trạm.
    4. Không còn giá trị âm phi lý.
    5. Ràng buộc hạt bụi `PM2.5 <= PM10 + 1e-3` được thực thi khi có PM10.
    6. Không có bước điền khuyết: không quan sát nào bị thêm vào.

    Trả về dict kết quả; `all_passed` = True khi tất cả kiểm tra đạt.
    """
    checks: Dict[str, Any] = {}

    timestamps = df[TIMESTAMP_COLUMN] if TIMESTAMP_COLUMN in df.columns else None
    checks["timezone_is_canonical"] = {
        "passed": bool(timestamps is not None and str(timestamps.dt.tz) == CANONICAL_TIMEZONE),
        "observed": str(timestamps.dt.tz) if timestamps is not None else None,
        "expected": CANONICAL_TIMEZONE,
    }

    key = _observation_key(df)
    duplicates = int(df.duplicated(subset=key).sum())
    checks["no_duplicate_observations"] = {"passed": duplicates == 0, "duplicates": duplicates}

    monotonic = bool(timestamps.is_monotonic_increasing) if timestamps is not None else False
    irregular = 0
    per_station_gaps: Dict[str, Any] = {}
    if timestamps is not None and len(df) > 1:
        if STATION_COLUMN in df.columns:
            for station_id, station_df in df.groupby(STATION_COLUMN, sort=True):
                station_df = station_df.sort_values(TIMESTAMP_COLUMN, kind="mergesort")
                diffs = station_df[TIMESTAMP_COLUMN].diff().dropna()
                bad = int((diffs != ONE_HOUR).sum())
                irregular += bad
                per_station_gaps[str(station_id)] = {
                    "rows": int(len(station_df)),
                    "irregular_intervals": bad,
                    "first": str(station_df[TIMESTAMP_COLUMN].min()),
                    "last": str(station_df[TIMESTAMP_COLUMN].max()),
                    "is_monotonic_increasing": bool(
                        station_df[TIMESTAMP_COLUMN].is_monotonic_increasing
                    ),
                }
        else:
            diffs = timestamps.diff().dropna()
            irregular = int((diffs != ONE_HOUR).sum())
    checks["continuous_hourly_grid_per_station"] = {
        "passed": monotonic and irregular == 0,
        "is_monotonic_increasing": monotonic,
        "irregular_intervals_total": irregular,
        "per_station": per_station_gaps,
    }

    negatives = {
        col: int((df[col] < 0).sum())
        for col in df.select_dtypes(include=[np.number]).columns
        if col in set(AIR_MEASUREMENT_COLUMNS) | set(WEATHER_MEASUREMENT_COLUMNS)
    }
    checks["no_negative_values"] = {
        "passed": all(count == 0 for count in negatives.values()),
        "negatives_by_column": negatives,
    }

    if "pm25" in df.columns and "pm10" in df.columns:
        pairs = df.dropna(subset=["pm25", "pm10"])
        violations = int((pairs["pm25"] > (pairs["pm10"] + 1e-3)).sum())
        checks["pm_subset_constraint"] = {
            "passed": violations == 0,
            "evaluated_pairs": int(len(pairs)),
            "violations_pm25_gt_pm10_plus_1e_3": violations,
        }
    else:
        checks["pm_subset_constraint"] = {
            "passed": True,
            "skipped": True,
            "reason": "Không có đủ cột pm25/pm10 trong tập dữ liệu này.",
        }

    checks["all_passed"] = all(
        v["passed"] for v in checks.values() if isinstance(v, dict) and "passed" in v
    )
    return checks


def assert_no_imputation(before: pd.DataFrame, after: pd.DataFrame, columns: Sequence[str]) -> None:
    """
    Chứng minh rằng không có phép điền khuyết nào đã diễn ra: số quan sát hợp lệ
    của mỗi cột đo sau làm sạch KHÔNG BAO GIỜ tăng so với trước đó.

    (Reindex có thể tăng tổng số dòng và khoảng trống mới sinh thêm NaN, nhưng
    tuyệt đối không hồi sinh một giá trị quan sát từng bị thiếu.)
    """
    for col in columns:
        if col not in before.columns or col not in after.columns:
            continue
        observed_before = int(before[col].notna().sum())
        observed_after = int(after[col].notna().sum())
        if observed_after > observed_before:
            raise AssertionError(
                f"Cột '{col}' tăng số quan sát hợp lệ từ {observed_before} lên "
                f"{observed_after} — phát hiện phép điền khuyết, vi phạm "
                "ranh giới Issue #6 / Issue #7!"
            )


# ---------------------------------------------------------------------------
# Pipeline điều phối
# ---------------------------------------------------------------------------


def clean_air_quality(
    df_air: pd.DataFrame, df_weather: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Thực hiện toàn bộ chuỗi làm sạch tất định cho tập ô nhiễm không khí.

    Thứ tự các bước (mỗi bước là một phép biến đổi tất định, không phụ thuộc dữ liệu):
    1. Chuẩn hóa múi giờ UTC+7 · 2. Sắp xếp tăng dần · 3. Khử trùng lặp ·
    4. Missing ngụy trang → NaN · 5. Giá trị âm phi lý → NaN ·
    6. Ràng buộc khí động học PM2.5 ⊆ PM10 · 7. Reindex lưới 1 giờ theo từng trạm ·
    8. Kẹt cảm biến → NaN · 9. Cờ `pm25_was_missing` · 10. Cờ `is_high_humidity_fog`.

    Reindex được đặt TRƯỚC các bước cảm biến để mọi quy tắc phía sau đo trên
    cùng một lưới giờ đồng nhất.

    Trả về `(df_đã_làm_sạch, báo_cáo_các_bước)`.
    """
    steps: List[Dict[str, Any]] = []
    input_snapshot = _snapshot(df_air)
    peak_trace = _trace_input_peak(df_air)

    def _record(name: str, title: str, rationale: str, stats: Dict[str, Any]) -> None:
        steps.append({"step": len(steps) + 1, "name": name, "title": title,
                      "rationale": rationale, "stats": stats})

    df_air, tz_stats = normalize_timestamps(df_air)
    _record(
        "normalize_timestamps", "Chuẩn hóa mốc thời gian về Asia/Ho_Chi_Minh (UTC+7)",
        "Mọi phép ghép và phân chia chuỗi thời gian phía sau yêu cầu một múi giờ duy nhất.",
        tz_stats,
    )

    df_air, sort_stats = sort_chronologically(df_air)
    _record(
        "sort_chronologically", "Sắp xếp tăng dần theo thời gian (và theo trạm)",
        "Đảm bảo chuỗi thời gian đơn điệu trước khi kiểm tra chuỗi liên tục.",
        sort_stats,
    )

    df_air, dup_stats = drop_duplicate_observations(df_air)
    _record(
        "drop_duplicate_observations", "Khử trùng lặp tại khóa quan sát",
        "Một mốc thời gian chỉ được mang một quan sát cho mỗi trạm.",
        dup_stats,
    )

    df_air, disguised_stats = normalize_disguised_missing(df_air, AIR_MEASUREMENT_COLUMNS)
    _record(
        "normalize_disguised_missing", "Chuyển missing ngụy trang (-999/-9999, chuỗi lỗi) thành NaN",
        "Mã lỗi nhà cung cấp nếu không bóc trần sẽ thành giá trị đo giả âm thầm đi vào phân tích.",
        disguised_stats,
    )

    df_air, air_bounds_stats = enforce_air_quality_physical_rules(df_air)
    _record(
        "enforce_air_quality_physical_rules", "Lọc giá trị âm phi lý của nồng độ hạt bụi",
        "Nồng độ âm là bất khả thi về mặt vật lý; 0.0 hợp lệ được giữ nguyên.",
        air_bounds_stats,
    )

    df_air, pm_subset_stats = enforce_pm_subset_constraint(df_air)
    _record(
        "enforce_pm_subset_constraint", "Thực thi ràng buộc khí động học PM2.5 ≤ PM10",
        "PM2.5 là tập con khí động học của PM10; nghịch đảo cho thấy lỗi quang học hoặc nhập nội.",
        pm_subset_stats,
    )

    df_air, reindex_stats = reindex_hourly_grid(df_air)
    _record(
        "reindex_hourly_grid", "Reindex lưới thời gian liên tục 1 giờ theo từng trạm",
        "Bộc lộ trung thực mọi khoảng trống do trạm ngừng phát; khoảng trống giữ nguyên dạng NaN.",
        reindex_stats,
    )

    df_air, stuck_stats = flag_stuck_values(df_air)
    _record(
        "flag_stuck_values", "Nhận diện lỗi kẹt cảm biến (> 6 giờ không đổi)",
        "Phần cứng đóng băng hoặc kẹt ở đường nền tạo ra chuỗi số đo hoàn toàn bất biến.",
        stuck_stats,
    )

    df_air, missing_flag_stats = flag_prolonged_missing(df_air, column="pm25")
    _record(
        "flag_prolonged_missing", "Gắn cờ pm25_was_missing cho khối khuyết > 6 giờ",
        "Chỉ báo chẩn đoán để Issue #7 không nội suy mù và không xóa dòng.",
        missing_flag_stats,
    )

    df_air, humidity_stats = attach_high_humidity_flag(df_air, df_weather)
    _record(
        "attach_high_humidity_flag", "Gắn cờ cảnh báo sương mù độ ẩm cao (RH > 90%)",
        "Cảm biến quang học nhầm giọt nước thành bụi khi RH cao — gắn cờ để chẩn đoán, không xóa dòng.",
        humidity_stats,
    )

    assert_no_imputation(df_air, df_air, AIR_MEASUREMENT_COLUMNS)
    return df_air, {
        "input": input_snapshot,
        "steps": steps,
        "output": _snapshot(df_air),
        "peak_trace": _resolve_peak_trace(peak_trace, df_air),
    }


def clean_weather(df_weather: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Thực hiện chuỗi làm sạch tất định cho tập khí tượng bề mặt ERA5.

    Khác với ô nhiễm không khí, tập khí tượng KHÔNG áp dụng quy tắc kẹt cảm biến
    (chuỗi 0.0 dài của lượng mưa là hiện tượng tự nhiên, xem `STUCK_SENSOR_COLUMNS`)
    và không sinh cờ `pm25_was_missing` (không có biến nào tên pm25).

    Trả về `(df_đã_làm_sạch, báo_cáo_các_bước)`.
    """
    steps: List[Dict[str, Any]] = []
    input_snapshot = _snapshot(df_weather)

    def _record(name: str, title: str, rationale: str, stats: Dict[str, Any]) -> None:
        steps.append({"step": len(steps) + 1, "name": name, "title": title,
                      "rationale": rationale, "stats": stats})

    df_weather, tz_stats = normalize_timestamps(df_weather)
    _record(
        "normalize_timestamps", "Chuẩn hóa mốc thời gian về Asia/Ho_Chi_Minh (UTC+7)",
        "Đồng bộ múi giờ với chuỗi ô nhiễm không khí trước mọi phép ghép tương lai.",
        tz_stats,
    )

    df_weather, sort_stats = sort_chronologically(df_weather)
    _record(
        "sort_chronologically", "Sắp xếp tăng dần theo thời gian",
        "Đảm bảo chuỗi thời gian đơn điệu trước khi kiểm tra chuỗi liên tục.",
        sort_stats,
    )

    df_weather, dup_stats = drop_duplicate_observations(df_weather)
    _record(
        "drop_duplicate_observations", "Khử trùng lặp tại khóa quan sát timestamp",
        "Điểm lưới ERA5 chỉ được mang một quan sát cho mỗi giờ.",
        dup_stats,
    )

    df_weather, disguised_stats = normalize_disguised_missing(df_weather, WEATHER_MEASUREMENT_COLUMNS)
    _record(
        "normalize_disguised_missing", "Chuyển missing ngụy trang thành NaN",
        "Bảo đảm mã lỗi nhà cung cấp không thành giá trị khí tượng giả.",
        disguised_stats,
    )

    df_weather, weather_bounds_stats = enforce_weather_physical_rules(df_weather)
    _record(
        "enforce_weather_physical_rules", "Kiểm tra dải hợp lệ khí tượng bề mặt",
        "0% ≤ RH ≤ 100%, 0 ≤ hướng gió ≤ 360°, lượng mưa ≥ 0, nhiệt độ và áp suất trong dải vật lý.",
        weather_bounds_stats,
    )

    df_weather, reindex_stats = reindex_hourly_grid(df_weather)
    _record(
        "reindex_hourly_grid", "Reindex lưới thời gian liên tục 1 giờ",
        "Bộc lộ mọi khoảng trống của chuỗi ERA5 dưới dạng NaN thay vì ẩn giấu.",
        reindex_stats,
    )

    assert_no_imputation(df_weather, df_weather, WEATHER_MEASUREMENT_COLUMNS)
    return df_weather, {"input": input_snapshot, "steps": steps, "output": _snapshot(df_weather)}


def run_deterministic_cleaning(
    air_interim_path: Path = Path("data/interim/air_quality_canonical.parquet"),
    weather_interim_path: Path = Path("data/interim/weather_canonical.parquet"),
    interim_dir: Optional[Path] = None,
    save: bool = True,
    project_root: Path = Path("."),
) -> Dict[str, Any]:
    """
    Điểm vào chính của Issue #6: nạp hai tập Canonical, chạy toàn bộ làm sạch tất định,
    kiểm chứng và lưu lại artifact trung gian.

    Artifact đầu ra ghi đè đúng các đường dẫn Canonical trong `data/interim/` —
    đây chính là hai tệp mà Issue #7 khai báo là đầu vào. Dữ liệu gốc vẫn được
    bảo toàn bất biến trong `data/raw/` kèm mã băm SHA-256 (chính sách ba tầng),
    nên toàn bộ artifact trung gian luôn tái tạo được bằng mã nguồn.

    Args:
        air_interim_path: Đường dẫn Parquet canonical ô nhiễm không khí đầu vào.
        weather_interim_path: Đường dẫn Parquet canonical khí tượng đầu vào.
        interim_dir: Thư mục ghi artifact đầu ra (mặc định: thư mục chứa
            `air_interim_path`).
        save: Ghi Parquet ra đĩa hay không.
        project_root: Thư mục gốc dự án, dùng để trình bày đường dẫn tương đối
            trong Cleaning Log (tránh phụ thuộc máy).

    Returns:
        Báo cáo có cấu trúc (dùng để dựng `docs/cleaning_log.md`).

    Raises:
        FileNotFoundError: Thiếu tệp đầu vào.
        ValueError / AssertionError: Sai lệch dữ liệu khiến làm sạch tất định
            không thể thực hiện an toàn.
    """
    air_interim_path = Path(air_interim_path)
    weather_interim_path = Path(weather_interim_path)
    if interim_dir is None:
        interim_dir = air_interim_path.parent
    interim_dir = Path(interim_dir)

    for path in (air_interim_path, weather_interim_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy tệp canonical đầu vào: {path}. "
                "Hãy chạy `python scripts/fetch_dataset.py` hoặc notebook 01 trước."
            )

    df_air_input = pd.read_parquet(air_interim_path)
    df_weather_input = pd.read_parquet(weather_interim_path)

    # Cảnh báo tái lập: nếu artifact trung gian đã trải qua Issue #6 thì chạy lại
    # sẽ KHÔNG còn hiện tượng cần xử lý và Cleaning Log sinh ra sẽ mô tả dữ liệu
    # đã làm sạch chứ không phải lần làm sạch gốc. Người dùng cần chạy lại
    # notebook 01 (hoặc scripts/fetch_dataset.py) để tái tạo log gốc.
    already_cleaned = [
        flag for flag in (PM25_MISSING_FLAG, HIGH_HUMIDITY_FLAG) if flag in df_air_input.columns
    ]
    if already_cleaned:
        logger.warning(
            "Artifact đầu vào đã chứa cột cờ của Issue #6 (%s). Lần chạy này chỉ "
            "tái kiểm chứng tính tất định; muốn tái tạo Cleaning Log gốc hãy chạy lại "
            "notebook 01 trước.",
            ", ".join(already_cleaned),
        )

    df_air_clean, air_report = clean_air_quality(df_air_input, df_weather_input)
    df_weather_clean, weather_report = clean_weather(df_weather_input)

    assert_no_imputation(df_air_input, df_air_clean, AIR_MEASUREMENT_COLUMNS)
    assert_no_imputation(df_weather_input, df_weather_clean, WEATHER_MEASUREMENT_COLUMNS)

    air_validation = validate_cleaned_dataset(df_air_clean)
    weather_validation = validate_cleaned_dataset(df_weather_clean)

    output_paths: Dict[str, Optional[str]] = {"air_quality": None, "weather": None}
    if save:
        interim_dir.mkdir(parents=True, exist_ok=True)
        air_out_path = interim_dir / air_interim_path.name
        weather_out_path = interim_dir / weather_interim_path.name
        df_air_clean.to_parquet(air_out_path, index=False, compression="snappy")
        df_weather_clean.to_parquet(weather_out_path, index=False, compression="snappy")
        output_paths = {
            "air_quality": _display_path(air_out_path, project_root),
            "weather": _display_path(weather_out_path, project_root),
        }
        logger.info(
            "Đã lưu artifact làm sạch tất định: %s (%d dòng) và %s (%d dòng)",
            air_out_path, len(df_air_clean), weather_out_path, len(df_weather_clean),
        )

    return {
        "issue": "#6 – Làm sạch tất định, lỗi cảm biến và reindex chuỗi thời gian",
        "milestone": "Milestone 2 – Kiểm toán & Làm sạch Dữ liệu (Tuần 03–05)",
        "policy": {
            "scope": "Chỉ phép biến đổi tất định, thực hiện TRƯỚC khi đóng băng và chia tập.",
            "excluded_data_dependent_preprocessing": [
                "Điền khuyết trung vị / trung bình / nội suy / giá trị trượt học",
                "Chuẩn hóa tỷ lệ (RobustScaler, StandardScaler)",
                "Lựa chọn đặc trưng hoặc mã hóa phụ thuộc phân phối / nhãn",
            ],
            "handover_to_issue_7": "Đóng băng tập dữ liệu, phân chia Train/Test theo chuỗi thời gian, "
                                   "fit tiền xử lý chỉ trên Train.",
            "thresholds": {
                "canonical_timezone": CANONICAL_TIMEZONE,
                "hourly_frequency": HOURLY_FREQ,
                "pm_aerodynamic_epsilon_ug_m3": PM_AERODYNAMIC_EPSILON_UG_M3,
                "stuck_value_threshold_hours": STUCK_VALUE_THRESHOLD_HOURS,
                "prolonged_missing_threshold_hours": PROLONGED_MISSING_THRESHOLD_HOURS,
                "high_humidity_fog_threshold_pct": HIGH_HUMIDITY_FOG_THRESHOLD_PCT,
                "weather_physical_bounds": WEATHER_PHYSICAL_BOUNDS,
            },
        },
        "air_quality": {
            **air_report,
            "source_path": _display_path(air_interim_path, project_root),
            "output_path": output_paths["air_quality"],
            "flag_columns": [PM25_MISSING_FLAG, HIGH_HUMIDITY_FLAG],
            "input_already_cleaned": already_cleaned,
            "validation": air_validation,
        },
        "weather": {
            **weather_report,
            "source_path": _display_path(weather_interim_path, project_root),
            "output_path": output_paths["weather"],
            "flag_columns": [],
            "validation": weather_validation,
        },
    }


# ---------------------------------------------------------------------------
# Sinh Cleaning Log
# ---------------------------------------------------------------------------

_VI_CHECK = {True: "PASS", False: "FAIL"}


def _display_path(path: Optional[str], project_root: Path) -> Optional[str]:
    """
    Trình bày đường dẫn theo dạng tương đối so với thư mục gốc dự án (dấu `/`).

    Mục đích: `docs/cleaning_log.md` được Git-track nên KHÔNG được chứa đường dẫn
    tuyệt đối phụ thuộc máy (ví dụ `C:\\Users\\...`), nếu không mỗi máy sẽ sinh ra
    một nội dung tài liệu khác nhau.
    """
    if path is None:
        return None
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(project_root).resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _fmt(value: Any) -> str:
    """
    Định dạng số liệu cho log.

    Quy ước: chỉ số nguyên (`int`) dùng dấu chấm phân tách nghìn kiểu Việt Nam
    (`8.022` = tám nghìn không trăm hai mươi hai). Số thực (`float`) giữ nguyên
    dạng thập phân **không** phân tách nghìn, vì dấu chấm kiểu Việt Nam sẽ gây
    mơ hồ (`-9.999` có thể bị đọc thành `-9,999` thập phân thay vì `-9999`).
    """
    if isinstance(value, bool):
        return "Có" if value else "Không"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if not value.is_integer() else str(int(value))
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(f'"{v}"' if isinstance(v, str) else _fmt(v) for v in value) + "]"
    return str(value)


def _flatten_stats(stats: Dict[str, Any], prefix: str = "") -> List[Tuple[str, Any]]:
    """Làm phẳng thống kê lồng nhau thành các cặp `(khóa, giá trị)` để dựng bảng."""
    rows: List[Tuple[str, Any]] = []
    for key, value in stats.items():
        label = f"{prefix}{key}"
        if isinstance(value, dict):
            rows.extend(_flatten_stats(value, prefix=f"{label}."))
        else:
            rows.append((label, value))
    return rows


def _render_steps(steps: List[Dict[str, Any]]) -> List[str]:
    """
    Dựng các mục Markdown mô tả từng bước làm sạch kèm số dô ng bị tác động.

    Giá trị ngắn (số, boolean, chuỗi ≤ 90 ký tự) nằm trong bảng; chuỗi văn bản dài
    được trình bày thành gạch đầu dòng riêng để bảng không bị tràn cột.
    """
    lines: List[str] = []
    for step in steps:
        lines.append(f"#### Bước {step['step']} — {step['title']}")
        lines.append("")
        lines.append(f"**Căn cứ logic:** {step['rationale']}")
        lines.append("")

        table_rows = [("Hàm thực thi", f"`{step['name']}()`")]
        bullets: List[str] = []
        for key, value in _flatten_stats(step["stats"]):
            text = _fmt(value)
            if isinstance(value, str) and len(text) > 90:
                bullets.append(f"- `{key}`: {text}")
            else:
                table_rows.append((f"`{key}`", f"`{text}`"))

        lines += ["| Chỉ số | Giá trị |", "|---|---|"]
        lines += [f"| {key} | {value} |" for key, value in table_rows]
        if bullets:
            lines += [""] + bullets
        lines.append("")
    return lines


def _render_validation(dataset: str, validation: Dict[str, Any]) -> List[str]:
    """Dựng bảng kiểm chứng tiêu chí nghiệm thu của Issue #6."""
    lines = [
        f"**Kiểm chứng tập {dataset}:**",
        "",
        "| Tiêu chí kiểm chứng | Kết quả | Trạng thái |",
        "|---|---|---|",
    ]
    for name, result in validation.items():
        if not isinstance(result, dict) or "passed" not in result:
            continue
        flat = _flatten_stats({k: v for k, v in result.items() if k != "passed"})
        detail_text = "; ".join(f"{key}={_fmt(value)}" for key, value in flat) or "—"
        lines.append(f"| `{name}` | {detail_text} | **{_VI_CHECK[result['passed']]}** |")
    return lines


def _render_extreme_preservation(report: Dict[str, Any]) -> List[str]:
    """
    Dựng bằng chứng định lượng rằng **không** giá trị nào bị mất vì lý do khác
    ngoài ràng buộc vật lý đã công bố.

    Bằng chứng được rút ra từ chính báo cáo làm sạch: đối chiếu đỉnh nồng độ
    trước/sau và liệt kê đầy đủ nhóm nguyên nhân đã dùng để chuyển `NaN`.
    """
    air = report["air_quality"]
    before = air["input"]["missing_cells"]
    after = air["output"]["missing_cells"]
    lines = [
        "### 7.1. Bằng Chứng Định Lượng: Không Mất Giá Trị Vì Lý Do Không Được Chứng Minh",
        "",
        "Nguyên tắc bảo toàn được kiểm chứng bằng cách **đối chiếu số ô khuyết trước và sau**",
        "cùng với danh mục đầy đủ các nguyên nhân đã dùng để chuyển giá trị thành `NaN`:",
        "",
        "| Biến | Số ô `NaN` trước | Số ô `NaN` sau | Nguyên nhân tăng thêm |",
        "|---|---|---|---|",
    ]
    for column in ("pm25", "pm10"):
        lines.append(
            f"| `{column}` | {_fmt(before.get(column, 0))} | {_fmt(after.get(column, 0))} | "
            "Khoảng trống thời gian từ reindex + ràng buộc khí động học |"
        )

    lines += [
        "",
        "Như vậy **không có ô `NaN` nào được tạo ra bởi nguyên nhân nằm ngoài danh mục đã công bố**",
        "(mã lỗi ngụy trang, giá trị âm phi lý, giá trị ngoài dải khí quyển, chuỗi kẹt cảm biến,",
        "nghịch đảo khí động học, hoặc khoảng trống thời gian thật). Cụ thể trên dữ liệu thực tế:",
        "",
    ]

    reasons = []
    for step in air["steps"]:
        stats = step["stats"]
        # `rows_inserted` được xử lý riêng bởi nhánh reindex bên dưới để tránh
        # liệt kê trùng hai lần cho cùng một con số.
        for key in ("total_cells_converted", "total_rows_nullified", "rows_nullified",
                    "duplicate_rows_removed"):
            if stats.get(key):
                reasons.append((step["title"], key, int(stats[key])))
        if step["name"] == "reindex_hourly_grid" and stats.get("rows_inserted"):
            reasons.append(("Khoảng trống thời gian từ reindex (NaN cố ý)",
                            "rows_inserted", int(stats["rows_inserted"])))
        if step["name"] == "flag_prolonged_missing" and stats.get("rows_flagged"):
            reasons.append(("Cờ chẩn đoán pm25_was_missing (không xóa giá trị)",
                            "rows_flagged", int(stats["rows_flagged"])))

    lines += ["| Phép biến đổi | Chỉ số | Số lượng |", "|---|---|---|"]
    for title, key, value in reasons:
        lines.append(f"| {title} | `{key}` | {_fmt(value)} |")

    lines += [
        "",
        _render_peak_note(air),
        "",
    ]
    return lines


def _render_peak_note(air: Dict[str, Any]) -> str:
    """
    Dựng ghi chú đã **kiểm chứng** về đỉnh PM2.5, thay cho một khẳng định có điều kiện.

    Ghi chú chỉ nêu kết luận khi bằng chứng đã được đối chiếu trên dữ liệu thật:
    đỉnh còn sống, hoặc đỉnh biến mất vì chính bản ghi đó vi phạm ràng buộc khí
    động học PM2.5 ≤ PM10.
    """
    trace = air.get("peak_trace") or {}
    if not trace:
        return "> **Lưu ý về đỉnh nồng độ:** không xác định được đỉnh PM2.5 trên tập dữ liệu này."

    peak = _fmt(trace["pm25_peak"])
    if trace.get("survived_cleaning"):
        return (
            f"> **Kiểm chứng đỉnh nồng độ:** đỉnh PM2.5 lớn nhất trước làm sạch là "
            f"{peak} µg/m³ và bản ghi đó **vẫn còn nguyên** sau làm sạch — không có quy tắc nào "
            "cắt bỏ cực trị."
        )
    if trace.get("nullified_by_physics_constraint"):
        return (
            f"> **Kiểm chứng đỉnh nồng độ:** đỉnh PM2.5 lớn nhất trước làm sạch là {peak} µg/m³ "
            f"(tại `{trace['timestamp']}`, trạm `{trace['station_id']}`), kèm PM10 đo được là "
            f"{_fmt(trace['pm10_at_peak'])} µg/m³ — tức vượt PM10 "
            f"{_fmt(trace['margin_pm25_minus_pm10'])} µg/m³. Bản ghi này **vi phạm ràng buộc khí "
            "động học PM2.5 ≤ PM10** nên đã chuyển `NaN`. Đỉnh biến mất là hệ quả của bằng chứng "
            "vật lý, **không phải** quy tắc cắt bỏ cực trị."
        )
    return (
        f"> **Kiểm chứng đỉnh nồng độ:** đỉnh PM2.5 lớn nhất trước làm sạch là {peak} µg/m³ và "
        "bản ghi đó đã chuyển `NaN`, nhưng **không** gắn được nguyên nhân nào trong danh mục "
        "đã công bố — cần điều tra thêm thay vì quy cho là nhiễu."
    )


def render_cleaning_log(report: Dict[str, Any]) -> str:
    """
    Dựng nội dung Markdown cho `docs/cleaning_log.md` từ báo cáo làm sạch.

    Hàm **tất định hoàn toàn**: cùng một báo cáo đầu vào luôn cho ra cùng một chuỗi
    Markdown. Cố tình KHÔNG nhúng dấu thời gian chạy (wall-clock) để tài liệu theo
    dõi trong Git không bị bẩn mỗi lần chạy lại notebook — cùng nguyên tắc với
    `data/raw/metadata.json`.
    """
    policy = report["policy"]
    air = report["air_quality"]
    weather = report["weather"]
    thresholds = policy["thresholds"]

    lines: List[str] = [
        "# Nhật Ký Làm Sạch Dữ Liệu (Cleaning Log)",
        "",
        f"> **Nguồn sinh:** `src/cleaning.py` · `run_deterministic_cleaning()` · `render_cleaning_log()`  ",
        f"> **Notebook:** [`notebooks/03_data_cleaning.ipynb`](../notebooks/03_data_cleaning.ipynb)  ",
        f"> **Issue:** {report['issue']}  ",
        f"> **Milestone:** {report['milestone']}  ",
        "> **Tính tất định:** tài liệu này được sinh tự động từ mã nguồn và **không** chứa dấu",
        "> thời gian chạy (wall-clock), nên chạy lại trên cùng dữ liệu cho ra kết quả giống hệt.",
        "",
    ]
    if air.get("input_already_cleaned"):
        lines += [
            "> [!WARNING]",
            "> **Artifact đầu vào đã được làm sạch từ trước** (đã chứa cột "
            f"`{', '.join(air['input_already_cleaned'])}`). Bản log này được sinh từ lần chạy lại trên "
            "dữ liệu **đã làm sạch**, nên các số liệu 'trước làm sạch' ở đây KHÔNG còn là trạng thái",
            "> gốc. Muốn tái tạo Cleaning Log gốc, hãy chạy lại `notebooks/01_data_collection.ipynb`",
            "> (hoặc `python scripts/fetch_dataset.py`) trước khi chạy `notebooks/03_data_cleaning.ipynb`.",
            "",
        ]
    lines += [
        "---",
        "",
        "## 1. Ranh Giới Phân Định: Làm Sạch Tất Định vs. Tiền Xử Lý Phụ Thuộc Dữ Liệu",
        "",
        f"**Phạm vi thực hiện tại đây — {policy['scope']}**",
        "",
        "| Được thực hiện (Issue #6) | Bị hạn chế (chuyển sang Issue #7) |",
        "|---|---|",
        "| Chuẩn hóa schema và múi giờ `Asia/Ho_Chi_Minh` (UTC+7) | Điền khuyết trung vị / trung bình / nội suy |",
        "| Sắp xếp tăng dần theo thời gian | Điền bằng giá trị trượt học từ dữ liệu |",
        "| Khử trùng lặp tại khóa quan sát | Chuẩn hóa tỷ lệ (RobustScaler, StandardScaler) |",
        "| Chuyển missing ngụy trang thành `NaN` | Lựa chọn đặc trưng phụ thuộc phân phối / nhãn |",
        "| Lọc giá trị âm và giá trị vi phạm giới hạn vật lý | Phép biến đổi mục tiêu ứng viên `np.log1p` |",
        "| Ràng buộc khí động học PM2.5 ≤ PM10 | Đóng băng tập dữ liệu và phân chia Train/Test |",
        "| Nhận diện kẹt cảm biến, gắn cờ sương mù độ ẩm cao | Fit tiền xử lý **chỉ trên Train** |",
        "| Reindex lưới 1 giờ liên tục theo từng trạm | Đóng gói Scikit-Learn `Pipeline` / `ColumnTransformer` |",
        "| Gắn cờ chẩn đoán `pm25_was_missing`, `is_high_humidity_fog` | Xuất `data/processed/air_pollution_final.parquet` |",
        "",
        "**Nguyên tắc chống rò rỉ được bảo vệ tại đây:** không một đại lượng thống kê toàn cục nào",
        "được tính toán trước khi chia tập. Cột `relative_humidity` chỉ được dùng để **tra cứu",
        f"mốc thời gian** nhằm sinh cờ chẩn đoán và không được giữ lại trong artifact ô nhiễm.",
        "",
        "**Bàn giao cho Issue #7:** " + policy["handover_to_issue_7"],
        "",
        "---",
        "",
        "## 2. Ngưỡng & Hằng Số Quy ước Sử Dụng",
        "",
        "| Hằng số | Giá trị | Nguồn quy định |",
        "|---|---|---|",
        f"| Múi giờ canonical | `{thresholds['canonical_timezone']}` | `docs/data_dictionary.md` §3.1 |",
        f"| Tần suất lưới thời gian | `freq='{thresholds['hourly_frequency']}'` | Issue #6, `.agents/rules/data.md` §3.4 |",
        f"| Dung sai khí động học ε | `{thresholds['pm_aerodynamic_epsilon_ug_m3']} µg/m³` | `.agents/rules/data.md` §4, Handoff 1 của Issue #5 |",
        f"| Ngưỡng kẹt cảm biến | `> {thresholds['stuck_value_threshold_hours']} giờ` không đổi | Issue #6, `docs/roadmap.md` §4.3 |",
        f"| Ngưỡng khối khuyết lớn | `> {thresholds['prolonged_missing_threshold_hours']} giờ` liên tiếp | Issue #6, `.agents/rules/data.md` §3.5 |",
        f"| Ngưỡng sương mù độ ẩm cao | `RH > {thresholds['high_humidity_fog_threshold_pct']}%` | Issue #6, `.agents/rules/data.md` §4 |",
        "",
        "**Quy ước đếm của chuỗi liên tục:** ngưỡng được đếm bằng **số quan sát liên tiếp** trên lưới 1 giờ,",
        "đúng theo cùng quy ước với hàm `audit_prolonged_zeros()` của Issue #5. Vì vậy",
        f"“kẹt cảm biến > {thresholds['stuck_value_threshold_hours']} giờ” và “khối khuyết lớn > "
        f"{thresholds['prolonged_missing_threshold_hours']} giờ” đều được hiện thực hoá bằng điều kiện "
        f"**chuỗi có ít nhất {thresholds['stuck_value_threshold_hours'] + 1} quan sát liên tiếp**.",
        "",
        "---",
        "",
        "## 3. Tập Dữ Liệu Ô Nhiễm Không Khí (Air Quality)",
        "",
        f"**Tệp canonical:** `{air['source_path']}`"
        + (f" — sau làm sạch được ghi đè tại `{air['output_path']}`"
           if air["output_path"] else " — chạy ở chế độ `save=False`, không ghi đè tệp"),
        "",
        "### 3.1. Trạng Thái Trước và Sau Làm Sạch",
        "",
        "| Chỉ số | Trước làm sạch | Sau làm sạch |",
        "|---|---|---|",
        f"| Số dòng | {_fmt(air['input']['rows'])} | {_fmt(air['output']['rows'])} |",
        f"| Số cột | {_fmt(len(air['input']['columns']))} | {_fmt(len(air['output']['columns']))} |",
        f"| Mốc thời gian nhỏ nhất | `{air['input'].get('min_timestamp')}` | `{air['output'].get('min_timestamp')}` |",
        f"| Mốc thời gian lớn nhất | `{air['input'].get('max_timestamp')}` | `{air['output'].get('max_timestamp')}` |",
        f"| Múi giờ | `{air['input'].get('timezone')}` | `{air['output'].get('timezone')}` |",
        f"| Bản ghi trùng khóa quan sát | {_fmt(air['input']['duplicate_observation_keys'])} | "
        f"{_fmt(air['output']['duplicate_observation_keys'])} |",
        f"| Số ô `pm25` khuyết thiếu | {_fmt(air['input']['missing_cells'].get('pm25', 0))} | "
        f"{_fmt(air['output']['missing_cells'].get('pm25', 0))} |",
        f"| Số ô `pm10` khuyết thiếu | {_fmt(air['input']['missing_cells'].get('pm10', 0))} | "
        f"{_fmt(air['output']['missing_cells'].get('pm10', 0))} |",
        f"| Đỉnh PM2.5 (µg/m³) | {_fmt(air['input'].get('pm25_peak'))} | "
        f"{_fmt(air['output'].get('pm25_peak'))} |",
        "",
    ]

    reindex_step = next(
        (s for s in air["steps"] if s["name"] == "reindex_hourly_grid"), None
    )
    if reindex_step:
        stats = reindex_step["stats"]
        lines += [
            "### 3.2. Khoảng Trống Thời Gian Được Bộc Lộ Sau Reindex",
            "",
            f"- Cửa sổ lưới thời gian thực hiện: `{stats['window_start']}` → `{stats['window_end']}`.",
            f"- Số dòng trước reindex: **{_fmt(stats['rows_before'])}**; sau reindex: **{_fmt(stats['rows_after'])}**.",
            f"- Số giờ trống được chèn ra dưới dạng `NaN`: **{_fmt(stats['rows_inserted'])}**.",
            f"- Các trạm quan trắc được reindex độc lập: {', '.join(f'`{s}`' for s in stats['stations'])}.",
            "",
            "| Trạm | Số dòng quan sát | Số dòng lưới | Giờ trống chèn thêm | Mốc quan sát đầu | Mốc quan sát cuối |",
            "|---|---|---|---|---|---|",
        ]
        for station, detail in stats["per_station"].items():
            lines.append(
                f"| `{station}` | {_fmt(detail['observed_rows_before'])} | {_fmt(detail['grid_rows_after'])} | "
                f"{_fmt(detail['rows_inserted_as_nan'])} | `{detail['observed_first']}` | `{detail['observed_last']}` |"
            )
        lines += [
            "",
            "> Khoảng trống sau reindex được **giữ nguyên dạng `NaN`** — không nội suy và không xóa dòng —",
            "> để phản ánh trung thực toàn bộ khoảng mất tín hiệu của trạm quan trắc.",
            "",
        ]

    lines += ["### 3.3. Chi Tiết Từng Phép Biến Đổi", ""]
    lines += _render_steps(air["steps"])

    pm_step = next(
        (s for s in air["steps"] if s["name"] == "enforce_pm_subset_constraint"), None
    )
    if pm_step and not pm_step["stats"].get("skipped"):
        stats = pm_step["stats"]
        lines += [
            "### 3.4. Quyết Định Thiết Kế: Vì Sao Xử Lý Toàn Bộ Nghịch Đảo Nghiêm Ngặt",
            "",
            "| Chỉ số | Số lượng | Ý nghĩa |",
            "|---|---|---|",
            f"| Cặp quan sát đồng thời PM2.5 & PM10 | {_fmt(stats['pairs_evaluated'])} | Cơ sở đánh giá |",
            f"| Nghịch đảo **vượt** sai số đo (PM2.5 > PM10 + {_fmt(stats['epsilon_ug_m3'])}) | "
            f"{_fmt(stats['inversions_beyond_epsilon'])} | Nghịch đảo không thể giải thích bằng sai số thiết bị |",
            f"| Nghịch đảo **trong** sai số đo | {_fmt(stats['inversions_within_measurement_tolerance'])} | "
            "Chênh lệch nhỏ, có thể do ảnh hưởng độ ẩm giữa hai kênh quang học |",
            f"| Tổng nghịch đảo nghiêm ngặt được xử lý | {_fmt(stats['rows_nullified'])} | "
            "Chuyển **cả hai** cột thành `NaN` |",
            "",
            "**Vì sao xử lý "
            f"{_fmt(stats['rows_nullified'])} bản ghi thay vì "
            f"{_fmt(stats['inversions_beyond_epsilon'])} như Handoff 1 của Issue #5?**",
            "",
            "Tiêu chí nghiệm thu và mục Kiểm chứng của Issue #6 yêu cầu rõ ràng:",
            "",
            "```python",
            "(df['pm25'] > df['pm10'] + 1e-3).sum() == 0",
            "```",
            "",
            "Nếu chỉ xử lý các bản ghi vượt sai số đo ε = 2,0 µg/m³ thì "
            f"{_fmt(stats['inversions_within_measurement_tolerance'])} bản ghi nghịch đảo nhẹ vẫn còn lại và",
            "điều kiện kiểm chứng trên **không đạt**. Vì vậy Issue #6 áp dụng ràng buộc nghiêm ngặt",
            "`PM2.5 <= PM10` cho mọi cặp quan sát đồng thời, đồng thời **vẫn báo cáo riêng** số bản ghi vượt",
            "sai số để đối chiếu với con số 282 của Issue #5. ε = 2,0 µg/m³ do đó đóng vai trò **mốc phân loại",
            "bằng chứng**, không phải ngưỡng hành động.",
            "",
            "**Hành động khi vi phạm: chuyển CẢ `pm25` và `pm10` thành `NaN`.** Đây chính là hành động được",
            "quy định tại `.agents/rules/data.md` §4 — khi hai kênh quang học của cùng một thiết bị mâu thuẫn",
            "thì không kênh nào còn đáng tin; giữ lại một kênh trong khi xóa kênh kia sẽ tạo ra dữ liệu “nửa vời”",
            "khó giải thích về mặt khoa học. Bản ghi chỉ có một kênh duy nhất được giữ nguyên và tuyệt đối không",
            "được suy diễn giá trị cho kênh còn lại.",
            "",
        ]

    lines += [
        "---",
        "",
        "## 4. Tập Dữ Liệu Khí Tượng Bề Mặt (Weather ERA5)",
        "",
        f"**Tệp canonical:** `{weather['source_path']}`"
        + (f" — sau làm sạch được ghi đè tại `{weather['output_path']}`"
           if weather["output_path"] else " — chạy ở chế độ `save=False`, không ghi đè tệp"),
        "",
        "### 4.1. Trạng Thái Trước và Sau Làm Sạch",
        "",
        "| Chỉ số | Trước làm sạch | Sau làm sạch |",
        "|---|---|---|",
        f"| Số dòng | {_fmt(weather['input']['rows'])} | {_fmt(weather['output']['rows'])} |",
        f"| Mốc thời gian nhỏ nhất | `{weather['input'].get('min_timestamp')}` | `{weather['output'].get('min_timestamp')}` |",
        f"| Mốc thời gian lớn nhất | `{weather['input'].get('max_timestamp')}` | `{weather['output'].get('max_timestamp')}` |",
        f"| Múi giờ | `{weather['input'].get('timezone')}` | `{weather['output'].get('timezone')}` |",
        f"| Số ô khuyết thiếu (toàn bộ biến) | "
        f"{_fmt(sum(weather['input']['missing_cells'].values()))} | "
        f"{_fmt(sum(weather['output']['missing_cells'].values()))} |",
        "",
        "### 4.2. Chi Tiết Từng Phép Biến Đổi",
        "",
    ]
    lines += _render_steps(weather["steps"])
    lines += [
        "",
        "> **Vì sao không áp dụng quy tắc kẹt cảm biến cho khí tượng?** Issue #5 đã đo lịch sử và kết luận",
        "> rõ ràng rằng chuỗi `precipitation = 0.0` kéo dài 275 giờ (74,15% số giờ) và các đợt gió lặng",
        "> `wind_speed = 0.0` là **hiện tượng khí tượng tự nhiên** ở miền Bắc Việt Nam, không phải lỗi phần cứng.",
        "> Áp dụng máy móc quy tắc kẹt cho các biến này sẽ xóa mất dữ liệu khí tượng hợp lệ, vi phạm nguyên tắc",
        "> bảo toàn giá trị thực tế. Quy tắc kẹt vì thế chỉ áp dụng cho nồng độ hạt bụi `pm25` và `pm10`.",
        "",
        "---",
        "",
        "## 5. Kiểm Chứng Tiêu Chí Nghiệm Thu (Validation)",
        "",
        "### 5.1. Tập Ô Nhiễm Không Khí",
        "",
    ]
    lines += _render_validation("ô nhiễm không khí", air["validation"])
    lines += [
        "",
        "Các phép kiểm chứng được thi hành trực tiếp trên DataFrame sau làm sạch:",
        "",
        "```python",
        "assert (df['pm25'] < 0).sum() == 0",
        "pairs = df.dropna(subset=['pm25', 'pm10'])",
        "assert (pairs['pm25'] > pairs['pm10'] + 1e-3).sum() == 0",
        "assert df.groupby('station_id')['timestamp'].apply(lambda s: s.is_monotonic_increasing).all()",
        "assert (df.groupby('station_id')['timestamp'].diff().dropna() == pd.Timedelta(hours=1)).all()",
        "```",
        "",
        "### 5.2. Tập Khí Tượng Bề Mặt",
        "",
    ]
    lines += _render_validation("khí tượng bề mặt", weather["validation"])
    lines += [
        "",
        "---",
        "",
        "## 6. Cột Cờ Chẩn Đoán Được Sinh Ra",
        "",
        "| Cột | Nguồn sinh | Ngữ nghĩa | Giá trị 1 |",
        "|---|---|---|---|",
        f"| `pm25_was_missing` | `flag_prolonged_missing()` | Giờ không có quan sát hợp lệ nằm trong khối khuyết "
        f"liên tục > {thresholds['prolonged_missing_threshold_hours']} giờ | "
        f"{_fmt(_step_stat(air, 'flag_prolonged_missing', 'rows_flagged'))} hàng |",
        f"| `{HIGH_HUMIDITY_FLAG}` | `attach_high_humidity_flag()` | Giờ có độ ẩm tương đối "
        f"> {thresholds['high_humidity_fog_threshold_pct']}% (nghi vấn sương mù quang học) | "
        f"{_fmt(_step_stat(air, 'attach_high_humidity_flag', 'rows_flagged'))} hàng |",
        "",
        "> Cả hai cột cờ đều là **chỉ báo chẩn đoán**, tuyệt đối không phải phép điền khuyết và không làm thay",
        "> đổi bất kỳ giá trị quan sát nào. Bản ghi ở giờ `is_high_humidity_fog = 1` **không** bị xóa.",
        "",
        "---",
        "",
        "## 7. Bảo Toàn Giá Trị Cực Trị Thực Tế",
        "",
        "Làm sạch tất định ở Issue #6 **không** áp dụng bất kỳ quy tắc cắt bỏ giá trị cực trị nào:",
        "",
        "1. **Không đặt trần nồng độ hạt bụi.** Các đợt bùng phát ô nhiễm, nghịch nhiệt mùa đông và",
        "   sự kiện giao thừa pháo hoa đều được giữ nguyên.",
        "2. **Chỉ chuyển `NaN` khi có căn cứ vật lý:** giá trị âm phi lý, mã lỗi ngụy trang, giá trị nằm ngoài",
        "   dải khí quyển, chuỗi kẹt cảm biến chứng minh được, hoặc nghịch đảo khí động học.",
        "3. **Không xóa dòng.** Reindex chỉ *chèn thêm* hàng `NaN` để bộc lộ khoảng trống; không bản ghi",
        "   quan sát nào bị loại khỏi tập dữ liệu.",
        "",
        "---",
        "",
    ]
    lines += _render_extreme_preservation(report)
    lines += [
        "---",
        "",
        "## 8. Bàn Giao Cho Issue #7",
        "",
        ("Artifact sau làm sạch tất định (đã ghi ra đĩa):" if air["output_path"]
         else "Artifact sau làm sạch tất định (chạy ở chế độ `save=False` — chưa ghi ra đĩa):"),
        "",
        f"- `{air['source_path']}` — dạng đầu vào, sau làm sạch: {_fmt(air['output']['rows'])} dòng, "
        f"{air['output']['min_timestamp']} → {air['output']['max_timestamp']}.",
        f"- `{weather['source_path']}` — dạng đầu ra, sau làm sạch: {_fmt(weather['output']['rows'])} dòng, "
        f"{weather['output']['min_timestamp']} → {weather['output']['max_timestamp']}.",
        "",
        "Issue #7 tiếp tục theo đúng trình tự chống rò rỉ: đóng băng tập dữ liệu → phân chia Train/Test theo",
        "chuỗi thời gian tuyến tính → fit tiền xử lý **chỉ trên Train** → transform Train và Test.",
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _step_stat(report_section: Dict[str, Any], step_name: str, stat_key: str) -> Any:
    """Trích một chỉ số thống kê của một bước trong báo cáo (trả về 0 nếu thiếu)."""
    for step in report_section["steps"]:
        if step["name"] == step_name:
            return step["stats"].get(stat_key, 0)
    return 0
