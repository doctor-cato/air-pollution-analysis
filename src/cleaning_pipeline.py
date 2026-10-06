
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

try:
    from src.data_quality import audit_dataframe, audit_six_dimensions
except ImportError as exc:
    logger.warning(
        "Không import được src.data_quality (%s). Tính năng audit của Issue #5 "
        "sẽ không khả dụng cho tới khi Issue #5 được cài đặt.",
        exc,
    )
    audit_dataframe = None
    audit_six_dimensions = None


TARGET_CANDIDATE: str = "pm25"

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

DIAGNOSTIC_FEATURES: List[str] = [
    "pm25_was_stuck",
]

TARGET_DERIVED_FLAGS: List[str] = [
    "pm25_was_missing",
]


NON_PREDICTIVE_FLAGS: List[str] = [
    "is_high_humidity_fog",
]


def add_cyclical_time_features(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    result = df.copy()
    ts = pd.to_datetime(result[timestamp_col])

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


def sort_by_time(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp",
) -> pd.DataFrame:
    return df.sort_values(timestamp_col, kind="stable").reset_index(drop=True)


def chronological_split(
    df: pd.DataFrame,
    split_timestamp: pd.Timestamp,
    timestamp_col: str = "timestamp",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
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

    assert train[timestamp_col].max() < test[timestamp_col].min(), (
        f"Temporal leakage: train.max ({train[timestamp_col].max()}) "
        f">= test.min ({test[timestamp_col].min()})"
    )

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


def build_preprocessing_pipeline(
    numeric_features: Optional[List[str]] = None,
    cyclical_features: Optional[List[str]] = None,
) -> Pipeline:
    num_feats = list(numeric_features if numeric_features is not None else NUMERIC_FEATURES)
    cyc_feats = list(cyclical_features if cyclical_features is not None else CYCLICAL_FEATURES)

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
            ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("scaler", RobustScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, num_feats),
            ("cyc", "passthrough", cyc_feats),
        ],
        remainder="drop",
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
    pipeline.fit(X_train)
    logger.info("Pipeline fitted on train set (%d rows)", len(X_train))
    return pipeline


def transform_with_pipeline(
    pipeline: Pipeline,
    X: pd.DataFrame,
) -> np.ndarray:
    return pipeline.transform(X)


def evaluate_log1p_transform(
    y_train: pd.Series,
) -> Dict[str, Any]:
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


def merge_air_weather(
    df_air: pd.DataFrame,
    df_weather: pd.DataFrame,
    on: Optional[List[str]] = None,
    validate: str = "1:1",
) -> pd.DataFrame:
    if on is None:
        if "station_id" in df_air.columns and "station_id" in df_weather.columns:
            on = ["station_id", "timestamp"]
        else:
            on = ["timestamp"]

    collide = sorted((set(df_air.columns) & set(df_weather.columns)) - set(on))
    if collide:
        raise ValueError(
            f"Hai bảng có cột trùng tên ngoài khóa ghép {on}: {collide}. "
            "pandas sẽ tách thành hậu tố _x/_y và mất tên gốc. Hãy đổi tên cột "
            "trước khi ghép, hoặc truyền `on` rõ ràng."
        )

    for name, df in [("air", df_air), ("weather", df_weather)]:
        dup_count = df.duplicated(subset=on).sum()
        if dup_count > 0:
            raise ValueError(
                f"Khóa {on} không unique trong bảng {name}: "
                f"{dup_count} bản ghi trùng lặp"
            )

    df_merged = df_air.merge(df_weather, on=on, how="left", validate=validate)

    assert len(df_merged) <= len(df_air), (
        f"Row Explosion: merged ({len(df_merged)}) > air ({len(df_air)}). "
        f"Kiểm tra lại khóa ghép {on}."
    )
    assert len(df_merged) == len(df_air), (
        f"Row count drift: merged ({len(df_merged)}) != air ({len(df_air)}). "
        f"Kiểm tra lại khóa ghép {on} và tham số validate={validate!r}. "
        f"`<=` ở trên không bắt được trường hợp này."
    )

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


def export_to_parquet(
    df: pd.DataFrame,
    output_path: str | Path,
    compression: str = "snappy",
    overwrite: bool = False,
) -> None:
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

    fd, tmp_name = tempfile.mkstemp(
        dir=str(output_path.parent), suffix=".parquet.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path, compression=compression, index=False)

        df_readback = pd.read_parquet(tmp_path)

        assert len(df_readback) == original_rows, (
            f"Row count mismatch: ghi {original_rows}, đọc lại {len(df_readback)}"
        )
        assert list(df_readback.columns) == original_cols, (
            f"Schema mismatch: ghi {original_cols}, đọc lại {list(df_readback.columns)}"
        )
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


@dataclass
class DatasetFreezeInfo:

    row_count: int
    timestamp_min: pd.Timestamp
    timestamp_max: pd.Timestamp
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
    if feature_columns is None:
        excluded = {
            timestamp_col,
            station_col,
            TARGET_CANDIDATE,
            *TARGET_DERIVED_FLAGS,
            *NON_PREDICTIVE_FLAGS,
        }
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
        if any(c in df.columns for c in NON_PREDICTIVE_FLAGS):
            logger.info(
                "freeze_dataset: loại %s khỏi feature mặc định vì chưa có bằng chứng về "
                "giá trị dự báo MARGINAL trên dữ liệu thật (corr(pm25, RH) ~ -0,04; "
                "mutual information 0,0024 — thấp nhất trong các biến khí tượng). Lưu ý: "
                "cờ CÓ tương tác với mùa (F = 16,78, p = 7e-11; Đông +2,79 so với Xuân "
                "-8,91 µg/m³), nên nếu muốn khai thác thì phải dùng dạng tương tác "
                "fog × mùa — thuộc Issue #8. Xem NON_PREDICTIVE_FLAGS.",
                NON_PREDICTIVE_FLAGS,
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


def run_preprocessing_audit(
    df: pd.DataFrame,
    dataset_name: str = "canonical_dataset",
) -> Dict[str, Any]:
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
    found: Dict[str, np.ndarray] = {}

    def walk(est: Any, path: str) -> None:
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
    verify_chronology: bool = True,
    atol: float = 1e-9,
) -> None:
    if not hasattr(pipeline, "named_steps"):
        raise AssertionError("Pipeline chưa được fit!")

    preprocessor = pipeline.named_steps.get("preprocessor")
    if preprocessor is None:
        raise AssertionError("Pipeline không có bước 'preprocessor'!")

    if not hasattr(preprocessor, "named_transformers_"):
        raise AssertionError(
            "Pipeline chưa được fit: ColumnTransformer chưa có `named_transformers_`."
        )

    if not verify_chronology:
        logger.warning(
            "validate_no_leakage(verify_chronology=False): LỚP KIỂM CHỨNG THỨ TỰ "
            "THỜI GIAN ĐANG BỊ TẮT THEO YÊU CẦU. Một phép chia ngẫu nhiên sẽ KHÔNG "
            "bị phát hiện. Chỉ dùng lối tắt này cho unit test rò rỉ tham số — "
            "KHÔNG dùng với dữ liệu thật."
        )
    else:
        if timestamps is None or test_timestamps is None:
            missing = (
                "cả `timestamps` và `test_timestamps`"
                if timestamps is None and test_timestamps is None
                else "`test_timestamps`" if timestamps is not None
                else "`timestamps`"
            )
            raise AssertionError(
                f"Thiếu {missing}. Lớp kiểm chứng thứ tự thời gian là BẮT BUỘC: "
                "nó là lớp duy nhất bắt được random split, và `validate_no_leakage` "
                "không thể chứng nhận \"không rò rỉ\" khi chưa kiểm tra "
                "train.max() < test.min(). Hãy truyền cả hai; nếu thực sự chỉ muốn "
                "kiểm rò rỉ tham số thì đặt `verify_chronology=False` một cách tường "
                "minh."
            )
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
    freeze_info = freeze_dataset(
        df,
        timestamp_col=timestamp_col,
        station_col=station_col,
        feature_columns=feature_columns,
        additional_info=additional_info,
    )

    audit_results = None
    if run_audit:
        audit_results = run_preprocessing_audit(df, dataset_name="preprocessing_input")
        freeze_info.additional_info["audit"] = {
            "summary_table": audit_results["summary_table"].to_dict(),
            "six_dimensions": audit_results["six_dimensions"],
        }

    return freeze_info, audit_results
