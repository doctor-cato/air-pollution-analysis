"""
Module chuẩn hóa việc nạp, kiểm tra lược đồ và lưu trữ Snappy Parquet cho bài toán
phân tích chất lượng không khí Hà Nội (Issue #15 — Task 9.1–9.3 & Scope Extension).

Module này cung cấp lớp giao diện dùng chung cho cả hai chế độ dữ liệu:
  - Baseline ``VN001`` (`1.0.0-m2-baseline`, `data/processed/air_pollution_final.parquet`)
  - Extended tách trạm ``VN001_extended`` / ``VN003_extended`` (`2.0.0-issue44-extended`,
    `data/processed/air_pollution_extended_2022_2026.parquet`)

Nguyên tắc thiết kế (fail-closed):
  - Không gây phụ thuộc vòng tròn: chỉ sử dụng thư viện chuẩn, `numpy` và `pandas`.
  - Bắt buộc hiện diện khóa `station_id` hợp lệ (không rỗng, không `NaN`, không khoảng trắng)
    và duy nhất cặp `(station_id, timestamp)`.
  - Tách biệt đường dẫn output theo từng cohort/phiên bản để không bao giờ ghi đè
    artifact baseline.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple, Union

import pandas as pd

REPO_ROOT: Path = Path(__file__).resolve().parent.parent

BASELINE_DATASET_PATH: Path = Path("data/processed/air_pollution_final.parquet")
EXTENDED_DATASET_PATH: Path = Path("data/processed/air_pollution_extended_2022_2026.parquet")

VN001_STATION_ID: str = "VN001_HANOI_556_NGUYEN_VAN_CU"
VN003_STATION_ID: str = "VN003_HANOI_OPENAQ_7441"

BASELINE_REQUIRED_COLUMNS: Tuple[str, ...] = (
    "timestamp",
    "station_id",
    "location",
    "pm25",
    "pm10",
    "pm25_was_stuck",
    "pm25_was_missing",
    "is_high_humidity_fog",
    "temperature",
    "relative_humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "surface_pressure",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
)

EXTENDED_EXTRA_COLUMNS: Tuple[str, ...] = (
    "split",
    "pm25_derived_interpolated",
    "pm25_is_derived",
    "winter_year",
    "season",
)

EXTENDED_REQUIRED_COLUMNS: Tuple[str, ...] = (
    BASELINE_REQUIRED_COLUMNS + EXTENDED_EXTRA_COLUMNS
)


@dataclass(frozen=True)
class DatasetCohortConfig:
    """Cấu hình bất biến mô tả một cohort dữ liệu tách theo trạm và phiên bản."""

    name: str
    station_id: str
    dataset_version: str
    input_path: Path
    output_dir: Path
    split_timestamp: str
    required_columns: Tuple[str, ...]
    description: str


COHORT_CONFIGS: Dict[str, DatasetCohortConfig] = {
    "vn001_baseline": DatasetCohortConfig(
        name="vn001_baseline",
        station_id=VN001_STATION_ID,
        dataset_version="1.0.0-m2-baseline",
        input_path=BASELINE_DATASET_PATH,
        output_dir=Path("reports/cohorts/vn001_baseline"),
        split_timestamp="2026-01-15 00:00:00+07:00",
        required_columns=BASELINE_REQUIRED_COLUMNS,
        description="Baseline VN001 (556 Nguyen Van Cu, 2025-07 to 2026-07, Issue #7 frozen split).",
    ),
    "vn001_extended": DatasetCohortConfig(
        name="vn001_extended",
        station_id=VN001_STATION_ID,
        dataset_version="2.0.0-issue44-extended",
        input_path=EXTENDED_DATASET_PATH,
        output_dir=Path("reports/cohorts/vn001_extended"),
        split_timestamp="2026-05-01 09:00:00+07:00",
        required_columns=EXTENDED_REQUIRED_COLUMNS,
        description="Extended cohort VN001 (80/20 intra-station chronological split).",
    ),
    "vn003_extended": DatasetCohortConfig(
        name="vn003_extended",
        station_id=VN003_STATION_ID,
        dataset_version="2.0.0-issue44-extended",
        input_path=EXTENDED_DATASET_PATH,
        output_dir=Path("reports/cohorts/vn003_extended"),
        split_timestamp="2024-08-13 23:00:00+07:00",
        required_columns=EXTENDED_REQUIRED_COLUMNS,
        description="Extended historical cohort VN003 (OpenAQ 7441, 2022-01 to 2025-04, 80/20 split).",
    ),
}


def get_cohort_config(cohort_name: str) -> DatasetCohortConfig:
    """Trả về cấu hình cohort bất biến theo tên chuẩn."""
    if cohort_name not in COHORT_CONFIGS:
        valid = ", ".join(sorted(COHORT_CONFIGS))
        raise KeyError(
            f"Unknown cohort '{cohort_name}'. Expected one of: {valid}"
        )
    return COHORT_CONFIGS[cohort_name]


def compute_file_sha256(path: Union[str, Path]) -> str:
    """Tính mã băm SHA-256 (hex lowercase) cho một tệp tồn tại trên đĩa."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Cannot hash missing file: {file_path}")
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_canonical_schema(
    df: pd.DataFrame,
    required_columns: Sequence[str] = BASELINE_REQUIRED_COLUMNS,
    require_tz_aware: bool = True,
) -> None:
    """Kiểm tra lược đồ cột bắt buộc, kiểu thời gian và tính duy nhất khóa."""
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Expected pandas.DataFrame, got {type(df).__name__}")
    if df.empty:
        raise ValueError("Dataset cannot be empty.")

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required canonical columns: {missing_cols}")

    ts = df["timestamp"]
    if not isinstance(ts.dtype, pd.DatetimeTZDtype):
        if pd.api.types.is_datetime64_any_dtype(ts):
            if require_tz_aware:
                raise ValueError(
                    "Column 'timestamp' must be timezone-aware (Asia/Ho_Chi_Minh)."
                )
        else:
            raise ValueError(
                f"Column 'timestamp' must have datetime dtype, got {ts.dtype}."
            )

    if ts.isna().any():
        raise ValueError("Column 'timestamp' contains NaT/null values.")


def enforce_station_key(
    df: pd.DataFrame,
    expected_station_id: Optional[str] = None,
    allow_multi_station: bool = False,
) -> pd.DataFrame:
    """
    Kiểm tra và chuẩn hóa phạm vi `station_id` theo chế độ fail-closed.

    - Từ chối nếu thiếu cột `station_id`, có giá trị `NaN` hoặc chuỗi rỗng.
    - Từ chối nếu phát hiện > 1 trạm khi `expected_station_id is None` và `not allow_multi_station`.
    - Từ chối nếu tồn tại bản ghi trùng khóa `(station_id, timestamp)`.
    - Trả về bản sao đã sắp xếp tăng dần theo `['station_id', 'timestamp']`.
    """
    if "station_id" not in df.columns:
        raise ValueError("Missing mandatory key column 'station_id'.")
    if "timestamp" not in df.columns:
        raise ValueError("Missing mandatory key column 'timestamp'.")

    if df["station_id"].isna().any():
        raise ValueError("Column 'station_id' contains null/NaN values.")

    station_strs = df["station_id"].astype(str).str.strip()
    if (station_strs == "").any():
        raise ValueError("Column 'station_id' contains blank/whitespace values.")

    work = df.copy()
    work["station_id"] = station_strs

    if expected_station_id is not None:
        target = expected_station_id.strip()
        if not target:
            raise ValueError("expected_station_id cannot be blank.")
        work = work.loc[work["station_id"] == target].copy()
        if work.empty:
            raise ValueError(
                f"Station '{target}' not found in dataset (available: {sorted(station_strs.unique())})."
            )
    elif not allow_multi_station:
        unique_stations = sorted(work["station_id"].unique())
        if len(unique_stations) != 1:
            raise ValueError(
                "Single-station mode refuses mixed stations "
                f"{unique_stations}; pass expected_station_id or allow_multi_station=True."
            )

    if work.duplicated(subset=["station_id", "timestamp"]).any():
        n_dup = int(work.duplicated(subset=["station_id", "timestamp"]).sum())
        raise ValueError(
            f"Duplicate (station_id, timestamp) keys detected: {n_dup} rows."
        )

    return work.sort_values(["station_id", "timestamp"], kind="mergesort").reset_index(drop=True)


def load_processed_parquet(
    path: Union[str, Path],
    required_columns: Sequence[str] = BASELINE_REQUIRED_COLUMNS,
    station_id: Optional[str] = None,
    allow_multi_station: bool = False,
) -> pd.DataFrame:
    """Đọc tệp Parquet đã xử lý và chạy đầy đủ các chốt kiểm tra schema/khóa trạm."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Processed Parquet file not found: {file_path}")

    df = pd.read_parquet(file_path)
    validate_canonical_schema(df, required_columns=required_columns)
    return enforce_station_key(
        df,
        expected_station_id=station_id,
        allow_multi_station=allow_multi_station,
    )


def load_cohort(
    cohort_name: str,
    base_dir: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, DatasetCohortConfig]:
    """
    Nạp dữ liệu cho một cohort chuẩn (`vn001_baseline`, `vn001_extended`, `vn003_extended`).

    Đảm bảo tách trạm độc lập và kiểm tra tính tuần tự của cột `split` nếu có.
    """
    config = get_cohort_config(cohort_name)
    root = Path(base_dir) if base_dir is not None else REPO_ROOT
    parquet_path = config.input_path if config.input_path.is_absolute() else root / config.input_path

    df = load_processed_parquet(
        parquet_path,
        required_columns=config.required_columns,
        station_id=config.station_id,
        allow_multi_station=False,
    )

    if "split" in df.columns:
        split_vals = set(df["split"].dropna().astype(str).unique())
        if not split_vals.issubset({"train", "test"}) or split_vals != {"train", "test"}:
            raise ValueError(
                f"Cohort '{cohort_name}' must contain both 'train' and 'test' splits; found {sorted(split_vals)}."
            )
        train_max = df.loc[df["split"] == "train", "timestamp"].max()
        test_min = df.loc[df["split"] == "test", "timestamp"].min()
        if not (train_max < test_min):
            raise ValueError(
                f"Chronological split leakage in '{cohort_name}': train_max={train_max} >= test_min={test_min}."
            )

    return df, config


def write_parquet_snappy(
    df: pd.DataFrame,
    output_path: Union[str, Path],
    allow_overwrite: bool = True,
) -> str:
    """
    Ghi DataFrame ra Snappy Parquet một cách nguyên tử (atomic replace) và trả về SHA-256.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("Cannot write empty or non-DataFrame object to Parquet.")

    if {"station_id", "timestamp"}.issubset(df.columns):
        if df.duplicated(subset=["station_id", "timestamp"]).any():
            raise ValueError("Cannot write Parquet with duplicate (station_id, timestamp) keys.")

    target = Path(output_path)
    if target.exists() and not allow_overwrite:
        raise FileExistsError(f"Refusing to overwrite existing Parquet file: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.stem}_", suffix=".parquet.tmp", dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path, engine="pyarrow", compression="snappy", index=False)
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return compute_file_sha256(target)
