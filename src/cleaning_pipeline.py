"""
Issue #7 – Preprocessing & sklearn pipeline chống data leakage.

Module này cung cấp các function/interface ĐỘC LẬP có thể hoạt động
ngay khi #5/#6 chưa hoàn thành. Khi #5/#6 merge xong, chỉ cần truyền
output của chúng vào các function dưới đây – không cần viết lại architecture.

PHẠM VI (chỉ những phần độc lập của #7):
  - Cyclical time features (hour/month sin/cos)
  - Chronological split helper (không random split)
  - sklearn Pipeline + ColumnTransformer (fit strictly on Train)
  - Target transformation diagnostic (log1p candidate)
  - Parquet export helper (snappy)
  - Merge function với row-explosion protection
  - Dataset freeze helper (ghi nhận metadata, không hard-code)
  - Integration với #5 (reuse audit_dataframe, audit_six_dimensions)

KHÔNG LÀM (thuộc #5/#6):
  - Completeness/accuracy/consistency/validity/uniqueness/timeliness audit
  - Physical constraint cleaning, sensor error detection, deduplication
  - Geographic filtering, timezone normalization, station-wise reindex
"""

from __future__ import annotations

import logging
import os
import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

logger = logging.getLogger(__name__)

# Reuse từ Issue #5 – không duplicate logic.
# Bắt buộc dùng đường dẫn đóng gói `src.data_quality`: module nằm trong package
# `src/`, nên `from data_quality import ...` luôn ModuleNotFoundError và im lặng
# biến hai hàm thành None — khiến `run_preprocessing_audit()` hỏng vĩnh viễn.
try:
    from src.data_quality import audit_dataframe, audit_six_dimensions
except ImportError as exc:  # pragma: no cover - chỉ xảy ra khi thiếu Issue #5
    # Ghi cảnh báo thay vì nuốt lỗi: `run_preprocessing_audit()` sẽ ném lỗi rõ
    # ràng khi được gọi, còn việc import module vẫn không làm sập CI.
    logger.warning(
        "Không import được src.data_quality (%s). Tính năng audit của Issue #5 "
        "sẽ không khả dụng cho tới khi Issue #5 được cài đặt.",
        exc,
    )
    audit_dataframe = None
    audit_six_dimensions = None

# ---------------------------------------------------------------------------
# Constants – feature groups (không hard-code dataset-specific values)
# ---------------------------------------------------------------------------

TARGET_CANDIDATE: str = "pm25"

# Ứng viên feature SỐ. KHÔNG chứa `TARGET_CANDIDATE`.
#
# Lý do: bản gốc liệt kê cả `pm25`, nên `build_preprocessing_pipeline()` gọi
# không tham số sẽ đưa chính target vào `X`. Bài toán dự báo biến thành bài toán
# đọc lại câu trả lời — R² = 1.0 một cách vô nghĩa, và sai lệch này KHÔNG bị
# `validate_no_leakage()` phát hiện vì imputer vẫn học đúng trên Train.
# `build_preprocessing_pipeline()` giờ raise nếu target lọt vào danh sách.
NUMERIC_FEATURES: List[str] = [
    "pm10",
    "temperature",
    "relative_humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "surface_pressure",
]

CYCLICAL_FEATURES: List[str] = [
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
]

# Cờ chẩn đoán do Issue #5/#6 sinh ra, ĐƯỢC dùng làm feature.
#   - `pm25_was_stuck`      : cảm biến kẹt (hiện là hằng số 0 trên tập Hà Nội,
#                            nên không mang thông tin phân biệt nhưng vô hại)
#   - `is_high_humidity_fog`: sương mù quang học — cảm biến đọc sai, đây là
#                            điều kiện khí quyển nên hợp lệ làm dự báo
DIAGNOSTIC_FEATURES: List[str] = [
    "pm25_was_stuck",
    "is_high_humidity_fog",
]

# Cờ chẩn đoán **KHÔNG** được dùng làm feature vì là hàm xác định của target.
#
# `pm25_was_missing` = `pm25.isna()` với ngưỡng khối khuyết > 6 giờ.
# `SimpleImputer(strategy="median")` lại điền median cho ĐÚNG những hàng đó. Hệ
# quả: mọi hàng `flag == 1` có target bằng đúng median của tập học — đo trên dữ
# liệu thật (cut 2026-01-15, median Train 37,83) là 256/256 hàng ở Train và
# 1.033/1.033 hàng ở Test, tức 100% ở cả hai. Mô hình học được quy tắc
# `flag == 1 => pm25 == median` và đúng 100%, đó là rò rỉ target theo cấu trúc chứ
# không phải tín hiệu vật lý.
#
# Lưu ý khi đọc con số: tổng số hàng `pm25` bị NaN là 1.549, nhưng cờ chỉ bắt
# 1.289 khối dài — 260 khối ngắn cũng được impute nhưng không lộ qua cờ.
#
# `validate_no_leakage()` VỀ BẢN CHẤT KHÔNG THỂ bắt lỗi này: imputer vẫn học
# đúng trên Train. Vì vậy phải loại ở mức danh sách feature, không phải ở mức
# kiểm chứng. Cờ vẫn được GIỮ trong dataset như tài liệu chẩn đoán.
TARGET_DERIVED_FLAGS: List[str] = [
    "pm25_was_missing",
]


# ---------------------------------------------------------------------------
# A. Cyclical time features
# ---------------------------------------------------------------------------


def add_cyclical_time_features(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Thêm các cột đặc trưng chu kỳ thời gian (sin/cos) vào DataFrame.

    Công thức:
        hour_sin = sin(2π * hour / 24)
        hour_cos = cos(2π * hour / 24)
        month_sin = sin(2π * month / 12)
        month_cos = cos(2π * month / 12)

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame chứa cột timestamp (đã là datetime).
    timestamp_col : str
        Tên cột timestamp.

    Returns
    -------
    pd.DataFrame
        DataFrame gốc + 4 cột mới: hour_sin, hour_cos, month_sin, month_cos.

    Raises
    ------
    ValueError
        Nếu cột thời gian có NaT hoặc không parse được. Nhánh `cyc` của
        ColumnTransformer là `passthrough` — không có imputer — nên NaN ở đây đi
        thẳng vào ma trận, và `RobustScaler` phía sau sẽ âm thầm biến nó thành 0.
    """
    result = df.copy()
    ts = pd.to_datetime(result[timestamp_col])

    # NaT -> hour/month là NaN -> sin/cos là NaN -> nhánh `cyc` passthrough không
    # lọc -> RobustScaler đổi NaN thành 0. Hàng đó biến thành "nửa đêm" giả, đúng
    # cái loại rò rỉ âm thầm mà #7 sinh ra để chặn. Phải chặn ngay tại nguồn.
    if ts.isna().any():
        n_nat = int(ts.isna().sum())
        raise ValueError(
            f"Cột thời gian '{timestamp_col}' có {n_nat} giá trị NaT hoặc không "
            "parse được. add_cyclical_time_features() sẽ tạo ra NaN ở cả 4 cột "
            "chu kỳ, mà nhánh `cyc` là passthrough nên không có imputer để bắt. "
            "Hãy xử lý timestamp trước khi gọi hàm này."
        )

    hour = ts.dt.hour
    month = ts.dt.month

    result["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    result["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    result["month_sin"] = np.sin(2 * np.pi * month / 12)
    result["month_cos"] = np.cos(2 * np.pi * month / 12)

    return result


# ---------------------------------------------------------------------------
# B. Chronological split
# ---------------------------------------------------------------------------


def sort_by_time(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    """
    Trả về bản sao đã sắp xếp tăng dần theo cột thời gian.

    `chronological_split()` **không** tự sort lại: sort tại chỗ sẽ che giấu
    việc người gọi truyền vào dữ liệu chưa chuẩn hoá, và một tập dữ liệu bị
    đảo thứ tự dòng là dấu hiệu đường ống ingestion có vấn đề. Gọi hàm này
    tường minh trước `chronological_split()` nếu thật sự cần.
    """
    return df.sort_values(timestamp_col, kind="stable").reset_index(drop=True)


def chronological_split(
    df: pd.DataFrame,
    split_timestamp: pd.Timestamp,
    timestamp_col: str = "timestamp",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chia DataFrame thành (train, test) theo mốc thời gian tuyến tính.

    TUYỆT ĐỐI không dùng random split. Train = dữ liệu trước split_timestamp,
    Test = dữ liệu từ split_timestamp trở đi.

    Hàm **từ chối** dữ liệu không sử dụng được thay vì tự sửa:

      - `NaT` trong cột thời gian — `ts < split` xử lý NaT là `False`, nên hàng đó
        rơi vào Test và mang theo NaT, biến mất khỏi mọi kiểm tra mà không ai biết
        mất bao nhiêu dòng. Tệ hơn: `train.max()` vẫn đúng nên assert rò rỉ thời
        gian vẫn xanh.
      - Thứ tự dòng không tăng dần — điều kiện không rò rỉ vẫn đạt (vì split theo
        mốc thời gian chứ không theo vị trí) nhưng thứ tự dòng trong output sai,
        mọi phép kiểm tra giả định "theo thời gian" phía sau sẽ sai lệch âm thầm.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame đã được sắp xếp theo thời gian (xem `sort_by_time()`).
    split_timestamp : pd.Timestamp
        Mốc cắt. Train: ts < split; Test: ts >= split.
    timestamp_col : str
        Tên cột timestamp.

    Returns
    -------
    (train, test) : Tuple[pd.DataFrame, pd.DataFrame]

    Raises
    ------
    AssertionError
        Nếu train.max >= test.min (rò rỉ thời gian), hoặc dữ liệu chứa NaT,
        hoặc thứ tự dòng không tăng dần theo thời gian.
    ValueError
        Nếu split_timestamp nằm ngoài dải thời gian của dữ liệu.
    """
    ts = pd.to_datetime(df[timestamp_col])

    if ts.isna().any():
        n_nat = int(ts.isna().sum())
        raise AssertionError(
            f"Cột thời gian '{timestamp_col}' có {n_nat} giá trị NaT. "
            "chronological_split() KHÔNG âm thầm bỏ hàng — NaT sẽ rơi vào Test "
            "và làm mất dòng mà không có dấu vết. Hãy xử lý ở #6 hoặc bỏ các hàng "
            "đó một cách tường minh trước khi split."
        )

    if not ts.is_monotonic_increasing:
        # `Series.diff()` trên datetime tz-aware trả về `timedelta64[ns]`, và
        # so sánh nó với `np.timedelta64(1, "h")` quy nạch đơn vị "generic" —
        # numpy đã DeprecationWarning và sẽ ném lỗi. Ép sang so sánh theo
        # `Timedelta` của pandas để không phụ thuộc vào đường chuyển đổi đó.
        deltas = pd.Series(ts).diff()
        first_bad = int(np.argmax((deltas < pd.Timedelta(0)).to_numpy())) + 1
        raise AssertionError(
            f"Cột thời gian '{timestamp_col}' không tăng dần (hàng {first_bad} đi "
            "lùi). chronological_split() không tự sort lại để không che giấu việc "
            "dữ liệu chưa chuẩn hoá. Gọi sort_by_time(df) trước nếu cần."
        )

    if split_timestamp <= ts.min() or split_timestamp > ts.max():
        raise ValueError(
            f"split_timestamp ({split_timestamp}) phải nằm trong dữ liệu: "
            f"({ts.min()}, {ts.max()}]"
        )

    train = df[ts < split_timestamp].copy()
    test = df[ts >= split_timestamp].copy()

    # Validation cứng: không có rò rỉ thời gian
    assert train[timestamp_col].max() < test[timestamp_col].min(), (
        f"Temporal leakage: train.max ({train[timestamp_col].max()}) "
        f">= test.min ({test[timestamp_col].min()})"
    )

    # Không mất dòng: hai tập phải phủ đúng toàn bộ input.
    assert len(train) + len(test) == len(df), (
        f"Split làm mất dòng: {len(train)} + {len(test)} != {len(df)}"
    )

    logger.info(
        "Chronological split @ %s: train=%d rows, test=%d rows",
        split_timestamp,
        len(train),
        len(test),
    )
    return train, test


# ---------------------------------------------------------------------------
# C. sklearn Pipeline + ColumnTransformer
# ---------------------------------------------------------------------------


def build_preprocessing_pipeline(
    numeric_features: Optional[List[str]] = None,
    cyclical_features: Optional[List[str]] = None,
) -> Pipeline:
    """
    Xây dựng Scikit-Learn Pipeline chống rò rỉ dữ liệu.

    Architecture:
        ColumnTransformer:
          - numeric: SimpleImputer(median) → RobustScaler
          - cyclical: passthrough (đã là sin/cos, không cần impute/scale)

    Pipeline CHỈ được fit trên Train. Khi gọi .transform(X_test),
    các tham số (median, IQR) từ Train được áp dụng – không học từ Test.

    Parameters
    ----------
    numeric_features : list[str] | None
        Danh sách cột số. Mặc định: NUMERIC_FEATURES.
    cyclical_features : list[str] | None
        Danh sách cột chu kỳ. Mặc định: CYCLICAL_FEATURES.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Pipeline chưa fit. Gọi .fit(X_train) rồi .transform(X_train/X_test).
    """
    num_feats = list(numeric_features if numeric_features is not None else NUMERIC_FEATURES)
    cyc_feats = list(cyclical_features if cyclical_features is not None else CYCLICAL_FEATURES)

    # Target vào feature = bài toán đọc lại đáp án. Chặn ở đây, không đợi tới test.
    if TARGET_CANDIDATE in num_feats:
        raise ValueError(
            f"Target '{TARGET_CANDIDATE}' không được đưa vào feature. "
            "Đưa target vào X biến bài toán dự báo thành bài toán đọc lại câu "
            "trả lời, khiến mọi chỉ số ở Issue #11-#13 mất ý nghĩa."
        )
    if TARGET_CANDIDATE in cyc_feats:
        raise ValueError(f"Target '{TARGET_CANDIDATE}' không được đưa vào cyclical features.")

    dup_num = sorted({c for c in num_feats if num_feats.count(c) > 1})
    if dup_num:
        raise ValueError(f"Cột số bị lặp trong danh sách feature: {dup_num}")

    numeric_transformer = Pipeline(
        steps=[
            # keep_empty_features=True: cột toàn NaN phải được giữ lại (giá trị
            # 0 sau impute) chứ không âm thầm biến mất khỏi ma trận — mất cột
            # làm lệch mọi `coef_`/`feature_importances_` đọc theo vị trí.
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", RobustScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, num_feats),
            ("cyc", "passthrough", cyc_feats),
        ],
        remainder="drop",  # bỏ các cột không được định nghĩa (ví dụ: target, ID)
    )

    pipeline = Pipeline(steps=[("preprocessor", preprocessor)])

    logger.info(
        "Pipeline built: numeric=%s, cyclical=%s",
        num_feats,
        cyc_feats,
    )
    return pipeline


def fit_pipeline_on_train(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
) -> Pipeline:
    """
    Fit pipeline STRICTLY trên Train.

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Pipeline từ build_preprocessing_pipeline().
    X_train : pd.DataFrame
        Features của Train (không chứa target).

    Returns
    -------
    Pipeline
        Pipeline đã fit.
    """
    pipeline.fit(X_train)
    logger.info("Pipeline fitted on train set (%d rows)", len(X_train))
    return pipeline


def transform_with_pipeline(
    pipeline: Pipeline,
    X: pd.DataFrame,
) -> np.ndarray:
    """
    Transform dữ liệu bằng pipeline đã fit.

    Áp dụng cho cả Train và Test – KHÔNG học lại tham số từ Test.

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Pipeline đã fit trên Train.
    X : pd.DataFrame
        Features cần transform.

    Returns
    -------
    np.ndarray
        Ma trận đã transform.
    """
    return pipeline.transform(X)


# ---------------------------------------------------------------------------
# D. Target transformation diagnostic (log1p candidate)
# ---------------------------------------------------------------------------


def evaluate_log1p_transform(
    y_train: pd.Series,
) -> Dict[str, Any]:
    """
    Đánh giá biến đổi log1p trên target – CHỈ diagnostic, KHÔNG kết luận.

    Tính các chỉ số trên Train để sau khi dataset freeze có thể quyết định
    có dùng log1p hay không dựa trên bằng chứng thực tế.

    Parameters
    ----------
    y_train : pd.Series
        Target (pm25) của Train.

    Returns
    -------
    dict
        {
            "n_observations": int,
            "n_negative": int,
            "original_skew": float,
            "log1p_skew": float,
            "original_kurtosis": float,
            "log1p_kurtosis": float,
            "log1p_values": pd.Series,  # giữ index để đối chiếu với y_train
        }

    Raises
    ------
    ValueError
        Nếu target có giá trị âm. `log1p` không xác định ở đó và `np.log1p`
        âm thầm trả NaN — biểu đồ phân phối sau đó vẽ ra rỗng mà không ai biết
        vì sao. Với PM2.5 đơn vị µg/m³ thế này không xảy ra, nhưng hàm không được
        giả định điều đó về dữ liệu tương lai.
    """
    y = pd.Series(y_train).dropna()

    if y.empty:
        raise ValueError("y_train rỗng sau khi dropna — không đánh giá được.")

    n_negative = int((y < 0).sum())
    if n_negative:
        raise ValueError(
            f"y_train có {n_negative} giá trị âm (min={float(y.min()):.4f}). "
            "log1p không xác định ở đó. PM2.5 đơn vị µg/m³ phải >= 0 — hãy kiểm "
            "tra lại đơn vị hoặc nguồn dữ liệu trước khi dùng log1p."
        )

    original_skew = float(y.skew())
    log1p_values = np.log1p(y)
    log1p_skew = float(log1p_values.skew())

    original_kurtosis = float(y.kurtosis())
    log1p_kurtosis = float(log1p_values.kurtosis())

    result = {
        "n_observations": int(len(y)),
        "n_negative": n_negative,
        "original_skew": original_skew,
        "log1p_skew": log1p_skew,
        "original_kurtosis": original_kurtosis,
        "log1p_kurtosis": log1p_kurtosis,
        "log1p_values": log1p_values,
    }

    logger.info(
        "log1p diagnostic: skew %.3f → %.3f, kurtosis %.3f → %.3f",
        original_skew,
        log1p_skew,
        original_kurtosis,
        log1p_kurtosis,
    )
    return result


# ---------------------------------------------------------------------------
# E. Merge function với row-explosion protection
# ---------------------------------------------------------------------------


def merge_air_weather(
    df_air: pd.DataFrame,
    df_weather: pd.DataFrame,
    on: Optional[List[str]] = None,
    validate: str = "1:1",
) -> pd.DataFrame:
    """
    Ghép dữ liệu ô nhiễm và khí tượng theo khóa quan sát.

    Parameters
    ----------
    df_air : pd.DataFrame
        Dữ liệu chất lượng không khí (canonical).
    df_weather : pd.DataFrame
        Dữ liệu khí tượng (canonical).
    on : list[str] | None
        Cột khóa ghép. Mặc định: ["station_id", "timestamp"] nếu cả hai có station_id,
        ngược lại ["timestamp"].
    validate : str
        Kiểm tra quan hệ: "1:1", "1:m", "m:1", "m:m". Mặc định "1:1".

    Returns
    -------
    pd.DataFrame
        DataFrame đã ghép.

    Raises
    ------
    ValueError
        Nếu khóa không unique trên một trong hai bảng, nếu hai bảng có cột trùng
        tên ngoài khóa, hoặc nếu KHÔNG cột khí tượng nào khớp được (toàn NaN).
    AssertionError
        Nếu len(df_merged) != len(df_air) – Row Explosion.
    """
    if on is None:
        if "station_id" in df_air.columns and "station_id" in df_weather.columns:
            on = ["station_id", "timestamp"]
        else:
            on = ["timestamp"]

    # Cột trùng tên ngoài khóa sẽ bị pandas đổi thành `_x`/`_y`, mất tên gốc —
    # ví dụ `pm25_was_missing` biến mất khỏi output, mọi tra cứu tên gốc phía
    # sau sẽ KeyError hoặc âm thầm lấy nhầm cột bên khí tượng.
    collide = sorted((set(df_air.columns) & set(df_weather.columns)) - set(on))
    if collide:
        raise ValueError(
            f"Hai bảng có cột trùng tên ngoài khóa ghép {on}: {collide}. "
            "pandas sẽ tách thành hậu tố _x/_y và mất tên gốc. Hãy đổi tên cột "
            "trước khi ghép, hoặc truyền `on` rõ ràng."
        )

    # Kiểm tra uniqueness của khóa trên mỗi bảng
    for name, df in [("air", df_air), ("weather", df_weather)]:
        dup_count = df.duplicated(subset=on).sum()
        if dup_count > 0:
            raise ValueError(
                f"Khóa {on} không unique trong bảng {name}: "
                f"{dup_count} bản ghi trùng lặp"
            )

    df_merged = df_air.merge(df_weather, on=on, how="left", validate=validate)

    # Chống Row Explosion — HAI phép, cả hai đều đúng, khác sức bắt:
    #
    # (1) `<=` là điều kiện cần mà Issue #7 §Yêu cầu kỹ thuật chỉ định, nên
    #     giữ nguyên để không lệch khỏi đặc tả. Nhưng với `how="left"` + khoá
    #     unique hai phía + `validate="1:1"`, nó **luôn đúng** và không bắt được
    #     gì: row explosion bị chặn sớm hơn bởi kiểm tra khoá unique ở trên.
    # (2) `==` là phép thật sự phân biệt được. `merge(how="left")` phải giữ đúng
    #     số dòng của bảng trái; lệch bất kỳ dòng nào là join sai.
    #
    # Giữ (1) vì đặc tả yêu cầu, giữ (2) vì (1) một mình là dead code.
    assert len(df_merged) <= len(df_air), (
        f"Row Explosion: merged ({len(df_merged)}) > air ({len(df_air)}). "
        f"Kiểm tra lại khóa ghép {on}."
    )
    assert len(df_merged) == len(df_air), (
        f"Row count drift: merged ({len(df_merged)}) != air ({len(df_air)}). "
        f"Kiểm tra lại khóa ghép {on} và tham số validate={validate!r}. "
        f"`<=` ở trên không bắt được trường hợp này."
    )

    # `.agents/rules/data.md` §3.6 BẮT BUỘC phải có kiểm tra này. Thiếu nó thì
    # một lệch timezone / định dạng timestamp sẽ cho ra frame trông hoàn toàn
    # bình thường (đúng số dòng, đúng schema) nhưng mọi cột khí tượng đều NaN —
    # rồi `SimpleImputer` lấp median và mô hình vẫn "chạy mượt" trên 6 hằng số
    # bịa, mọi chỉ số ở Issue #11-#13 trở nên vô nghĩa.
    weather_cols = [c for c in df_weather.columns if c not in on]
    if weather_cols:
        all_nan = [c for c in weather_cols if df_merged[c].isna().all()]
        if all_nan:
            raise ValueError(
                f"Không dòng nào khớp được khí tượng — toàn bộ cột "
                f"{all_nan} đều NaN. Kiểm tra lại timezone và định dạng "
                f"timestamp, hoặc cửa sổ thời gian của hai bảng (khóa {on})."
            )
        unmatched = int(df_merged[weather_cols].isna().all(axis=1).sum())
        if unmatched:
            coverage = 100.0 * (1 - unmatched / len(df_merged))
            warnings.warn(
                f"Coverage khí tượng chỉ {coverage:.1f}%: {unmatched}/{len(df_merged)} "
                f"dòng không khớp được khí tượng nào. Kiểm tra lại cửa sổ thời gian.",
                RuntimeWarning,
                stacklevel=2,
            )

    logger.info(
        "Merged air (%d) + weather (%d) → %d rows on %s",
        len(df_air),
        len(df_weather),
        len(df_merged),
        on,
    )
    return df_merged


# ---------------------------------------------------------------------------
# F. Parquet export helper
# ---------------------------------------------------------------------------


def export_to_parquet(
    df: pd.DataFrame,
    output_path: str | Path,
    compression: str = "snappy",
    overwrite: bool = False,
) -> None:
    """
    Xuất DataFrame ra Parquet (snappy) với validation sau khi ghi.

    Ghi **nguyên tử**: ghi vào file tạm cùng thư mục rồi mới `os.replace()` sang
    đích. Bản gốc ghi thẳng vào đích nên nếu validation sau ghi thất bại (dtype
    lệch, schema lệch) thì **file hỏng vẫn nằm ở đó** — người chạy tiếp đọc
    được một artifact đã hỏng mà tin là hợp lệ. Ở đây file tạm bị dọn và đích
    giữ nguyên trạng thái trước đó.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame cần xuất.
    output_path : str | Path
        Đường dẫn file đầu ra.
    compression : str
        Kiểu nén. Mặc định: "snappy" theo `.agents/rules/data.md`.
    overwrite : bool
        Cho phép ghi đè file đã tồn tại. Mặc định False: ghi đè artifact đã
        đóng băng là hành vi không thể phát hiện và làm mất dấu vết chạy trước.

    Raises
    ------
    FileExistsError
        Nếu file đích đã tồn tại và `overwrite=False`.
    AssertionError
        Nếu file đọc lại không khớp schema, row count hoặc dtype.
    """
    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"{output_path} đã tồn tại. Truyền overwrite=True nếu thực sự muốn "
            "ghi đè — artifact đã đóng băng là bằng chứng, không phải rác."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    original_rows = len(df)
    original_cols = list(df.columns)
    original_dtypes = df.dtypes.to_dict()

    # os.replace là atomic trên cùng filesystem; temp nằm CÙNG thư mục đích.
    fd, tmp_name = tempfile.mkstemp(
        dir=str(output_path.parent), suffix=".parquet.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path, compression=compression, index=False)

        # Validation: đọc lại và đối chiếu TRƯỚC khi chạm vào file đích.
        df_readback = pd.read_parquet(tmp_path)

        assert len(df_readback) == original_rows, (
            f"Row count mismatch: ghi {original_rows}, đọc lại {len(df_readback)}"
        )
        assert list(df_readback.columns) == original_cols, (
            f"Schema mismatch: ghi {original_cols}, đọc lại {list(df_readback.columns)}"
        )
        # `original_dtypes` phải thực sự được dùng: Parquet có thể đổi kiểu
        # bool/int khi round-trip, gây hỏng kiểu cờ chẩn đoán mà không đổi số
        # dòng hay tên cột.
        readback_dtypes = {c: str(df_readback[c].dtype) for c in df_readback.columns}
        mismatched = {
            c: (str(original_dtypes[c]), readback_dtypes[c])
            for c in original_cols
            if str(original_dtypes[c]) != readback_dtypes[c]
        }
        assert not mismatched, (
            f"Dtype mismatch sau khi ghi/đọc lại parquet: {mismatched}"
        )
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise

    os.replace(tmp_path, output_path)

    logger.info(
        "Exported %d rows × %d cols → %s (compression=%s)",
        original_rows,
        len(original_cols),
        output_path,
        compression,
    )


# ---------------------------------------------------------------------------
# G. Dataset freeze helper
# ---------------------------------------------------------------------------


@dataclass
class DatasetFreezeInfo:
    """Metadata của dataset đã đóng băng – không hard-code giá trị."""

    row_count: int
    timestamp_min: pd.Timestamp
    timestamp_max: pd.Timestamp
    # Optional vì `freeze_dataset()` dùng None khi dataset không có cột trạm —
    # báo cáo "0 trạm" là khẳng định sai sự thật, còn None là "không đo được".
    station_count: Optional[int]
    feature_columns: List[str] = field(default_factory=list)
    target_column: str = TARGET_CANDIDATE
    additional_info: Dict[str, Any] = field(default_factory=dict)


def freeze_dataset(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    station_col: str = "station_id",
    feature_columns: Optional[List[str]] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> DatasetFreezeInfo:
    """
    Ghi nhận metadata của dataset sau khi đóng băng.

    KHÔNG hard-code giá trị hiện tại thành final result.
    Chỉ thu thập và trả về thông tin để sau này so sánh/kiểm chứng.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset đã làm sạch (output của #5/#6).
    timestamp_col : str
        Tên cột timestamp.
    station_col : str
        Tên cột station_id.
    feature_columns : list[str] | None
        Danh sách feature columns. Mặc định: **cột số** trừ target, timestamp và
        trạm — đúng tập mà `build_preprocessing_pipeline()` nhận. Bản gốc lấy
        *mọi* cột còn lại, nên `pm25_was_missing` (hàm xác định của target) và
        `location` (chuỗi) lọt vào danh sách feature theo mặc định.
    additional_info : dict | None
        Thông tin bổ sung (ví dụ: split_timestamp, pipeline_params).

    Returns
    -------
    DatasetFreezeInfo
    """
    if feature_columns is None:
        excluded = {timestamp_col, station_col, TARGET_CANDIDATE, *TARGET_DERIVED_FLAGS}
        feature_columns = [
            c
            for c in df.columns
            if c not in excluded and pd.api.types.is_numeric_dtype(df[c])
        ]
        dropped = [
            c for c in df.columns
            if c not in excluded and not pd.api.types.is_numeric_dtype(df[c])
        ]
        if dropped:
            logger.info(
                "freeze_dataset: bỏ %d cột không phải số khỏi feature mặc định: %s",
                len(dropped),
                dropped,
            )
        if any(c in df.columns for c in TARGET_DERIVED_FLAGS):
            logger.info(
                "freeze_dataset: loại %s khỏi feature mặc định vì là hàm xác định "
                "của target — dùng làm feature là rò rỉ mà guard nào cũng không bắt.",
                TARGET_DERIVED_FLAGS,
            )

    info = DatasetFreezeInfo(
        row_count=len(df),
        timestamp_min=df[timestamp_col].min(),
        timestamp_max=df[timestamp_col].max(),
        station_count=df[station_col].nunique() if station_col in df.columns else None,
        feature_columns=feature_columns,
        additional_info=additional_info or {},
    )

    logger.info(
        "Dataset frozen: %d rows, %s stations, span [%s → %s]",
        info.row_count,
        info.station_count if info.station_count is not None else "unknown",
        info.timestamp_min,
        info.timestamp_max,
    )
    return info


# ---------------------------------------------------------------------------
# H. Integration với Issue #5 (reuse audit functions)
# ---------------------------------------------------------------------------


def run_preprocessing_audit(
    df: pd.DataFrame,
    dataset_name: str = "canonical_dataset",
) -> Dict[str, Any]:
    """
    Chạy audit từ Issue #5 trên dataset trước khi preprocessing.

    Reuse trực tiếp `audit_dataframe` và `audit_six_dimensions` từ `data_quality.py`.
    Không duplicate logic – chỉ gọi lại và wrap kết quả.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset cần audit (thường là output của #5/#6).
    dataset_name : str
        Tên dataset để ghi nhận trong báo cáo.

    Returns
    -------
    dict
        {
            "summary_table": pd.DataFrame,  # từ audit_dataframe
            "six_dimensions": dict,         # từ audit_six_dimensions
        }
    """
    if audit_dataframe is None or audit_six_dimensions is None:
        raise ImportError(
            "Không thể import audit functions từ data_quality. "
            "Đảm bảo Issue #5 đã được implement."
        )

    summary_table = audit_dataframe(df)
    six_dims = audit_six_dimensions(df, dataset_name=dataset_name)

    logger.info("Preprocessing audit completed for '%s'", dataset_name)
    return {
        "summary_table": summary_table,
        "six_dimensions": six_dims,
    }


def _learned_arrays(estimator: Any) -> Dict[str, np.ndarray]:
    """
    Thu thập **mọi** tham số đã học của một estimator thành dict có khoá đầy đủ.

    Bản gốc chỉ đọc `imputer.statistics_` và bỏ qua `scaler.center_`/`scale_`, nên
    thay `RobustScaler` bằng bản fit trên Test vẫn in ra "✓ No leakage" dù
    docstring khẳng định đã kiểm tra cả tham số scale. Hàm này đi theo cây
    `named_steps` và gom mọi thuộc tính kết thúc bằng `_` có kiểu số, nên guard
    không cần biết trước pipeline có mấy nhánh hay tên gì.
    """
    found: Dict[str, np.ndarray] = {}

    def walk(est: Any, path: str) -> None:
        # Pipeline lưu con trong `named_steps`; ColumnTransformer lưu trong
        # `transformers_` (thuộc tính đã fit). Bỏ qua `transformers_` thì
        # ColumnTransformer trả về dict rỗng vì các biến con nằm trong
        # `_transformers` — tức là guard im lặng đúng lúc cần phát hiện rò rỉ.
        for name, child in getattr(est, "named_steps", {}).items():
            walk(child, f"{path}.{name}" if path else name)

        transformers = getattr(est, "transformers_", None)
        if isinstance(transformers, list):
            for entry in transformers:
                if not isinstance(entry, tuple) or len(entry) < 2:
                    continue
                name, child = entry[0], entry[1]
                if hasattr(child, "transform") or hasattr(child, "fit"):
                    walk(child, f"{path}.{name}" if path else str(name))

        for key, value in vars(est).items():
            if key.startswith("_") or not key.endswith("_"):
                continue
            if isinstance(value, np.ndarray) and value.dtype.kind in "fbiu":
                found[f"{path or est.__class__.__name__}::{key}"] = np.asarray(
                    value, dtype=float
                )

    walk(estimator, "")
    return found


def validate_no_leakage(
    pipeline: Pipeline,
    *,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    timestamps: Optional[pd.Series] = None,
    test_timestamps: Optional[pd.Series] = None,
    atol: float = 1e-9,
) -> None:
    """
    Kiểm chứng pipeline **thực sự** được fit trên Train chứ không phải trên Test.

    Bốn lớp kiểm chứng, mỗi lớp vá một lỗ hổng của bản gốc:

    1. **Thứ tự thời gian.** Bản gốc không đọc cột `timestamp` lần nào, nên một
       `train_test_split` ngẫu nhiên — vi phạm cam biên #1 của dự án — vẫn in ra
       "✓ No leakage". Nay hàm so `train.max() < test.min()`.
    2. **Giá trị học được, không chỉ sự tồn tại.** Bản gốc kiểm `hasattr()` rồi bỏ
       qua, nên chỉ so `imputer.statistics_`. Nay so **mọi** tham số đã học
       (`statistics_`, `center_`, `scale_`, ...) với giá trị refit trên Train.
    3. **Mọi nhánh của ColumnTransformer.** Bản gốc hard-code tên `"num"`, nên
       transformer thứ hai học trên Test là im lặng. Nay `_learned_arrays()` đi
       theo cây `named_steps` nên tự bao phủ mọi nhánh, kể cả nhánh thêm sau này.
    4. **Thứ tự đối số.** `X_train`/`X_test` là keyword-only; trước đó truyền
       sai thứ tự vô hiệu hóa toàn bộ guard.

    Tham số `X_train`/`X_test` là **keyword-only** có chủ đích: gọi
    `validate_no_leakage(p, X_test, X_train)` là lỗi ghi nhầm biến, và guard phải
    bắt được chứ không được tin theo tên tham số.

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Pipeline đã fit.
    X_train, X_test : pd.DataFrame
        Features của Train (dùng để fit) và Test (chỉ dùng để transform).
    timestamps, test_timestamps : pd.Series | None
        Cột thời gian tương ứng. **Nên truyền cả hai** — khi đó hàm kiểm tra
        không có chồng lấn thời gian giữa hai tập, tức là bắt được phép chia
        ngẫu nhiên.

        Bỏ truyền thì lớp kiểm chứng thứ tự thời gian **bị tắt** và hàm chỉ in
        một `logging.WARNING**; đó là lựa chọn của người gọi, không phải hành
        vi mặc định an toàn. Trừ cả hai hoặc chỉ truyền một sẽ ném
        `AssertionError` — truyền nửa vời là lỗi ghi nhầm, không phải ý định.

        .. warning::
           Đo lại trên dữ liệu thật: một ``train_test_split`` ngẫu nhiên với
           đúng ``X_train``/``X_test`` nhưng **không** truyền timestamp là
           **không bị bắt**. Các lớp 2–3 vẫn phát hiện được *scaler fit sai
           tập*, nhưng không phát hiện được *chính cái phép chia*. Vì vậy lớp 1
           là lớp duy nhất chống được random split — hãy luôn bật nó.
    atol : float
        Sai số cho phép khi so sánh float.

    Raises
    ------
    AssertionError
        Nếu phát hiện dấu hiệu leakage, hoặc pipeline chưa fit.
    """
    if not hasattr(pipeline, "named_steps"):
        raise AssertionError("Pipeline chưa được fit!")

    preprocessor = pipeline.named_steps.get("preprocessor")
    if preprocessor is None:
        raise AssertionError("Pipeline không có bước 'preprocessor'!")

    if not hasattr(preprocessor, "named_transformers_"):
        raise AssertionError(
            "Pipeline chưa được fit: ColumnTransformer chưa có `named_transformers_`."
        )

    # --- Lớp 1: thứ tự thời gian ---------------------------------------------
    #
    # Lớp này là **tùy chọn** (vì `chronological_split()` đã tự kiểm), nhưng
    # việc nó tùy chọn chính là một lỗ hổng âm thầm: một `train_test_split`
    # ngẫu nhiên — vi phạm cam biên #1 của dự án — vẫn in ra "✓ No leakage"
    # nếu người gọi quên truyền `timestamps`. Đo lại: `train_test_split`
    # ngẫu nhiên với đúng X_train/X_test nhưng KHÔNG truyền timestamp là
    # **không bị bắt**. Vì vậy bỏ truyền phải nói to, không được im lặng.
    if (timestamps is None) != (test_timestamps is None):
        raise AssertionError(
            "Truyền `timestamps` nhưng không truyền `test_timestamps` (hoặc "
            "ngược lại). Lớp kiểm chứng thứ tự thời gian cần CẢ HAI, hoặc "
            "KHÔNG truyền cả hai nếu muốn bỏ qua lớp này."
        )
    if timestamps is None or test_timestamps is None:
        logger.warning(
            "validate_no_leakage(): KHÔNG truyền timestamps/test_timestamps → "
            "LỚP KIỂM CHỨNG THỨ TỰ THỜI GIAN ĐANG BỊ TẮT. Một phép chia ngẫu "
            "nhiên sẽ KHÔNG bị phát hiện. Hãy truyền cả hai nếu cần chứng minh "
            "train.max() < test.min()."
        )
    else:
        tr = pd.to_datetime(pd.Series(timestamps))
        te = pd.to_datetime(pd.Series(test_timestamps))
        if tr.isna().any() or te.isna().any():
            raise AssertionError(
                "Cột thời gian có NaT — không thể kiểm chứng rò rỉ thời gian."
            )
        if not (tr.max() < te.min()):
            raise AssertionError(
                "Rò rỉ thời gian: train.max()="
                f"{tr.max()} KHÔNG nhỏ hơn test.min()={te.min()}. "
                "Đây là dấu hiệu split ngẫu nhiên — dự án cấm tuyệt đối random split."
            )

    # --- Chuẩn bị: tập cột mà ColumnTransformer thực sự học -------------------
    # Imputer chỉ học trên TẬP CỘT đã chọn, nên phải so sánh trên đúng tập cột đó.
    #
    # Bỏ qua entry `remainder`: khi input có cột thừa, sklearn ghi lại các cột
    # bị drop dưới dạng CHỈ SỐ VỊ TRÍ ([1], [2], …), không phải tên cột. Thu
    # chúng vào danh sách tên sẽ ra thông báo "thiếu cột '1'" vô nghĩa.
    columns: List[str] = []
    for name, _, cols in preprocessor.transformers_:
        if name == "remainder":
            continue
        if isinstance(cols, (list, tuple, np.ndarray, pd.Index)):
            selector = [c for c in cols]
            positional = [c for c in selector if not isinstance(c, str)]
            if positional:
                raise AssertionError(
                    f"ColumnTransformer '{name}' dùng chỉ số vị trí {positional} thay "
                    "vì tên cột. Guard chỉ kiểm chứng được selector theo tên — hãy "
                    "truyền danh sách tên cột rõ ràng."
                )
            columns.extend(selector)
    columns = list(dict.fromkeys(columns))
    if not columns:
        raise AssertionError("ColumnTransformer không có cột số nào để kiểm chứng.")

    for label, frame in (("X_train", X_train), ("X_test", X_test)):
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise AssertionError(f"{label} thiếu cột mà pipeline đã học: {missing}")

    # --- Lớp 2 + 3: so MỌI tham số đã học với giá trị refit -------------------
    got = _learned_arrays(preprocessor)
    if not got:
        raise AssertionError(
            "Pipeline chưa có tham số nào được học — không thể kiểm chứng rò rỉ."
        )

    ref_train = clone(pipeline).fit(X_train[columns])
    ref_test = clone(pipeline).fit(X_test[columns])
    exp_train = _learned_arrays(ref_train.named_steps["preprocessor"])
    exp_test = _learned_arrays(ref_test.named_steps["preprocessor"])

    mismatched = []
    for key, value in got.items():
        if key not in exp_train:
            mismatched.append((key, "chỉ xuất hiện ở pipeline đang kiểm chứng"))
            continue
        if not np.allclose(value, exp_train[key], rtol=0, atol=atol):
            mismatched.append(
                (key,
                 f"pipeline={np.ravel(value)[:4].tolist()} khớp "
                 f"Test={np.ravel(exp_test.get(key, value))[:4].tolist()} chứ không "
                 f"khớp Train={np.ravel(exp_train[key])[:4].tolist()}")
            )

    if mismatched:
        lines = "\n  - ".join(f"{k}: {why}" for k, why in mismatched[:6])
        raise AssertionError(
            "Temporal/preprocessing leakage — tham số đã học KHÔNG khớp giá trị "
            f"refit trên Train:\n  - {lines}\n"
            "Pipeline phải fit CHỈ trên Train. Kiểm tra cả imputer lẫn scaler, và "
            "mọi nhánh của ColumnTransformer."
        )

    # --- Lớp 4: phép so sánh phải có sức phân biệt ----------------------------
    if all(
        key in exp_test and np.allclose(got[key], exp_test[key], rtol=0, atol=atol)
        for key in got
    ):
        raise AssertionError(
            "Kiểm chứng không có sức phân biệt: refit trên Train và trên Test cho ra "
            "cùng tham số, nên không thể chứng minh pipeline fit trên Train. Hãy dùng "
            "tập chia có phân phối khác nhau."
        )

    logger.info("✓ No leakage: mọi tham số đã học khớp refit Train, khác refit Test")
    logger.info("  - Cột đã học: %s", columns)
    logger.info("  - Số tham số so sánh: %d", len(got))
    for key in sorted(got)[:8]:
        logger.info("    %-46s %s", key, np.ravel(got[key])[:4].tolist())


def freeze_dataset_with_audit(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    station_col: str = "station_id",
    feature_columns: Optional[List[str]] = None,
    additional_info: Optional[Dict[str, Any]] = None,
    run_audit: bool = True,
) -> Tuple[DatasetFreezeInfo, Optional[Dict[str, Any]]]:
    """
    Freeze dataset và chạy audit (nếu run_audit=True).

    Parameters
    ----------
    df : pd.DataFrame
        Dataset đã làm sạch.
    timestamp_col : str
        Tên cột timestamp.
    station_col : str
        Tên cột station_id.
    feature_columns : list[str] | None
        Danh sách feature columns.
    additional_info : dict | None
        Thông tin bổ sung.
    run_audit : bool
        Có chạy audit từ #5 không. Mặc định: True.

    Returns
    -------
    (DatasetFreezeInfo, audit_results | None)
    """
    # Freeze dataset
    freeze_info = freeze_dataset(
        df,
        timestamp_col=timestamp_col,
        station_col=station_col,
        feature_columns=feature_columns,
        additional_info=additional_info,
    )

    # Chại audit nếu yêu cầu
    audit_results = None
    if run_audit:
        audit_results = run_preprocessing_audit(df, dataset_name="preprocessing_input")
        # Ghi nhận audit vào freeze info
        freeze_info.additional_info["audit"] = {
            "summary_table": audit_results["summary_table"].to_dict(),
            "six_dimensions": audit_results["six_dimensions"],
        }

    return freeze_info, audit_results
