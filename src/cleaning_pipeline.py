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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
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

NUMERIC_FEATURES: List[str] = [
    "pm25",
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

TARGET_CANDIDATE: str = "pm25"


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
    """
    result = df.copy()
    ts = pd.to_datetime(result[timestamp_col])

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


def chronological_split(
    df: pd.DataFrame,
    split_timestamp: pd.Timestamp,
    timestamp_col: str = "timestamp",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chia DataFrame thành (train, test) theo mốc thời gian tuyến tính.

    TUYỆT ĐỐI không dùng random split. Train = dữ liệu trước split_timestamp,
    Test = dữ liệu từ split_timestamp trở đi.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame đã được sắp xếp theo thời gian. Hàm **không** tự sort lại
        (xem `sort_by_time()`); nếu đưa vào dữ liệu chưa sort, thứ tự dòng trong
        `train`/`test` sẽ sai dù điều kiện không rò rỉ vẫn đạt.
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
        Nếu train.max >= test.min (rò rỉ thời gian).
    ValueError
        Nếu split_timestamp nằm ngoài dải thời gian của dữ liệu.
    """
    ts = pd.to_datetime(df[timestamp_col])

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
    num_feats = numeric_features if numeric_features is not None else NUMERIC_FEATURES
    cyc_feats = cyclical_features if cyclical_features is not None else CYCLICAL_FEATURES

    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
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
            "original_skew": float,
            "log1p_skew": float,
            "original_kurtosis": float,
            "log1p_kurtosis": float,
            "log1p_values": np.ndarray,  # đã transform, để kiểm tra phân phối
        }
    """
    y = y_train.dropna()

    original_skew = float(y.skew())
    log1p_values = np.log1p(y)
    log1p_skew = float(pd.Series(log1p_values).skew())

    original_kurtosis = float(y.kurtosis())
    log1p_kurtosis = float(pd.Series(log1p_values).kurtosis())

    result = {
        "original_skew": original_skew,
        "log1p_skew": log1p_skew,
        "original_kurtosis": original_kurtosis,
        "log1p_kurtosis": log1p_kurtosis,
        "log1p_values": log1p_values.values,
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
    AssertionError
        Nếu len(df_merged) > len(df_air) – Row Explosion.
    ValueError
        Nếu khóa không unique trên một trong hai bảng.
    """
    if on is None:
        if "station_id" in df_air.columns and "station_id" in df_weather.columns:
            on = ["station_id", "timestamp"]
        else:
            on = ["timestamp"]

    # Kiểm tra uniqueness của khóa trên mỗi bảng
    for name, df in [("air", df_air), ("weather", df_weather)]:
        dup_count = df.duplicated(subset=on).sum()
        if dup_count > 0:
            raise ValueError(
                f"Khóa {on} không unique trong bảng {name}: "
                f"{dup_count} bản ghi trùng lặp"
            )

    df_merged = df_air.merge(df_weather, on=on, how="left", validate=validate)

    # Chống Row Explosion
    assert len(df_merged) <= len(df_air), (
        f"Row Explosion: merged ({len(df_merged)}) > air ({len(df_air)}). "
        f"Kiểm tra lại khóa ghép {on}."
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
) -> None:
    """
    Xuất DataFrame ra Parquet (snappy) với validation sau khi ghi.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame cần xuất.
    output_path : str | Path
        Đường dẫn file đầu ra.
    compression : str
        Kiểu nén. Mặc định: "snappy".

    Raises
    ------
    AssertionError
        Nếu file đọc lại không khớp schema hoặc row count.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    original_rows = len(df)
    original_cols = list(df.columns)
    original_dtypes = df.dtypes.to_dict()

    df.to_parquet(output_path, compression=compression, index=False)

    # Validation: đọc lại và đối chiếu
    df_readback = pd.read_parquet(output_path)

    assert len(df_readback) == original_rows, (
        f"Row count mismatch: ghi {original_rows}, đọc lại {len(df_readback)}"
    )
    assert list(df_readback.columns) == original_cols, (
        f"Schema mismatch: ghi {original_cols}, đọc lại {list(df_readback.columns)}"
    )
    # `original_dtypes` phải thực sự được dùng: Parquet có thể đổi kiểu bool/int
    # khi round-trip, gây hỏng kiểu cờ chẩn đoán mà không đổi số dòng hay tên cột.
    readback_dtypes = {c: str(df_readback[c].dtype) for c in df_readback.columns}
    mismatched = {
        c: (original_dtypes[c], readback_dtypes[c])
        for c in original_cols
        if original_dtypes[c] != readback_dtypes[c]
    }
    assert not mismatched, f"Dtype mismatch sau khi ghi/đọc lại parquet: {mismatched}"

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
    station_count: int
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
        Danh sách feature columns. Mặc định: tất cả cột trừ target.
    additional_info : dict | None
        Thông tin bổ sung (ví dụ: split_timestamp, pipeline_params).

    Returns
    -------
    DatasetFreezeInfo
    """
    if feature_columns is None:
        feature_columns = [
            c for c in df.columns if c not in {timestamp_col, station_col, TARGET_CANDIDATE}
        ]

    info = DatasetFreezeInfo(
        row_count=len(df),
        timestamp_min=df[timestamp_col].min(),
        timestamp_max=df[timestamp_col].max(),
        station_count=df[station_col].nunique() if station_col in df.columns else 0,
        feature_columns=feature_columns,
        additional_info=additional_info or {},
    )

    logger.info(
        "Dataset frozen: %d rows, %d stations, span [%s → %s]",
        info.row_count,
        info.station_count,
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


def validate_no_leakage(
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    atol: float = 1e-9,
) -> None:
    """
    Kiểm chứng pipeline **thực sự** được fit trên Train chứ không phải trên Test.

    Bản gốc chỉ kiểm tra `statistics_` / `center_` "đã tồn tại", nên pipeline fit
    trên Test vẫn in ra dòng "✓ No leakage" — tức là bảo đảm giả về đúng quy tắc
    cứng nhất của dự án. Hàm này thay bằng phép so sánh số học: median và
    tham số scale của pipeline phải **bằng** giá trị fit lại trên `X_train`, và
    phải **khác** giá trị fit trên `X_test` khi hai tập có phân phối khác nhau.

    Parameters
    ----------
    pipeline : sklearn.pipeline.Pipeline
        Pipeline đã fit.
    X_train : pd.DataFrame
        Train features (dùng để fit).
    X_test : pd.DataFrame
        Test features (chỉ dùng để transform).
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

    # Pipeline chưa fit sẽ khiến `named_transformers_` ném AttributeError khó hiểu
    # ("object has no attribute transformers_"). Chặn trước để lỗi rõ ràng.
    if not hasattr(preprocessor, "named_transformers_"):
        raise AssertionError(
            "Pipeline chưa được fit: ColumnTransformer chưa có `named_transformers_`."
        )

    num_transformer = preprocessor.named_transformers_.get("num")
    if num_transformer is None:
        raise AssertionError("Không tìm thấy numeric transformer!")

    imputer = num_transformer.named_steps.get("imputer")
    if imputer is None:
        raise AssertionError("Không tìm thấy imputer!")

    if not hasattr(imputer, "statistics_"):
        raise AssertionError("Imputer chưa được fit!")

    scaler = num_transformer.named_steps.get("scaler")
    if scaler is None:
        raise AssertionError("Không tìm thấy scaler!")

    if not hasattr(scaler, "center_") or not hasattr(scaler, "scale_"):
        raise AssertionError("Scaler chưa được fit!")

    # --- Phép kiểm chứng thực chất -------------------------------------------
    # Imputer chỉ học trên TẬP CỘT mà ColumnTransformer đã chọn, nên phải so sánh
    # trên đúng tập cột đó. So sánh với toàn bộ `X_train` sẽ lệch số phần tử
    # (ví dụ pipeline 8 cột trong khi X_train có 12 cột) và ném ValueError thay vì
    # kết luận đúng.
    _, _, numeric_columns = next(
        t for t in preprocessor.transformers_ if t[0] == "num"
    )
    numeric_columns = list(numeric_columns)
    missing = [c for c in numeric_columns if c not in X_train.columns]
    if missing:
        raise AssertionError(f"X_train thiếu cột mà pipeline đã học: {missing}")
    missing = [c for c in numeric_columns if c not in X_test.columns]
    if missing:
        raise AssertionError(f"X_test thiếu cột mà pipeline đã học: {missing}")

    # Median mà pipeline đã học phải khớp median của Train trên cùng tập cột.
    expected = SimpleImputer(strategy="median").fit(X_train[numeric_columns]).statistics_
    got = np.asarray(imputer.statistics_, dtype=float)
    if not np.allclose(got, expected, rtol=0, atol=atol):
        test_median = np.asarray(
            SimpleImputer(strategy="median").fit(X_test[numeric_columns]).statistics_,
            dtype=float,
        )
        raise AssertionError(
            "Temporal/preprocessing leakage: imputer.statistics_ khớp Test chứ "
            f"không khớp Train. pipeline={got.tolist()}, Train={expected.tolist()}, "
            f"Test={test_median.tolist()}"
        )

    # Median của Test phải khác median của Train, nếu bằng nhau thì phép so sánh
    # ở trên không có sức phân biệt và kiểm chứng là vô nghĩa.
    test_median = np.asarray(
        SimpleImputer(strategy="median").fit(X_test[numeric_columns]).statistics_,
        dtype=float,
    )
    distinguishable = not np.allclose(got, test_median, rtol=0, atol=atol)
    if not distinguishable:
        raise AssertionError(
            "Kiểm chứng không có sức phân biệt: median của Train và Test bằng "
            "nhau nên không thể chứng minh pipeline fit trên Train. Hãy dùng tập "
            "chia tập có phân phối khác nhau."
        )

    logger.info("✓ No leakage: imputer.statistics_ khớp Train và khác Test")
    logger.info("  - Cột số đã học: %s", numeric_columns)
    logger.info("  - Imputer statistics (pipeline): %s", got.tolist())
    logger.info("  - Imputer statistics (Train)    : %s", expected.tolist())
    logger.info("  - Imputer statistics (Test)     : %s", test_median.tolist())


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
