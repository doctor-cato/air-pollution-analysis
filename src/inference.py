"""
Issue #11 — Suy luận thống kê: kiểm định giả thuyết có đối chứng cho PM2.5 Hà Nội.

VÌ SAO CÓ MODULE NÀY
--------------------
Trước Issue #11, repo chỉ có thống kê **mô tả** (Issue #8) và hình ảnh giải thích
(Issue #9). Mọi câu hỏi dạng "có khác biệt không" vẫn chưa có p-value nào được
tính. Module này là **một chỗ duy nhất** sinh ra toàn bộ suy luận của W9:

  * `notebooks/05_statistical_inference.ipynb` gọi `run_inference()` rồi
    `render_inference_report()` — notebook **không** tự tính lại con số nào.
  * `reports/inference_results.md` là output của `render_inference_report()`.
  * `tests/test_inference.py` kiểm **hành vi** của từng phép kiểm trên dữ liệu
    tổng hợp đã biết trước đáp án, không kiểm chuỗi số trong báo cáo.

BA QUYẾT ĐỊNH PHƯƠNG PHÁP ĐÓNG BĂNG TẠI ĐÂY
-------------------------------------------
1. **Đơn vị phân tích là NGÀY, không phải GIỜ.** ACF bậc 1 của chuỗi giờ xấp xỉ
   0,94; coi 9.044 giờ là 9.044 quan sát độc lập sẽ thổi phồng cỡ mẫu lên
   khoảng 30 lần và biến mọi p-value thành vô nghĩa. Một ngày chỉ được giữ khi
   có **≥ 18/24 giờ** đo được (tiêu chí độ phủ 75% — **lựa chọn phân tích của
   dự án**, không phải điều khoản của QCVN).
2. **Khoảng tin cậy dùng circular moving block bootstrap**, block 7 ngày,
   1.000 lặp, seed 42, CI percentile. Không bootstrap từng hàng giờ, cũng không
   bootstrap độc lập từng ngày — cả hai đều phá cấu trúc tự tương quan.
   Với so sánh hai nhóm, mỗi nhóm được resample **theo block riêng** (stratified)
   để giữ nguyên cỡ mẫu từng nhóm.
3. **Bốn kiểm định xác nhận được hiệu chỉnh Holm trong CÙNG một family**; sáu cặp
   mùa hậu định là family **riêng** và mang nhãn *exploratory*. Các kiểm tra độ
   nhạy không nằm trong family nào — chỉ báo p thô và nói rõ là thăm dò.

GIỚI HẠN CỦA VIỆC KHÔNG DÙNG TRAIN/TEST SPLIT
---------------------------------------------
Các phép kiểm ở đây **không fit mô hình**, không chọn siêu tham số, không đánh
giá hiệu năng dự báo, nên không có nguy cơ rò rỉ thông tin từ Test sang Train.
Vì vậy chúng chạy trên **toàn bộ giai đoạn quan sát** để tận dụng cỡ mẫu — riêng
một kiểm định QCVN trung bình năm vốn cần trọn chu kỳ. Điểm cắt
`2026-01-15 00:00+07:00` của Issue #7 **không bị thay đổi** ở đây và vẫn là điểm
cắt duy nhất cho mọi mô hình ở Issue #12–#13.

ĐIỀU KHÔNG ĐƯỢC LÀM VỚI MODULE NÀY
----------------------------------
* Không chọn alternative/direction sau khi nhìn thấy p (mọi kiểm định xác nhận
  đều **hai phía**; chiều của hiệu ứng đọc từ ước lượng và CI).
* Không hardcode số liệu: mọi con số trong báo cáo đi ra từ `run_inference()`.
* Không kết luận "đạt/không đạt QCVN": quy chuẩn có quy tắc thống kê riêng
  (số ngày vượt được phép) mà dự án **không** mã hoá. Module chỉ báo tần suất
  vượt ngưỡng và kiểm định vị trí phân phối so với ngưỡng.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from src.flag_evidence import (
    SEASON_DISPLAY_ORDER,
    SEASON_LABELS_VI,
    SEASON_MONTHS,
    format_int_vi,
    format_number_vi,
    format_scientific_vi,
)

# ---------------------------------------------------------------------------
# Hằng số — nguồn sự thật duy nhất cho Issue #11
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_PATH: Path = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
DEFAULT_REPORT_PATH: Path = REPO_ROOT / "reports" / "inference_results.md"

TIMESTAMP_COLUMN = "timestamp"
TARGET_COLUMN = "pm25"
STATION_COLUMN = "station_id"
LOCAL_TZ = "Asia/Ho_Chi_Minh"

#: Mức ý nghĩa chốt trước khi nhìn dữ liệu.
ALPHA: float = 0.05
CONFIDENCE_LEVEL: float = 0.95

#: Số lặp bootstrap và seed cố định (tái lập tuyệt đối).
N_BOOTSTRAP: int = 1_000
BOOTSTRAP_SEED: int = 42

#: Độ dài block (ngày). Bằng đúng một chu kỳ tuần — ACF(7) của chuỗi ngày là 0,46,
#: nên block 7 ngày giữ được phần lớn cấu trúc tự tương quan ngắn hạn.
BLOCK_LENGTH_DAYS: int = 7

#: Tiêu chí độ phủ tối thiểu để một ngày được coi là "có trung bình ngày".
#: 18/24 = 75% — **lựa chọn phân tích của dự án**, không trích dẫn như điều khoản QCVN.
MIN_VALID_HOURS_PER_DAY: int = 18
HOURS_PER_DAY: int = 24

#: Ngưỡng QCVN 05:2023/BTNMT cho PM2.5 (µg/m³), tách bạch theo chu kỳ lấy mẫu.
QCVN_2023_PM25_24H_LIMIT: float = 50.0
QCVN_2023_PM25_ANNUAL_LIMIT: float = 25.0

#: Nhãn chu kỳ lấy mẫu — in kèm mọi ngưỡng để không ai đọc nhầm 24h thành năm.
QCVN_24H_LABEL = "QCVN 05:2023/BTNMT — trung bình 24 giờ"
QCVN_ANNUAL_LABEL = "QCVN 05:2023/BTNMT — trung bình năm"

#: Yêu cầu tối thiểu cho kiểm tra độ nhạy ghép cặp theo tuần.
PAIRED_MIN_WEEKDAYS: int = 3
PAIRED_MIN_WEEKEND_DAYS: int = 2

#: Ngưỡng mô tả hình dạng phân phối (dùng cho phần diễn giải, không phải kiểm định).
SKEW_MODERATE: float = 0.5
SKEW_SUBSTANTIAL: float = 1.0

#: Số bậc tự tương quan in ra báo cáo.
ACF_LAGS_DAILY: Tuple[int, ...] = (1, 2, 3, 7, 14)
ACF_LAGS_HOURLY: Tuple[int, ...] = (1, 2, 3, 24, 168)

#: Nhãn hiển thị cho effect size — bảng báo cáo dùng nhãn này thay tên biến thô.
EFFECT_SIZE_LABELS: Dict[str, str] = {
    "r_rb": "r_rb",
    "r_rb_pairs": "r (cặp)",
    "epsilon_squared": "ε²",
    "cohen_d": "Cohen's d",
}


# ---------------------------------------------------------------------------
# Nạp dữ liệu
# ---------------------------------------------------------------------------


def _require_columns(df: pd.DataFrame, columns: Sequence[str], *, context: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise KeyError(
            f"{context}: thiếu cột {missing}. Cột hiện có: {list(df.columns)}. "
            "Chạy notebook 03 (transformation pipeline) để sinh "
            "`data/processed/air_pollution_final.parquet`."
        )


def _local_timestamps(values: pd.Series) -> pd.Series:
    """Chuyển cột thời gian về datetime tz-aware `Asia/Ho_Chi_Minh`, fail loudly."""
    ts = pd.to_datetime(values, errors="raise")
    n_nat = int(ts.isna().sum())
    if n_nat:
        raise ValueError(
            f"Cột thời gian có {n_nat} giá trị NaT — không dựng được lưới ngày."
        )
    if ts.dt.tz is None:
        return ts.dt.tz_localize(LOCAL_TZ)
    return ts.dt.tz_convert(LOCAL_TZ)


def load_analysis_frame(path: Optional[Path] = None) -> pd.DataFrame:
    """
    Đọc dataset đã đóng băng của Issue #7 và chuẩn hoá thời gian.

    Chỉ **đọc**; không sửa `data/`. Raises `FileNotFoundError` nếu thiếu tệp.
    """
    data_path = Path(path) if path is not None else DEFAULT_DATA_PATH
    if not data_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {data_path}. Chạy `python scripts/fetch_dataset.py` "
            "rồi notebook 01 → 03 để tái tạo dataset."
        )
    df = pd.read_parquet(data_path)
    _require_columns(
        df, [TIMESTAMP_COLUMN, TARGET_COLUMN], context="load_analysis_frame"
    )
    out = df.copy()
    out[TIMESTAMP_COLUMN] = _local_timestamps(out[TIMESTAMP_COLUMN])
    out[TARGET_COLUMN] = pd.to_numeric(out[TARGET_COLUMN], errors="coerce")
    return out


def dataset_sha256(path: Optional[Path] = None) -> str:
    """SHA-256 của tệp Parquet nguồn — bằng chứng báo cáo ứng với đúng dữ liệu nào."""
    data_path = Path(path) if path is not None else DEFAULT_DATA_PATH
    return hashlib.sha256(data_path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Dựng panel ngày
# ---------------------------------------------------------------------------


def _season_from_month(month: pd.Series) -> pd.Series:
    season = month.map(SEASON_MONTHS)
    if season.isna().any():  # pragma: no cover - tháng luôn trong 1..12
        raise ValueError("Có tháng không nằm trong 1..12 nên chưa gán được mùa.")
    return season


def build_daily_panel(
    df: pd.DataFrame,
    *,
    min_valid_hours: int = MIN_VALID_HOURS_PER_DAY,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Tổng hợp chuỗi giờ thành panel **một dòng một ngày** và trả kèm nhật ký lọc.

    Quy tắc: một ngày được giữ khi có `min_valid_hours` giờ (mặc định 18) có
    `pm25` khác NaN. Nếu dữ liệu có nhiều trạm, mỗi ngày là **trung bình các trạm**
    (ghi lại `n_stations`) — hiện tại dữ liệu chỉ có một trạm.

    Returns
    -------
    (panel, audit)
        `panel` sắp theo thời gian, cột: `date`, `pm25_mean`, `pm25_median`,
        `valid_hours`, `season`, `is_weekend`, `day_of_week`, `iso_year`, `iso_week`.
    """
    if not 1 <= min_valid_hours <= HOURS_PER_DAY:
        raise ValueError(
            f"min_valid_hours phải trong [1, {HOURS_PER_DAY}], nhận {min_valid_hours}."
        )
    _require_columns(df, [TIMESTAMP_COLUMN, TARGET_COLUMN], context="build_daily_panel")

    work = df.copy()
    work[TIMESTAMP_COLUMN] = _local_timestamps(work[TIMESTAMP_COLUMN])
    work[TARGET_COLUMN] = pd.to_numeric(work[TARGET_COLUMN], errors="coerce")
    work["_date"] = work[TIMESTAMP_COLUMN].dt.normalize()

    n_stations = int(work[STATION_COLUMN].nunique()) if STATION_COLUMN in work else 1
    rows_total = len(work)
    observed = work.dropna(subset=[TARGET_COLUMN])
    if observed.empty:
        raise ValueError("Không có giờ nào có `pm25` — không dựng được panel ngày.")

    per_day = observed.groupby("_date", observed=True)[TARGET_COLUMN].agg(
        valid_hours="size", pm25_mean="mean", pm25_median="median"
    )
    per_day = per_day.sort_index()

    keep = per_day["valid_hours"] >= min_valid_hours
    panel = per_day.loc[keep].copy()
    if panel.empty:
        raise ValueError(
            f"Không ngày nào đạt ≥ {min_valid_hours} giờ có `pm25`. Panel rỗng — "
            "không kiểm định được."
        )

    panel = panel.rename(columns={"pm25_mean": "pm25_mean", "pm25_median": "pm25_median"})
    panel["date"] = panel.index
    panel["season"] = _season_from_month(panel["date"].dt.month)
    panel["day_of_week"] = panel["date"].dt.dayofweek
    panel["is_weekend"] = (panel["day_of_week"] >= 5).astype(int)
    iso = panel["date"].dt.isocalendar()
    panel["iso_year"] = iso["year"].astype(int)
    panel["iso_week"] = iso["week"].astype(int)
    panel["week_key"] = (
        panel["iso_year"].astype(str) + "-W" + panel["iso_week"].astype(str).str.zfill(2)
    )
    panel = panel.reset_index(drop=True)

    dropped = per_day.loc[~keep, "valid_hours"]
    span_days = int((per_day.index.max() - per_day.index.min()).days) + 1
    audit: Dict[str, Any] = {
        "rows_hourly": rows_total,
        "hours_with_pm25": len(observed),
        "hours_missing_pm25": rows_total - len(observed),
        "n_stations": n_stations,
        "span_days": span_days,
        "days_with_any_observation": len(per_day),
        "days_full_24h": int((per_day["valid_hours"] == HOURS_PER_DAY).sum()),
        "min_valid_hours": min_valid_hours,
        "days_kept": len(panel),
        "days_dropped": len(dropped),
        "dropped_dates": [str(d.date()) for d in dropped.index],
        "coverage_first": str(panel["date"].min().date()),
        "coverage_last": str(panel["date"].max().date()),
        "observed_first": str(per_day.index.min().date()),
        "observed_last": str(per_day.index.max().date()),
        "season_counts": {
            SEASON_LABELS_VI[s]: int(n) for s, n in panel["season"].value_counts().items()
        },
        "weekday_days": int((panel["is_weekend"] == 0).sum()),
        "weekend_days": int((panel["is_weekend"] == 1).sum()),
    }
    return panel, audit


# ---------------------------------------------------------------------------
# Chẩn đoán phân phối
# ---------------------------------------------------------------------------


def _shape_words(skewness: float, excess_kurtosis: float) -> str:
    if abs(skewness) < SKEW_MODERATE:
        skew_word = "gần đối xứng"
    elif abs(skewness) < SKEW_SUBSTANTIAL:
        skew_word = "lệch vừa"
    else:
        skew_word = "lệch mạnh"
    direction = "phải" if skewness > 0 else "trái"
    tail = (
        "đuôi dày hơn chuẩn"
        if excess_kurtosis > 0.5
        else ("đuôi mỏng hơn chuẩn" if excess_kurtosis < -0.5 else "độ nhọn gần chuẩn")
    )
    return f"{skew_word} về phía {direction}, {tail}"


def distribution_diagnostics(values: Sequence[float]) -> Dict[str, Any]:
    """
    Mô tả hình dạng phân phối + hai kiểm định chuẩn tắc, **không** kết luận sẵn.

    Vì sao cần cả hai: Shapiro-Wilk có power rất cao với n lớn — n = 299 là đủ để
    bác bỏ "chuẩn" chỉ vì lệch 0,1. Vì vậy báo cáo thêm D'Agostino K² và buộc
    người đọc diễn giải **cỡ hiệu ứng hình dạng** (skewness, kurtosis) chứ không
    chỉ đọc p. Việc chọn phép kiểm phi tham số ở đây dựa trên **cả** hình dạng
    thực nghiệm **và** bản chất thang đo (nồng độ bị chặn dưới 0, có outlier),
    không dựa riêng vào một p-value.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát để chẩn đoán, nhận {x.size}.")

    shapiro_w, shapiro_p = stats.shapiro(x)
    dag_stat, dag_p = stats.normaltest(x)
    q1, q3 = np.percentile(x, [25, 75])
    skewness = float(stats.skew(x, bias=False))
    excess = float(stats.kurtosis(x, fisher=True, bias=False))

    return {
        "n": int(x.size),
        "mean": float(x.mean()),
        "sd": float(x.std(ddof=1)),
        "median": float(np.median(x)),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
        "min": float(x.min()),
        "max": float(x.max()),
        "skewness": skewness,
        "excess_kurtosis": excess,
        "shape": _shape_words(skewness, excess),
        "shapiro_w": float(shapiro_w),
        "shapiro_p": float(shapiro_p),
        "dagostino_stat": float(dag_stat),
        "dagostino_p": float(dag_p),
        "n_outliers_3sd": int((np.abs(x - x.mean()) > 3 * x.std(ddof=1)).sum()),
    }


def qq_points(values: Sequence[float]) -> pd.DataFrame:
    """
    Toạ độ Q-Q plot so với phân phối chuẩn (plotting positions Blom).

    Trả về DataFrame `theoretical`, `sample` để notebook vẽ — không vẽ ở đây để
    `src/` không phụ thuộc Matplotlib backend.
    """
    x = np.sort(np.asarray(values, dtype=float))
    x = x[np.isfinite(x)]
    n = x.size
    if n < 3:
        raise ValueError(f"Cần ≥ 3 quan sát để vẽ Q-Q, nhận {n}.")
    positions = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
    theoretical = stats.norm.ppf(positions)
    standardized = (x - x.mean()) / x.std(ddof=1)
    return pd.DataFrame({"theoretical": theoretical, "sample": standardized})


# ---------------------------------------------------------------------------
# Tự tương quan & cỡ mẫu hiệu dụng
# ---------------------------------------------------------------------------


def autocorrelation(values: Sequence[float], max_lag: int = 1) -> np.ndarray:
    """
    ACF mẫu (không hiệu chỉnh) tới `max_lag`, bỏ qua NaN theo từng cặp.

    Tự tính bằng numpy thay vì gọi statsmodels để hàm thuần, không phụ thuộc
    trạng thái model — và để test có thể so với công thức corr(x[:-k], x[k:]).
    """
    x = np.asarray(values, dtype=float)
    if x.size < 3:
        raise ValueError("Cần ≥ 3 quan sát để tính ACF.")
    if max_lag < 1 or max_lag >= x.size:
        raise ValueError(f"max_lag phải trong [1, {x.size - 1}], nhận {max_lag}.")

    out = np.empty(max_lag + 1, dtype=float)
    out[0] = 1.0
    for lag in range(1, max_lag + 1):
        a, b = x[:-lag], x[lag:]
        mask = np.isfinite(a) & np.isfinite(b)
        if mask.sum() < 3:
            out[lag] = np.nan
            continue
        left, right = a[mask], b[mask]
        # np.corrcoef chia cho SD = 0 khi một phía là hằng số; trả NaN tường minh
        # thay vì để numpy phát RuntimeWarning rồi vẫn ra NaN.
        if np.std(left) == 0.0 or np.std(right) == 0.0:
            out[lag] = np.nan
            continue
        out[lag] = float(np.corrcoef(left, right)[0, 1])
    return out


def effective_sample_size(values: Sequence[float]) -> Dict[str, float]:
    """
    Cỡ mẫu hiệu dụng theo xấp xỉ AR(1): ``n_eff = n · (1 − ρ) / (1 + ρ)``.

    Đây là **chỉ báo bậc độ lớn**, không phải hiệu chỉnh p-value. Nó trả lời câu
    "299 ngày này chứa bao nhiêu thông tin độc lập?" — nếu n_eff nhỏ hơn nhiều so
    với n thì p-value của các phép kiểm giả định độc lập là **lạc quan**.
    """
    x = np.asarray(values, dtype=float)
    n = int(np.isfinite(x).sum())
    if n < 10:
        raise ValueError("Cần ≥ 10 quan sát để ước lượng AR(1).")
    if x.size < 3:
        raise ValueError("Cần ≥ 3 vị trí để tính ACF bậc 1.")
    # Giữ nguyên vị trí NaN: với chuỗi dày (một phần tử mỗi ngày) ACF bậc 1 mới
    # thực sự là tương quan giữa hai ngày liền kề. Nếu nén bỏ NaN trước, một cặp
    # "lag 1" có thể là hai ngày cách nhau nhiều ngày và ρ bị chệch.
    rho = float(autocorrelation(x, 1)[1])
    if math.isnan(rho):
        # Chuỗi hằng: phương sai bằng 0 nên tương quan không xác định. Về mặt
        # thông tin, một chuỗi không đổi chứa đúng một bậc tự do — xử lý như
        # tương quan hoàn hảo thay vì để NaN lan sang n_eff.
        finite = x[np.isfinite(x)]
        if finite.size >= 3 and np.allclose(finite, finite[0]):
            rho = 0.999999
        else:
            raise ValueError("ρ bậc 1 không xác định: không đủ cặp giá trị hữu hạn.")
    if not math.isfinite(rho) or rho <= -1.0:
        raise ValueError(f"ρ bậc 1 không hợp lệ: {rho}.")
    if rho >= 1.0:
        rho = 0.999999  # chuỗi hằng — n_eff tiến về 0
    n_eff = n * (1.0 - rho) / (1.0 + rho)
    return {
        "n": n,
        "rho_lag1": rho,
        "n_effective": float(n_eff),
        "inflation_factor": float(n / n_eff) if n_eff > 0 else float("inf"),
    }


def dense_daily_series(
    panel: pd.DataFrame, *, value_col: str = "pm25_mean"
) -> np.ndarray:
    """
    Chuỗi giá trị ngày trên **lưới lịch đầy đủ** — ngày bị loại thành NaN.

    Vì sao cần: panel chỉ giữ ngày đủ độ phủ, nên hai dòng liền nhau có thể cách
    nhau vài ngày. Tính ACF trên vector đã nén sẽ ghép các ngày không liền kề và
    làm ρ chệch. Hàm này giữ đúng vị trí thời gian để `autocorrelation()` bỏ qua
    cặp NaN chứ không bỏ qua khoảng trống.
    """
    if "date" not in panel or value_col not in panel:
        raise KeyError(f"dense_daily_series thiếu cột 'date' hoặc {value_col!r}.")
    series = panel.set_index("date")[value_col].sort_index()
    grid = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(grid).to_numpy(dtype=float)


def minimum_detectable_difference(
    group_a: Sequence[float],
    group_b: Sequence[float],
    *,
    alpha: float = ALPHA,
    power: float = 0.80,
) -> Dict[str, float]:
    """
    Chênh lệch nhỏ nhất phát hiện được (MDE) cho hai trung bình, xấp xỉ chuẩn.

    Công thức: ``(z_{1−α/2} + z_{power}) · s_pooled · sqrt(1/n₁ + 1/n₂)``.
    Đây là **tính toán hậu nghiệm dựa trên SD quan sát**, không phải phân tích
    power tiên nghiệm; mục đích là để câu "p > 0,05" không bị đọc thành "không có
    hiệu ứng". Nếu chênh lệch quan sát nhỏ hơn MDE, phép kiểm không đủ độ phân
    giải để phân biệt "không có hiệu ứng" với "hiệu ứng nhỏ hơn MDE".
    """
    a = np.asarray(group_a, dtype=float)
    b = np.asarray(group_b, dtype=float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        raise ValueError("MDE cần ≥ 2 quan sát mỗi nhóm.")
    if not 0.0 < alpha < 1.0 or not 0.0 < power < 1.0:
        raise ValueError("alpha và power phải trong (0, 1).")
    n1, n2 = a.size, b.size
    pooled_var = ((n1 - 1) * a.var(ddof=1) + (n2 - 1) * b.var(ddof=1)) / (n1 + n2 - 2)
    z_alpha = float(stats.norm.ppf(1.0 - alpha / 2.0))
    z_power = float(stats.norm.ppf(power))
    mde = (z_alpha + z_power) * math.sqrt(pooled_var) * math.sqrt(1.0 / n1 + 1.0 / n2)
    return {
        "alpha": float(alpha),
        "power": float(power),
        "n_a": int(n1),
        "n_b": int(n2),
        "pooled_sd": float(math.sqrt(pooled_var)),
        "mde": float(mde),
    }


# ---------------------------------------------------------------------------
# Hiệu chỉnh đa kiểm định
# ---------------------------------------------------------------------------


def holm_adjust(pvalues: Sequence[float]) -> np.ndarray:
    """
    Hiệu chỉnh Holm–Bonferroni, giữ nguyên thứ tự đầu vào.

    Holm kiểm soát FWER mà không giả định các kiểm định độc lập, và luôn mạnh hơn
    (hoặc bằng) Bonferroni — đó là lý do chọn Holm thay vì Bonferroni thuần.
    """
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1 or p.size == 0:
        raise ValueError("holm_adjust cần một vector p-value không rỗng.")
    if np.any(~np.isfinite(p)) or np.any(p < 0.0) or np.any(p > 1.0):
        raise ValueError(f"p-value phải trong [0, 1] và hữu hạn, nhận {p.tolist()}.")

    m = p.size
    order = np.argsort(p, kind="mergesort")
    adjusted_sorted = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order, start=1):
        candidate = min(1.0, (m - rank + 1) * p[idx])
        running = max(running, candidate)
        adjusted_sorted[rank - 1] = running

    adjusted = np.empty(m, dtype=float)
    adjusted[order] = adjusted_sorted
    return adjusted


# ---------------------------------------------------------------------------
# Bootstrap khối
# ---------------------------------------------------------------------------


def circular_block_indices(
    n: int,
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> np.ndarray:
    """
    Chỉ số cho circular moving block bootstrap, shape `(n_bootstrap, n)`.

    Vì sao circular: chuỗi ngày có điểm đầu/điểm cuối, block ở biên sẽ ngắn hơn
    các block khác nếu cắt cứng. Nối vòng giữ mọi block đúng `block_length` quan
    sát và giữ phân phối biên của chuỗi gốc.
    """
    if n < 2:
        raise ValueError(f"Cần ≥ 2 quan sát để bootstrap, nhận {n}.")
    if not 1 <= block_length <= n:
        raise ValueError(f"block_length phải trong [1, {n}], nhận {block_length}.")
    if n_bootstrap < 1:
        raise ValueError(f"n_bootstrap phải ≥ 1, nhận {n_bootstrap}.")

    rng = np.random.default_rng(seed)
    n_blocks = int(math.ceil(n / block_length))
    starts = rng.integers(0, n, size=(n_bootstrap, n_blocks))
    offsets = np.arange(block_length)
    idx = (starts[:, :, None] + offsets[None, None, :]) % n
    return idx.reshape(n_bootstrap, n_blocks * block_length)[:, :n]


def _percentile_ci(replicates: np.ndarray) -> Tuple[float, float]:
    lower = (1.0 - CONFIDENCE_LEVEL) / 2.0 * 100.0
    upper = 100.0 - lower
    lo, hi = np.percentile(replicates, [lower, upper])
    return float(lo), float(hi)


def bootstrap_ci(
    values: Sequence[float],
    *,
    statistic: str = "median",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """CI percentile cho một thống kê của **một** chuỗi (block bootstrap)."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        raise ValueError(f"Cần ≥ 5 quan sát để bootstrap CI, nhận {x.size}.")
    reducer = {"median": np.median, "mean": np.mean}.get(statistic)
    if reducer is None:
        raise ValueError(f"statistic phải là 'median' hoặc 'mean', nhận {statistic!r}.")

    # Block không thể dài hơn chuỗi; với mẫu ngắn hơn block_length, dùng nguyên
    # chuỗi làm một block (bootstrap sẽ thoái hoá thành tái lấy mẫu toàn bộ).
    block = min(block_length, x.size)
    idx = circular_block_indices(
        x.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed
    )
    replicates = reducer(x[idx], axis=1)
    lo, hi = _percentile_ci(replicates)
    return {
        "statistic": statistic,
        "point": float(reducer(x)),
        "ci_low": lo,
        "ci_high": hi,
        "n_bootstrap": n_bootstrap,
        "block_length": block,
        "seed": seed,
        "replicates_sd": float(replicates.std(ddof=1)),
    }


def bootstrap_difference_ci(
    a: Sequence[float],
    b: Sequence[float],
    *,
    statistic: str = "median",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    CI percentile cho `thống kê(a) − thống kê(b)`, resample **theo block từng nhóm**.

    Stratified (không gộp chung) để cỡ mẫu hai nhóm được giữ nguyên trong mọi lặp;
    cái giá là bỏ qua tương quan chéo nhóm, nên đi kèm kiểm tra độ nhạy ghép cặp
    theo tuần ở `paired_weekly_differences()`.
    """
    xa = np.asarray(a, dtype=float)
    xa = xa[np.isfinite(xa)]
    xb = np.asarray(b, dtype=float)
    xb = xb[np.isfinite(xb)]
    if xa.size < 5 or xb.size < 5:
        raise ValueError(
            f"Mỗi nhóm cần ≥ 5 quan sát, nhận {xa.size} và {xb.size}."
        )
    reducer = {"median": np.median, "mean": np.mean}.get(statistic)
    if reducer is None:
        raise ValueError(f"statistic phải là 'median' hoặc 'mean', nhận {statistic!r}.")

    block = min(block_length, xa.size, xb.size)
    idx_a = circular_block_indices(
        xa.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed
    )
    idx_b = circular_block_indices(
        xb.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed + 1
    )
    replicates = reducer(xa[idx_a], axis=1) - reducer(xb[idx_b], axis=1)
    lo, hi = _percentile_ci(replicates)
    point = float(reducer(xa) - reducer(xb))
    return {
        "statistic": statistic,
        "point": point,
        "ci_low": lo,
        "ci_high": hi,
        "n_bootstrap": n_bootstrap,
        "block_length": block,
        "seed": seed,
        "replicates_sd": float(replicates.std(ddof=1)),
        "excludes_zero": bool(lo > 0.0 or hi < 0.0),
    }


# ---------------------------------------------------------------------------
# Các phép kiểm
# ---------------------------------------------------------------------------


def mann_whitney(
    a: Sequence[float],
    b: Sequence[float],
    *,
    alternative: str = "two-sided",
    label_a: str = "A",
    label_b: str = "B",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    Mann-Whitney U hai mẫu + rank-biserial + CI bootstrap cho chênh lệch trung vị.

    Dấu của `r_rb`: ``r_rb = 2U/(n_a·n_b) − 1`` với U của nhóm **a**, nên dương
    nghĩa là a có xu hướng lớn hơn b. Công thức trong roadmap
    ``1 − 2U/(n_a·n_b)`` cho cùng độ lớn nhưng dấu ngược vì U ở đó tính cho nhóm
    đối chứng; dùng một quy ước và nói rõ quy ước đó.
    """
    xa = np.asarray(a, dtype=float)
    xa = xa[np.isfinite(xa)]
    xb = np.asarray(b, dtype=float)
    xb = xb[np.isfinite(xb)]
    if xa.size < 3 or xb.size < 3:
        raise ValueError(f"Mỗi nhóm cần ≥ 3 quan sát, nhận {xa.size} và {xb.size}.")
    if alternative not in ("two-sided", "less", "greater"):
        raise ValueError(f"alternative không hợp lệ: {alternative!r}.")

    result = stats.mannwhitneyu(xa, xb, alternative=alternative, method="auto")
    u_a = float(result.statistic)
    n_a, n_b = int(xa.size), int(xb.size)
    r_rb = 2.0 * u_a / (n_a * n_b) - 1.0
    diff_ci = bootstrap_difference_ci(
        xa,
        xb,
        statistic="median",
        block_length=block_length,
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    return {
        "test": "mann_whitney_u",
        "label_a": label_a,
        "label_b": label_b,
        "alternative": alternative,
        "statistic_name": "U",
        "statistic": u_a,
        "p_value": float(result.pvalue),
        "n_a": n_a,
        "n_b": n_b,
        "median_a": float(np.median(xa)),
        "median_b": float(np.median(xb)),
        "mean_a": float(xa.mean()),
        "mean_b": float(xb.mean()),
        "median_difference": diff_ci["point"],
        "mean_difference": float(xa.mean() - xb.mean()),
        "effect_size_name": "r_rb",
        "effect_size": float(r_rb),
        "ci": diff_ci,
        "n_zero_differences": None,
    }


def kruskal_wallis(
    groups: Mapping[str, Sequence[float]],
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    Kruskal-Wallis một chiều + epsilon-squared ``ε² = H/(n−1)``.

    Chọn KW thay vì ANOVA vì (a) phân phối lệch mạnh và có outlier, (b) so sánh
    **bốn** nhóm nên không thể gộp thành một cặp Mann-Whitney mà không mất kiểm
    soát sai lầm loại I.
    """
    if len(groups) < 2:
        raise ValueError("Kruskal-Wallis cần ≥ 2 nhóm.")
    arrays: List[np.ndarray] = []
    for name, values in groups.items():
        x = np.asarray(values, dtype=float)
        x = x[np.isfinite(x)]
        if x.size < 3:
            raise ValueError(f"Nhóm {name!r} cần ≥ 3 quan sát, nhận {x.size}.")
        arrays.append(x)

    result = stats.kruskal(*arrays)
    h = float(result.statistic)
    n = int(sum(x.size for x in arrays))
    df = len(arrays) - 1
    epsilon_squared = h / (n - 1) if n > 1 else float("nan")
    return {
        "test": "kruskal_wallis",
        "alternative": "two-sided (omnibus)",
        "statistic_name": "H",
        "statistic": h,
        "p_value": float(result.pvalue),
        "df": df,
        "n": n,
        "group_sizes": {name: int(x.size) for name, x in zip(groups, arrays)},
        "group_medians": {name: float(np.median(x)) for name, x in zip(groups, arrays)},
        "effect_size_name": "epsilon_squared",
        "effect_size": float(min(max(epsilon_squared, 0.0), 1.0)),
        "ci": None,
        "bootstrap": {"block_length": block_length, "n_bootstrap": n_bootstrap, "seed": seed},
    }


def wilcoxon_signed_rank(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    alternative: str = "two-sided",
    label: str = "giá trị",
) -> Dict[str, Any]:
    """
    Wilcoxon signed-rank một mẫu + matched-pairs rank-biserial.

    SciPy mới không trả ``zstatistic`` nên W⁺/W⁻ được tính lại từ hạng — nhờ vậy
    effect size ``r = (W⁺ − W⁻)/(W⁺ + W⁻)`` kiểm chứng được độc lập với thư viện.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 5:
        raise ValueError(f"Cần ≥ 5 quan sát, nhận {x.size}.")
    if alternative not in ("two-sided", "less", "greater"):
        raise ValueError(f"alternative không hợp lệ: {alternative!r}.")

    d = x - mu
    n_nonzero = int(np.count_nonzero(d != 0.0))
    if n_nonzero < 5:
        raise ValueError(
            f"Chỉ có {n_nonzero} chênh lệch khác 0 — kiểm định signed-rank không dùng được."
        )
    result = stats.wilcoxon(d, alternative=alternative, zero_method="wilcox", correction=False)

    ranks = stats.rankdata(np.abs(d[d != 0.0]))
    signs = np.sign(d[d != 0.0])
    w_plus = float(ranks[signs > 0].sum())
    w_minus = float(ranks[signs < 0].sum())
    total = w_plus + w_minus
    r = (w_plus - w_minus) / total if total > 0 else float("nan")

    return {
        "test": "wilcoxon_signed_rank",
        "label": label,
        "mu": float(mu),
        "alternative": alternative,
        "statistic_name": "W",
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "n": int(x.size),
        "n_nonzero": n_nonzero,
        "w_plus": w_plus,
        "w_minus": w_minus,
        "median": float(np.median(x)),
        "median_difference": float(np.median(x) - mu),
        "effect_size_name": "r_rb_pairs",
        "effect_size": float(r),
        "ci": None,
    }


def one_sample_t(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    alternative: str = "two-sided",
    label: str = "giá trị",
) -> Dict[str, Any]:
    """
    t-test một mẫu + Cohen's d + CI 95% của trung bình (theo phân phối t).

    Lưu ý: CI này giả định các quan sát **độc lập**. Với chuỗi ngày còn tự tương
    quan, CI đó hẹp hơn thực tế — vì vậy báo cáo luôn kèm CI block bootstrap và
    nói rõ nếu hai CI khác nhau.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát, nhận {x.size}.")
    if alternative not in ("two-sided", "less", "greater"):
        raise ValueError(f"alternative không hợp lệ: {alternative!r}.")

    sd = float(x.std(ddof=1))
    if sd == 0.0:
        raise ValueError("Độ lệch chuẩn bằng 0 — Cohen's d không xác định.")
    result = stats.ttest_1samp(x, popmean=mu, alternative=alternative)
    se = sd / math.sqrt(x.size)
    t_crit = float(stats.t.ppf(0.975, df=x.size - 1))
    mean = float(x.mean())
    return {
        "test": "one_sample_t",
        "label": label,
        "mu": float(mu),
        "alternative": alternative,
        "statistic_name": "t",
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "df": int(x.size - 1),
        "n": int(x.size),
        "mean": mean,
        "sd": sd,
        "mean_difference": mean - mu,
        "effect_size_name": "cohen_d",
        "effect_size": (mean - mu) / sd,
        "ci_t": {"ci_low": mean - t_crit * se, "ci_high": mean + t_crit * se},
        "ci": None,
    }


# ---------------------------------------------------------------------------
# Kiểm tra độ nhạy
# ---------------------------------------------------------------------------


def paired_weekly_differences(
    panel: pd.DataFrame,
    *,
    value_col: str = "pm25_mean",
    min_weekdays: int = PAIRED_MIN_WEEKDAYS,
    min_weekend_days: int = PAIRED_MIN_WEEKEND_DAYS,
) -> Dict[str, Any]:
    """
    Chênh lệch trung bình-trong-tuần (weekday − weekend) theo từng tuần ISO.

    Vì sao cần: so sánh hai nhóm rời rạc bỏ qua việc hai nhóm nằm xen kẽ trong
    cùng một tuần. Ghép cặp theo tuần loại bỏ biến thiên "tuần này bẩn hơn tuần
    kia" — thứ tự tương quan mạnh nhất còn lại sau khi đã lấy trung bình ngày.
    """
    for col in ("week_key", "is_weekend", value_col):
        if col not in panel.columns:
            raise KeyError(f"paired_weekly_differences thiếu cột {col!r}.")

    rows: List[Dict[str, Any]] = []
    for week, grp in panel.groupby("week_key", observed=True):
        weekday = grp.loc[grp["is_weekend"] == 0, value_col].dropna()
        weekend = grp.loc[grp["is_weekend"] == 1, value_col].dropna()
        if len(weekday) < min_weekdays or len(weekend) < min_weekend_days:
            continue
        rows.append(
            {
                "week_key": week,
                "n_weekday": int(len(weekday)),
                "n_weekend": int(len(weekend)),
                "weekday_mean": float(weekday.mean()),
                "weekend_mean": float(weekend.mean()),
                "difference": float(weekday.mean() - weekend.mean()),
            }
        )

    if len(rows) < 5:
        raise ValueError(
            f"Chỉ có {len(rows)} tuần đủ điều kiện (≥{min_weekdays} ngày trong tuần và "
            f"≥{min_weekend_days} ngày cuối tuần) — không đủ để ghép cặp."
        )

    paired = pd.DataFrame(rows).sort_values("week_key").reset_index(drop=True)
    diffs = paired["difference"].to_numpy()
    test = wilcoxon_signed_rank(diffs, mu=0.0, alternative="two-sided", label="chênh lệch tuần")
    ci = bootstrap_ci(
        diffs,
        statistic="median",
        block_length=min(BLOCK_LENGTH_DAYS, max(1, len(diffs) // 4)),
        n_bootstrap=N_BOOTSTRAP,
        seed=BOOTSTRAP_SEED,
    )
    return {
        "n_weeks": int(len(paired)),
        "min_weekdays": min_weekdays,
        "min_weekend_days": min_weekend_days,
        "median_difference": float(np.median(diffs)),
        "mean_difference": float(diffs.mean()),
        "share_weekday_higher": float((diffs > 0).mean()),
        "test": test,
        "ci": ci,
        "weeks": paired,
    }


def season_weekly_sensitivity(
    panel: pd.DataFrame,
    *,
    value_col: str = "pm25_mean",
) -> Dict[str, Any]:
    """
    Kruskal-Wallis lặp lại trên **trung bình tuần theo mùa** (tham dò).

    Tuần được gán mùa theo ngày đầu tuần có mặt trong panel. Ở mức tuần, ACF còn
    lại thấp hơn nhiều so với mức ngày, nên đây là phép thử xem kết luận mùa có
    phụ thuộc vào giả định độc lập của từng ngày hay không.
    """
    for col in ("week_key", "season", value_col):
        if col not in panel.columns:
            raise KeyError(f"season_weekly_sensitivity thiếu cột {col!r}.")
    weekly = (
        panel.groupby(["week_key", "season"], observed=True)[value_col]
        .mean()
        .reset_index()
    )
    weekly["week_index"] = weekly["week_key"].str.extract(r"W(\d+)").astype(int)
    weekly = weekly.sort_values(["week_index", "week_key"]).drop_duplicates("week_key", keep="first")

    groups = {
        season: weekly.loc[weekly["season"] == season, value_col].to_numpy()
        for season in SEASON_DISPLAY_ORDER
    }
    groups = {k: v for k, v in groups.items() if v.size >= 3}
    if len(groups) < 2:
        raise ValueError("Không đủ mùa có ≥ 3 tuần để chạy kiểm tra độ nhạy.")
    result = kruskal_wallis(groups, n_bootstrap=0)
    return {"weekly_kruskal": result, "n_weeks": int(len(weekly))}


# ---------------------------------------------------------------------------
# Bối cảnh QCVN: các mẫu số khác nhau trả lời các câu hỏi khác nhau
# ---------------------------------------------------------------------------


def qcvn_context(
    hourly: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    limit: float = QCVN_2023_PM25_24H_LIMIT,
) -> Dict[str, Any]:
    """
    Đếm số ngày vượt ngưỡng 24h theo **hai** định nghĩa, nói rõ mẫu số.

    Vì sao phải tách: "31,13% giờ vượt 50" (tử số của cửa sổ trượt 24h, mẫu số
    5.317 cửa sổ hợp lệ) và "28,09% ngày vượt 50" (tử số là ngày, mẫu số 299 ngày
    đủ độ phủ) là hai câu khác nhau. Trộn tử số của định nghĩa này với mẫu số của
    định nghĩa kia sẽ cho ra tỷ lệ không trả lời được câu hỏi nào.
    """
    work = hourly.copy()
    work["_date"] = _local_timestamps(work[TIMESTAMP_COLUMN]).dt.normalize()
    work[TARGET_COLUMN] = pd.to_numeric(work[TARGET_COLUMN], errors="coerce")

    series = work.sort_values(TIMESTAMP_COLUMN).set_index(TIMESTAMP_COLUMN)[TARGET_COLUMN]
    series = series[~series.index.duplicated(keep="first")]
    # Lưới giờ đầy đủ: cửa sổ 24 giờ phải là 24 giờ liền kề thật, không phải 24
    # dòng dữ liệu (nếu dòng bị thiếu, 24 dòng có thể trải dài hơn 24 giờ).
    grid = pd.date_range(series.index.min(), series.index.max(), freq="h")
    rolling = series.reindex(grid).rolling(
        HOURS_PER_DAY, min_periods=HOURS_PER_DAY
    ).mean()
    roll_valid = rolling.dropna()
    roll_over = int((roll_valid >= limit).sum())

    panel_over = int((panel["pm25_mean"] >= limit).sum())
    n_panel = int(len(panel))
    return {
        "limit": float(limit),
        "rolling_windows_valid": int(roll_valid.size),
        "rolling_windows_over": roll_over,
        "rolling_share": float(roll_over / roll_valid.size) if roll_valid.size else float("nan"),
        "panel_days": n_panel,
        "panel_days_over": panel_over,
        "panel_share": float(panel_over / n_panel) if n_panel else float("nan"),
        "panel_days_equal_or_over_ci": _wilson_interval(panel_over, n_panel),
        "hourly_rows": int(len(work)),
        "hourly_rows_over_limit_note": (
            "Số giờ đơn lẻ ≥ 50 KHÔNG phải tỷ lệ vượt chuẩn 24h và không được dùng làm tử số."
        ),
    }


def _wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """CI Wilson cho một tỷ lệ — ổn định hơn Wald khi tỷ lệ gần 0/1."""
    if n <= 0:
        raise ValueError("n phải > 0.")
    phat = successes / n
    denom = 1.0 + z**2 / n
    centre = (phat + z**2 / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2)) / denom
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


# ---------------------------------------------------------------------------
# Điều phối toàn bộ
# ---------------------------------------------------------------------------


def _season_groups(panel: pd.DataFrame, value_col: str = "pm25_mean") -> Dict[str, np.ndarray]:
    groups: Dict[str, np.ndarray] = {}
    for season in SEASON_DISPLAY_ORDER:
        values = panel.loc[panel["season"] == season, value_col].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size:
            groups[season] = values
    return groups


def _posthoc_pairs(groups: Mapping[str, np.ndarray]) -> Dict[str, Any]:
    """Sáu cặp mùa bằng Mann-Whitney — family hậu định riêng, nhãn exploratory."""
    names = [s for s in SEASON_DISPLAY_ORDER if s in groups]
    pairs: List[Dict[str, Any]] = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            result = mann_whitney(
                groups[a],
                groups[b],
                label_a=SEASON_LABELS_VI[a],
                label_b=SEASON_LABELS_VI[b],
                seed=BOOTSTRAP_SEED,
            )
            result["pair"] = f"{SEASON_LABELS_VI[a]} – {SEASON_LABELS_VI[b]}"
            pairs.append(result)

    adjusted = holm_adjust([p["p_value"] for p in pairs])
    for pair, p_holm in zip(pairs, adjusted):
        pair["p_holm"] = float(p_holm)
        pair["reject_holm"] = bool(p_holm < ALPHA)
    return {"pairs": pairs, "n_pairs": len(pairs), "family": "posthoc_seasonal_pairs"}


def run_inference(
    df: Optional[pd.DataFrame] = None,
    *,
    data_path: Optional[Path] = None,
    min_valid_hours: int = MIN_VALID_HOURS_PER_DAY,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    Chạy toàn bộ suy luận của Issue #11 và trả về một payload duy nhất.

    `df=None` thì đọc `data/processed/air_pollution_final.parquet`. Truyền `df`
    để test chạy trên dữ liệu tổng hợp mà không cần `data/`.
    """
    hourly = load_analysis_frame(data_path) if df is None else df.copy()
    _require_columns(hourly, [TIMESTAMP_COLUMN, TARGET_COLUMN], context="run_inference")

    panel, audit = build_daily_panel(hourly, min_valid_hours=min_valid_hours)
    values = panel["pm25_mean"].to_numpy(dtype=float)

    diagnostics = distribution_diagnostics(values)

    hourly_series = hourly.set_index(TIMESTAMP_COLUMN)[TARGET_COLUMN].sort_index()
    hourly_series = hourly_series[~hourly_series.index.duplicated(keep="first")]
    hourly_grid = pd.date_range(
        hourly_series.index.min(), hourly_series.index.max(), freq="h"
    )
    hourly_values = hourly_series.reindex(hourly_grid).to_numpy(dtype=float)
    dense_daily = dense_daily_series(panel)
    daily_acf = autocorrelation(dense_daily, max(ACF_LAGS_DAILY))
    hourly_acf = autocorrelation(hourly_values, max(ACF_LAGS_HOURLY))
    dependence = {
        "daily_acf": {lag: float(daily_acf[lag]) for lag in ACF_LAGS_DAILY},
        "hourly_acf": {lag: float(hourly_acf[lag]) for lag in ACF_LAGS_HOURLY},
        "daily_effective_n": effective_sample_size(dense_daily),
        "daily_series_note": (
            "ACF ngày tính trên lưới lịch đầy đủ (ngày bị loại = NaN), không nén "
            "bỏ khoảng trống."
        ),
    }

    # --- Kiểm định 1: bốn mùa ------------------------------------------------
    season_groups = _season_groups(panel)
    if len(season_groups) < 2:
        raise ValueError("Cần ≥ 2 mùa có dữ liệu để so sánh.")
    season_test = kruskal_wallis(season_groups, n_bootstrap=n_bootstrap, seed=seed)
    pair_ci = None
    if "Dong" in season_groups and "He" in season_groups:
        pair_ci = bootstrap_difference_ci(
            season_groups["Dong"],
            season_groups["He"],
            statistic="median",
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
    season_test["ci_dong_vs_he"] = pair_ci

    # --- Kiểm định 2: weekday vs weekend -------------------------------------
    weekday = panel.loc[panel["is_weekend"] == 0, "pm25_mean"].to_numpy(dtype=float)
    weekend = panel.loc[panel["is_weekend"] == 1, "pm25_mean"].to_numpy(dtype=float)
    weekday_test = mann_whitney(
        weekday,
        weekend,
        label_a="Ngày làm việc",
        label_b="Ngày cuối tuần",
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    weekday_power = minimum_detectable_difference(weekday, weekend)

    # --- Kiểm định 3a: QCVN 24h ---------------------------------------------
    qcvn_24h_test = wilcoxon_signed_rank(
        values, mu=QCVN_2023_PM25_24H_LIMIT, alternative="two-sided", label="trung bình ngày"
    )
    qcvn_24h_test["ci_bootstrap"] = bootstrap_ci(
        values, statistic="median", n_bootstrap=n_bootstrap, seed=seed
    )

    # --- Kiểm định 3b: QCVN trung bình năm ----------------------------------
    annual_test = one_sample_t(
        values, mu=QCVN_2023_PM25_ANNUAL_LIMIT, alternative="two-sided", label="trung bình ngày"
    )
    annual_test["ci_bootstrap"] = bootstrap_ci(
        values, statistic="mean", n_bootstrap=n_bootstrap, seed=seed
    )

    # --- Family xác nhận + Holm --------------------------------------------
    confirmatory = [
        ("season_kruskal", "Mùa (Kruskal-Wallis, 4 nhóm)", season_test),
        ("weekday_mannwhitney", "Ngày làm việc vs cuối tuần (Mann-Whitney)", weekday_test),
        ("qcvn_24h_wilcoxon", "Trung bình 24h vs 50 µg/m³ (Wilcoxon)", qcvn_24h_test),
        ("qcvn_annual_ttest", "Trung bình giai đoạn vs 25 µg/m³ (t một mẫu)", annual_test),
    ]
    adjusted = holm_adjust([test["p_value"] for _, _, test in confirmatory])
    holm_table = []
    for (key, label, test), p_holm in zip(confirmatory, adjusted):
        test["p_holm"] = float(p_holm)
        test["reject_holm"] = bool(p_holm < ALPHA)
        test["reject_raw"] = bool(test["p_value"] < ALPHA)
        holm_table.append(
            {
                "key": key,
                "label": label,
                "p_raw": float(test["p_value"]),
                "p_holm": float(p_holm),
                "reject_raw": bool(test["p_value"] < ALPHA),
                "reject_holm": bool(p_holm < ALPHA),
                "statistic_name": test["statistic_name"],
                "statistic": test["statistic"],
                "effect_size_name": test["effect_size_name"],
                "effect_size": test["effect_size"],
            }
        )

    posthoc = _posthoc_pairs(season_groups)
    sensitivity = {
        "paired_weeks": paired_weekly_differences(panel),
        "season_weekly": season_weekly_sensitivity(panel),
        "power_mde": weekday_power,
    }
    context = qcvn_context(hourly, panel)

    return {
        "meta": {
            "issue": "#11",
            "alpha": ALPHA,
            "confidence_level": CONFIDENCE_LEVEL,
            "n_bootstrap": n_bootstrap,
            "bootstrap_seed": seed,
            "block_length_days": BLOCK_LENGTH_DAYS,
            "min_valid_hours_per_day": min_valid_hours,
            "split_point_note": (
                "Không dùng Train/Test: các phép kiểm không fit mô hình. Điểm cắt "
                "2026-01-15 của Issue #7 giữ nguyên cho Issue #12–#13."
            ),
            "dataset_sha256": dataset_sha256(data_path) if data_path or df is None else None,
            "numpy_version": np.__version__,
            "scipy_version": stats.__name__ and _scipy_version(),
            "data_source": str(data_path or DEFAULT_DATA_PATH),
        },
        "panel": {"n": int(len(panel)), "audit": audit, "frame": panel},
        "diagnostics": diagnostics,
        "dependence": dependence,
        "tests": {
            "season_kruskal": season_test,
            "weekday_mannwhitney": weekday_test,
            "qcvn_24h_wilcoxon": qcvn_24h_test,
            "qcvn_annual_ttest": annual_test,
        },
        "holm_confirmatory": holm_table,
        "posthoc_season": posthoc,
        "sensitivity": sensitivity,
        "qcvn_context": context,
    }


def _scipy_version() -> str:
    import scipy

    return scipy.__version__


# ---------------------------------------------------------------------------
# Render báo cáo
# ---------------------------------------------------------------------------


def _p(value: float) -> str:
    """p-value: ký hiệu khoa học khi rất nhỏ, 4 chữ số thập phân khi không."""
    if value < 1e-4:
        return format_scientific_vi(value, 2)
    return format_number_vi(value, 4)


def _ci_text(ci: Optional[Mapping[str, Any]]) -> str:
    if not ci:
        return "—"
    return f"[{format_number_vi(ci['ci_low'], 2)}; {format_number_vi(ci['ci_high'], 2)}]"


def _decision(p_holm: float) -> str:
    return "bác bỏ H₀" if p_holm < ALPHA else "không bác bỏ H₀"


def render_inference_report(results: Mapping[str, Any]) -> str:
    """
    Sinh `reports/inference_results.md` từ payload của `run_inference()`.

    Mọi con số đều lấy từ `results`; không có số nào viết tay trong hàm này.
    """
    meta = results["meta"]
    audit = results["panel"]["audit"]
    diag = results["diagnostics"]
    dep = results["dependence"]
    tests = results["tests"]
    ctx = results["qcvn_context"]
    season = tests["season_kruskal"]
    weekday = tests["weekday_mannwhitney"]
    q24 = tests["qcvn_24h_wilcoxon"]
    annual = tests["qcvn_annual_ttest"]
    posthoc = results["posthoc_season"]
    sensitivity = results["sensitivity"]
    paired = sensitivity["paired_weeks"]
    weekly_season = sensitivity["season_weekly"]["weekly_kruskal"]
    mde = sensitivity["power_mde"]
    weekday_ci = weekday["ci"]
    ci_includes_zero = bool(
        weekday_ci is not None and weekday_ci["ci_low"] <= 0.0 <= weekday_ci["ci_high"]
    )

    n = results["panel"]["n"]
    season_rows = "\n".join(
        f"| {SEASON_LABELS_VI[s]} | {format_int_vi(season['group_sizes'][s])} | "
        f"{format_number_vi(season['group_medians'][s], 2)} |"
        for s in SEASON_DISPLAY_ORDER
        if s in season["group_sizes"]
    )
    holm_rows = "\n".join(
        f"| {row['label']} | {row['statistic_name']} = {format_number_vi(row['statistic'], 3)} | "
        f"{_p(row['p_raw'])} | {_p(row['p_holm'])} | "
        f"{EFFECT_SIZE_LABELS.get(row['effect_size_name'], row['effect_size_name'])} = "
        f"{format_number_vi(row['effect_size'], 3)} | {_decision(row['p_holm'])} |"
        for row in results["holm_confirmatory"]
    )
    posthoc_rows = "\n".join(
        f"| {pair['pair']} | {format_number_vi(pair['median_a'], 2)} | "
        f"{format_number_vi(pair['median_b'], 2)} | "
        f"{format_number_vi(pair['statistic'], 0)} | {_p(pair['p_value'])} | "
        f"{_p(pair['p_holm'])} | {format_number_vi(pair['effect_size'], 3)} | "
        f"{_ci_text(pair['ci'])} | {_decision(pair['p_holm'])} |"
        for pair in posthoc["pairs"]
    )
    acf_daily = " · ".join(
        f"lag {lag} = {format_number_vi(v, 4)}" for lag, v in dep["daily_acf"].items()
    )
    acf_hourly = " · ".join(
        f"lag {lag} = {format_number_vi(v, 4)}" for lag, v in dep["hourly_acf"].items()
    )
    eff = dep["daily_effective_n"]
    ctx_ci = ctx["panel_days_equal_or_over_ci"]

    lines = [
        "# Kết quả Suy luận Thống kê — Issue #11 (W9)",
        "",
        "> **Tệp này được sinh tự động** bởi `src/inference.py::render_inference_report()`",
        "> từ `notebooks/05_statistical_inference.ipynb`. Không sửa tay: mọi con số",
        "> dưới đây lấy trực tiếp từ `run_inference()` trên dataset đã đóng băng.",
        "",
        "| Trường | Giá trị |",
        "|---|---|",
        f"| Issue | {meta['issue']} |",
        f"| Mức ý nghĩa α (chốt trước khi xem dữ liệu) | {format_number_vi(meta['alpha'], 2)} |",
        f"| Bootstrap | {format_int_vi(meta['n_bootstrap'])} lặp · block {meta['block_length_days']} ngày · seed {meta['bootstrap_seed']} · CI percentile {int(meta['confidence_level'] * 100)}% |",
        f"| Đơn vị phân tích | Trung bình ngày (≥ {meta['min_valid_hours_per_day']}/24 giờ có `pm25`) |",
        f"| Nguồn dữ liệu | `{meta['data_source']}` |",
        f"| SHA-256 dataset | `{meta['dataset_sha256'] or 'không tính (dữ liệu truyền vào)'}` |",
        f"| NumPy / SciPy | {meta['numpy_version']} / {meta['scipy_version']} |",
        "",
        "---",
        "",
        "## 1. Đơn vị phân tích và nhật ký lọc mẫu",
        "",
        f"- Chuỗi giờ: **{format_int_vi(audit['rows_hourly'])}** dòng, trong đó "
        f"**{format_int_vi(audit['hours_with_pm25'])}** giờ có `pm25` và "
        f"**{format_int_vi(audit['hours_missing_pm25'])}** giờ thiếu.",
        f"- Dải quan sát (giờ có `pm25`): **{audit['observed_first']} → {audit['observed_last']}** "
        f"({audit['span_days']} ngày lịch, {audit['n_stations']} trạm); ngày đủ độ phủ đầu–cuối: "
        f"{audit['coverage_first']} → {audit['coverage_last']}.",
        f"- Ngày có ít nhất một giờ đo: **{format_int_vi(audit['days_with_any_observation'])}**; "
        f"ngày đủ 24/24 giờ: **{format_int_vi(audit['days_full_24h'])}**.",
        f"- Ngày đạt tiêu chí ≥ {audit['min_valid_hours']}/24 giờ: **{format_int_vi(audit['days_kept'])}** — "
        f"đây là cỡ mẫu của mọi kiểm định (n = {format_int_vi(n)}).",
        f"- Ngày bị loại vì thiếu độ phủ: **{format_int_vi(audit['days_dropped'])}**.",
        f"- Ngày làm việc / cuối tuần trong panel: **{format_int_vi(audit['weekday_days'])}** / "
        f"**{format_int_vi(audit['weekend_days'])}**.",
        "",
        "**Vì sao không dùng từng giờ làm đơn vị phân tích.** ACF bậc 1 của chuỗi giờ là "
        f"{format_number_vi(dep['hourly_acf'][1], 4)} — {format_int_vi(audit['rows_hourly'])} giờ "
        "không phải bấy nhiêu quan sát độc lập. "
        "Tổng hợp về ngày là bước giảm tự tương quan **bắt buộc**, không phải tuỳ chọn trình bày. "
        f"Tiêu chí ≥ {audit['min_valid_hours']}/24 giờ là **lựa chọn phân tích của dự án** "
        "(độ phủ 75%), không phải điều khoản của QCVN 05:2023/BTNMT.",
        "",
        "**Vì sao không dùng Train/Test split.** Các phép kiểm dưới đây không fit mô hình, "
        "không chọn siêu tham số và không đánh giá năng lực dự báo, nên không có đường rò rỉ "
        "Test → Train. Chạy trên toàn bộ giai đoạn quan sát để tận dụng cỡ mẫu và để kiểm định "
        "trung bình năm có trọn chu kỳ. Điểm cắt `2026-01-15 00:00+07:00` của Issue #7 "
        "**không bị thay đổi**.",
        "",
        "---",
        "",
        "## 2. Chẩn đoán phân phối (không mặc định chuẩn / không chuẩn)",
        "",
        "| Chỉ số | Giá trị |",
        "|---|---|",
        f"| n (ngày) | {format_int_vi(diag['n'])} |",
        f"| Trung bình ± SD | {format_number_vi(diag['mean'], 2)} ± {format_number_vi(diag['sd'], 2)} µg/m³ |",
        f"| Trung vị [IQR] | {format_number_vi(diag['median'], 2)} "
        f"[{format_number_vi(diag['q1'], 2)}; {format_number_vi(diag['q3'], 2)}] µg/m³ |",
        f"| Min – Max | {format_number_vi(diag['min'], 2)} – {format_number_vi(diag['max'], 2)} µg/m³ |",
        f"| Skewness (hiệu chỉnh mẫu) | {format_number_vi(diag['skewness'], 4)} |",
        f"| Excess kurtosis | {format_number_vi(diag['excess_kurtosis'], 4)} |",
        f"| Hình dạng (mô tả định lượng) | {diag['shape']} |",
        f"| Shapiro-Wilk | W = {format_number_vi(diag['shapiro_w'], 4)}, p = {_p(diag['shapiro_p'])} |",
        f"| D'Agostino K² | K² = {format_number_vi(diag['dagostino_stat'], 3)}, p = {_p(diag['dagostino_p'])} |",
        f"| Số ngày ngoài ±3 SD | {format_int_vi(diag['n_outliers_3sd'])} |",
        "",
        "Cả hai kiểm định chuẩn tắc đều bác bỏ tính chuẩn, nhưng **đó không phải lý do duy nhất** "
        "để chọn phép kiểm phi tham số. Với n cỡ này, Shapiro-Wilk có power đủ để phát hiện lệch "
        "nhỏ không có ý nghĩa thực tiễn; vì vậy quyết định dựa thêm vào (a) skewness và kurtosis "
        "quan sát được, (b) bản chất thang đo — nồng độ bị chặn dưới 0, phân phối lệch phải, có "
        "outlier đợt ô nhiễm, và (c) các phép kiểm phi tham số so sánh **trung vị/hạng**, đúng với "
        "câu hỏi về mức nền phơi nhiễm hơn là về trung bình số học. Q-Q plot: `figures/FIG-08.png`.",
        "",
        "---",
        "",
        "## 3. Tự tương quan và cỡ mẫu hiệu dụng",
        "",
        f"- ACF chuỗi **giờ**: {acf_hourly}.",
        f"- ACF chuỗi **ngày**: {acf_daily}.",
        f"- AR(1) của chuỗi ngày: ρ = {format_number_vi(eff['rho_lag1'], 4)} → "
        f"n_eff ≈ **{format_number_vi(eff['n_effective'], 1)}** so với n = {format_int_vi(eff['n'])} "
        f"(hệ số lạm phát ×{format_number_vi(eff['inflation_factor'], 2)}).",
        "",
        "**Hệ quả và cách xử lý.** Mann-Whitney, Kruskal-Wallis, Wilcoxon và t-test đều giả định "
        "quan sát độc lập. Ở mức ngày, giả định đó **không** được bảo đảm (ρ = "
        f"{format_number_vi(eff['rho_lag1'], 2)}), nên p-value của chúng là **lạc quan** — đây là "
        "giới hạn được nêu thẳng, không được che. Biện pháp đã áp dụng: (1) hạ đơn vị phân tích từ "
        "giờ xuống ngày; (2) mọi CI dùng **block bootstrap 7 ngày**, không resample từng quan sát; "
        "(3) thêm hai **kiểm tra độ nhạy** ở mức tuần (mục 8) — nơi tự tương quan thấp hơn nhiều; "
        "(4) không dùng p-value để tuyên bố 'hiệu ứng lớn': mọi kết luận đọc kèm effect size và CI.",
        "",
        "---",
        "",
        "## 4. Kiểm định 1 — Khác biệt giữa các mùa",
        "",
        f"**H₀:** trung vị `pm25` trung bình ngày bằng nhau giữa bốn mùa. "
        f"**H₁:** có ít nhất một mùa khác biệt. **α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        "**Vì sao Kruskal-Wallis:** bốn nhóm (không phải hai) nên dùng KW omnibus giữ sai lầm loại I "
        "ở mức α; sau đó mới khảo sát sáu cặp bằng Mann-Whitney trong một family hậu định riêng.",
        "",
        "| Mùa | n (ngày) | Trung vị (µg/m³) |",
        "|---|---|---|",
        season_rows,
        "",
        f"- **H = {format_number_vi(season['statistic'], 4)}**, df = {season['df']}, "
        f"n = {format_int_vi(season['n'])}, **p thô = {_p(season['p_value'])}**, "
        f"**p Holm = {_p(season['p_holm'])}** → {_decision(season['p_holm'])}.",
        f"- Effect size **ε² = {format_number_vi(season['effect_size'], 4)}** "
        "(tỷ lệ phương sai hạng giải thích bởi mùa).",
    ]
    if season.get("ci_dong_vs_he"):
        ci = season["ci_dong_vs_he"]
        lines.append(
            f"- CI 95% block bootstrap cho chênh lệch trung vị **Đông − Hè**: "
            f"{format_number_vi(ci['point'], 2)} µg/m³, {_ci_text(ci)}."
        )
    lines += [
        "",
        "### 4.1. Hậu định sáu cặp mùa (exploratory — family Holm riêng)",
        "",
        "Sáu cặp này **không** thuộc family xác nhận: chúng được khảo sát sau khi KW bác bỏ H₀, "
        "nên mang nhãn *exploratory* và được hiệu chỉnh Holm trong family riêng. Kết luận của "
        "Issue #11 chỉ dựa vào KW ở trên; bảng dưới đây để định vị khác biệt nằm ở đâu.",
        "",
        "| Cặp | Trung vị A | Trung vị B | U | p thô | p Holm | r_rb | CI 95% (A−B) | Kết luận |",
        "|---|---|---|---|---|---|---|---|---|",
        posthoc_rows,
        "",
        "---",
        "",
        "## 5. Kiểm định 2 — Ngày làm việc vs ngày cuối tuần",
        "",
        f"**H₀:** trung vị `pm25` trung bình ngày của ngày làm việc bằng của ngày cuối tuần. "
        f"**H₁:** hai trung vị khác nhau. **α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        "**Vì sao Mann-Whitney:** hai nhóm độc lập về mặt thiết kế (một ngày chỉ thuộc một nhóm), "
        "phân phối lệch và có outlier; MW so sánh hạng nên không bị chi phối bởi vài ngày ô nhiễm nặng.",
        "",
        f"- Ngày làm việc: n = {format_int_vi(weekday['n_a'])}, "
        f"trung vị {format_number_vi(weekday['median_a'], 2)} µg/m³.",
        f"- Ngày cuối tuần: n = {format_int_vi(weekday['n_b'])}, "
        f"trung vị {format_number_vi(weekday['median_b'], 2)} µg/m³.",
        f"- **U = {format_number_vi(weekday['statistic'], 1)}**, "
        f"**p thô = {_p(weekday['p_value'])}**, **p Holm = {_p(weekday['p_holm'])}** → "
        f"{_decision(weekday['p_holm'])}.",
        f"- Chênh lệch trung vị: **{format_number_vi(weekday['median_difference'], 2)} µg/m³**, "
        f"CI 95% block bootstrap {_ci_text(weekday['ci'])}.",
        f"- Effect size **r_rb = {format_number_vi(weekday['effect_size'], 4)}** "
        "(dương = ngày làm việc cao hơn).",
        "",
        "**Ý nghĩa thống kê ≠ ý nghĩa thực tiễn — và power có giới hạn.** Với SD gộp "
        f"{format_number_vi(mde['pooled_sd'], 2)} µg/m³, n₁ = {format_int_vi(mde['n_a'])}, "
        f"n₂ = {format_int_vi(mde['n_b'])}, chênh lệch nhỏ nhất phát hiện được ở power "
        f"{format_number_vi(mde['power'] * 100, 0)}%, α = 0,05 là **MDE ≈ "
        f"{format_number_vi(mde['mde'], 2)} µg/m³** (xấp xỉ chuẩn, tính hậu nghiệm từ SD quan sát). "
        "Con số này là ngưỡng phân giải của phép kiểm, không phải kết luận về hiệu ứng:",
        "",
        f"- Chênh lệch quan sát được là {format_number_vi(weekday['median_difference'], 2)} µg/m³, "
        f"**nhỏ hơn MDE**, và CI 95% block bootstrap {_ci_text(weekday['ci'])} "
        f"{'chứa 0' if ci_includes_zero else 'không chứa 0'}; |r_rb| = "
        f"{format_number_vi(abs(weekday['effect_size']), 3)}. "
        "Vì vậy dữ liệu **không đủ độ phân giải** để phân biệt 'không có khác biệt' với "
        "'khác biệt nhỏ hơn MDE' — đây không phải bằng chứng khẳng định hai nhóm bằng nhau.",
        f"- Mọi kết luận trong báo cáo đọc theo **CI và effect size**, không theo p đơn độc. "
        "Ước lượng điểm nằm trong khoảng sai số thực hành của một trạm đo, nên không được "
        "dùng để quy kết nguồn phát thải hay hành vi giao thông.",
        "",
        "---",
        "",
        "## 6. Kiểm định 3 — Đối chiếu QCVN 05:2023/BTNMT (đúng chu kỳ lấy mẫu)",
        "",
        "Hai ngưỡng được kiểm định **tách biệt**, mỗi ngưỡng đi với đúng chu kỳ trung bình của nó. "
        "Không có phép so sánh nào giữa một giờ đơn lẻ với ngưỡng ngày hoặc ngưỡng năm.",
        "",
        "### 6.1. Ngưỡng trung bình 24 giờ — 50 µg/m³",
        "",
        f"**H₀:** trung vị của trung bình ngày bằng 50 µg/m³. **H₁:** khác 50. "
        f"**α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        "**Vì sao Wilcoxon signed-rank một mẫu:** so sánh một chuỗi với một hằng số, không giả định "
        "chuẩn; mỗi ngày là một cặp (giá trị, 50).",
        "",
        f"- n = {format_int_vi(q24['n'])} ngày; trung vị {format_number_vi(q24['median'], 2)} µg/m³.",
        f"- **W = {format_number_vi(q24['statistic'], 1)}** (W⁺ = {format_number_vi(q24['w_plus'], 1)}, "
        f"W⁻ = {format_number_vi(q24['w_minus'], 1)}), **p thô = {_p(q24['p_value'])}**, "
        f"**p Holm = {_p(q24['p_holm'])}** → {_decision(q24['p_holm'])}.",
        f"- Effect size **r = {format_number_vi(q24['effect_size'], 4)}** "
        "(âm = trung vị nằm dưới ngưỡng).",
        f"- CI 95% block bootstrap cho trung vị: {_ci_text(q24['ci_bootstrap'])}.",
        f"- Số ngày có trung bình ≥ 50 µg/m³: **{format_int_vi(ctx['panel_days_over'])}/"
        f"{format_int_vi(ctx['panel_days'])} = {format_number_vi(ctx['panel_share'] * 100, 2)}%** "
        f"(CI 95% Wilson: {format_number_vi(ctx_ci[0] * 100, 2)}% – "
        f"{format_number_vi(ctx_ci[1] * 100, 2)}%).",
        "",
        f"> **Hai mẫu số, hai câu hỏi.** Trong {format_int_vi(ctx['rolling_windows_valid'])} cửa sổ "
        f"trượt 24 giờ hợp lệ, có {format_int_vi(ctx['rolling_windows_over'])} cửa sổ ≥ 50 "
        f"({format_number_vi(ctx['rolling_share'] * 100, 2)}%). Con số này **không** thay thế được "
        f"tỷ lệ theo ngày ({format_int_vi(ctx['panel_days_over'])}/"
        f"{format_int_vi(ctx['panel_days'])} = "
        f"{format_number_vi(ctx['panel_share'] * 100, 2)}%), vì tử số và mẫu số khác đơn vị. "
        f"Ghép {format_int_vi(ctx['rolling_windows_over'])} cửa sổ với "
        f"{format_int_vi(ctx['hourly_rows'])} dòng giờ sẽ cho "
        f"{format_number_vi(100 * ctx['rolling_windows_over'] / ctx['hourly_rows'], 2)}% — một tỷ lệ "
        "không ứng với đơn vị nào và không được dùng trong báo cáo.",
        "",
        f"> **Không kết luận 'đạt/không đạt QCVN'.** Quy chuẩn quy định cách đánh giá tuân thủ "
        "(số ngày vượt được phép trong một năm) mà dự án **không** mã hoá và không có văn bản gốc "
        "đối chiếu. Kết quả trên chỉ nói: vị trí trung tâm của phân phối trung bình ngày nằm "
        "dưới 50 µg/m³, nhưng gần ba phần mười số ngày vượt ngưỡng — hai sự thật không mâu thuẫn.",
        "",
        "### 6.2. Ngưỡng trung bình năm — 25 µg/m³",
        "",
        f"**H₀:** trung bình của trung bình ngày bằng 25 µg/m³. **H₁:** khác 25. "
        f"**α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        "**Vì sao t-test một mẫu:** ngưỡng năm là ngưỡng của **trung bình**, không phải trung vị, "
        "nên phép kiểm phải so trung bình. Đây **không** phải ngưỡng áp cho một giờ hay một ngày.",
        "",
        f"- n = {format_int_vi(annual['n'])} ngày; trung bình {format_number_vi(annual['mean'], 2)} "
        f"± {format_number_vi(annual['sd'], 2)} µg/m³.",
        f"- **t = {format_number_vi(annual['statistic'], 4)}**, df = {annual['df']}, "
        f"**p thô = {_p(annual['p_value'])}**, **p Holm = {_p(annual['p_holm'])}** → "
        f"{_decision(annual['p_holm'])}.",
        f"- Cohen's d = **{format_number_vi(annual['effect_size'], 4)}** (đơn vị: độ lệch chuẩn của "
        "trung bình ngày, không phải của một quan sát năm).",
        f"- CI 95% theo phân phối t (giả định độc lập): {_ci_text(annual['ci_t'])}.",
        f"- CI 95% block bootstrap (tôn trọng tự tương quan): "
        f"{_ci_text(annual['ci_bootstrap'])}.",
        "",
        "> **Giới hạn thiết kế:** dải dữ liệu là 07/2025–07/2026, **không** trùng năm dương lịch. "
        "Vì vậy đại lượng trên là trung bình **giai đoạn quan sát**, không phải 'trung bình năm' "
        "theo định nghĩa quy chuẩn. Nó là chỉ báo mức nền, không phải một phán quyết tuân thủ.",
        "",
        "---",
        "",
        "## 7. Tổng hợp family xác nhận — p thô và p Holm cạnh nhau",
        "",
        "| Kiểm định | Thống kê | p thô | p Holm | Effect size | Kết luận (Holm) |",
        "|---|---|---|---|---|---|",
        holm_rows,
        "",
        f"Holm được chọn thay Bonferroni vì kiểm soát FWER **không cần giả định độc lập** và luôn "
        f"mạnh hơn hoặc bằng. Family xác nhận gồm đúng **{len(results['holm_confirmatory'])}** kiểm "
        "định — mỗi kiểm định trả lời một câu hỏi khác nhau, nên hiệu chỉnh ở đây là biện pháp "
        "phòng ngừa, không phải để 'cứu' kết luận. Cột p thô được giữ nguyên để người đọc tự kiểm "
        "tra hiệu chỉnh có làm đổi kết luận hay không.",
        "",
        "---",
        "",
        "## 8. Kiểm tra độ nhạy (exploratory, không thuộc family nào)",
        "",
        "### 8.1. Ghép cặp theo tuần cho weekday/weekend",
        "",
        f"- Số tuần đủ điều kiện (≥ {paired['min_weekdays']} ngày trong tuần và "
        f"≥ {paired['min_weekend_days']} ngày cuối tuần): **{format_int_vi(paired['n_weeks'])}**.",
        f"- Trung vị chênh lệch (weekday − weekend): "
        f"**{format_number_vi(paired['median_difference'], 2)} µg/m³**, "
        f"CI 95% bootstrap {_ci_text(paired['ci'])}.",
        f"- Tỷ lệ tuần có weekday cao hơn: "
        f"{format_number_vi(paired['share_weekday_higher'] * 100, 1)}%.",
        f"- Wilcoxon signed-rank trên {format_int_vi(paired['test']['n'])} chênh lệch tuần: "
        f"W = {format_number_vi(paired['test']['statistic'], 1)}, "
        f"p = {_p(paired['test']['p_value'])}, "
        f"r = {format_number_vi(paired['test']['effect_size'], 4)} → "
        f"{'bác bỏ' if paired['test']['p_value'] < ALPHA else 'không bác bỏ'} H₀ ở α = 0,05.",
        "",
        "Phép thử này loại bỏ biến thiên giữa các tuần và không dựa vào giả định các ngày độc lập. "
        "Nếu kết luận khác với Mann-Whitney ở mục 5, kết luận đúng là **không ổn định** — và đó "
        "phải là điều được viết ra.",
        "",
        "### 8.2. Kruskal-Wallis trên trung bình tuần theo mùa",
        "",
        f"- Số tuần dùng được: {format_int_vi(sensitivity['season_weekly']['n_weeks'])}; "
        f"H = {format_number_vi(weekly_season['statistic'], 3)}, df = {weekly_season['df']}, "
        f"p = {_p(weekly_season['p_value'])}, ε² = "
        f"{format_number_vi(weekly_season['effect_size'], 4)}.",
        "- Ở mức tuần, cỡ mẫu nhỏ hơn nhiều nên power thấp; p không có ý nghĩa **không** phủ định "
        "kết quả mức ngày, và p có ý nghĩa thì củng cố. Mục đích duy nhất là kiểm tra kết luận mùa "
        "có phụ thuộc vào giả định độc lập của từng ngày hay không.",
        "",
        "---",
        "",
        "## 9. Đọc p-value cho đúng (task 5.7)",
        "",
        "p-value là xác suất **của dữ liệu, có điều kiện H₀ đúng** — không phải xác suất H₀ đúng, "
        "cũng không phải xác suất kết quả lặp lại. Bốn sai lầm thường gặp và cách đọc đúng:",
        "",
        "| Sai lầm | Vì sao sai | Cách đọc đúng trong báo cáo này |",
        "|---|---|---|",
        "| p là xác suất H₀ đúng | p tính dưới giả định H₀; nó không phải xác suất hậu nghiệm | Chỉ nói 'dữ liệu không tương thích với H₀ ở mức α' |",
        "| 1 − p là xác suất H₁ đúng | H₁ thường là hợp, không có phân phối tiên nghiệm | Không gán xác suất cho H₁ |",
        "| p nhỏ = hiệu ứng lớn | p phụ thuộc cỡ mẫu; n ≈ 300 đủ làm hiệu ứng nhỏ có ý nghĩa | Luôn đọc kèm effect size và CI |",
        "| p > α = 'không có hiệu ứng' | Đó là 'không đủ bằng chứng', không phải bằng chứng không | Nêu rõ giới hạn power của từng phép kiểm |",
        "",
        "**Power = 1 − β, và độ phân giải của phép kiểm có giới hạn cụ thể.** Với SD gộp "
        f"{format_number_vi(mde['pooled_sd'], 2)} µg/m³, n₁ = {format_int_vi(mde['n_a'])}, "
        f"n₂ = {format_int_vi(mde['n_b'])}, chênh lệch nhỏ nhất phát hiện được ở power "
        f"{format_number_vi(mde['power'] * 100, 0)}%, α = 0,05 là **MDE ≈ "
        f"{format_number_vi(mde['mde'], 2)} µg/m³**. Chênh lệch trung vị quan sát ở mục 5 là "
        f"{format_number_vi(abs(weekday['median_difference']), 2)} µg/m³, tức "
        f"{'nhỏ hơn' if mde['mde'] > abs(weekday['median_difference']) else 'không nhỏ hơn'} MDE. "
        f"Vì thế kết quả ở mục 5 ({_decision(weekday['p_holm'])}) **không** chứng minh hai nhóm "
        "bằng nhau: nó chỉ cho thấy dữ liệu không đủ độ phân giải để tách 'không có khác biệt' "
        "khỏi 'khác biệt nhỏ hơn MDE'. Ở mức tuần (mục 8) n nhỏ hơn nên độ phân giải còn thô hơn; "
        "một kết quả không ý nghĩa ở đó không được dùng để bác bỏ kết quả mức ngày. Với bài toán "
        "cảnh báo, sai lầm loại II (bỏ lọt một đợt ô nhiễm) tốn kém hơn sai lầm loại I, nên ngưỡng "
        "vận hành của mô hình ở Issue #13 sẽ được chọn theo Recall chứ không theo Accuracy.",
        "",
        "---",
        "",
        "## 10. Prior probability và bẫy base-rate (task 5.8)",
        "",
        f"Trong {format_int_vi(ctx['panel_days'])} ngày đủ độ phủ, "
        f"{format_int_vi(ctx['panel_days_over'])} ngày có trung bình ≥ 50 µg/m³ → **prior ≈ "
        f"{format_number_vi(ctx['panel_share'] * 100, 1)}%**. Đó là xác suất tiên nghiệm mà một bộ "
        "phân loại 'ngày ô nhiễm' phải đối mặt: nếu nó luôn dự đoán 'không ô nhiễm', Accuracy đã "
        f"≈ {format_number_vi((1 - ctx['panel_share']) * 100, 1)}% mà không học được gì.",
        "",
        "Vì vậy mọi tỷ lệ trong báo cáo này đều nêu rõ **tử số và mẫu số**, và không có tỷ lệ nào "
        "được trình bày như một 'độ chính xác'. Prior cũng **dịch chuyển** giữa Train và Test do "
        "điểm cắt rơi vào giữa mùa đông; hệ quả đó thuộc Issue #13 và phải được xử lý bằng Recall "
        "và PR-AUC, không bằng Accuracy.",
        "",
        "---",
        "",
        "## 11. Giới hạn khoa học",
        "",
        "1. **Một chu kỳ mùa, một trạm.** Dải 07/2025–07/2026 chỉ chứa một vòng mùa và toàn bộ dữ "
        "liệu đến từ một trạm đô thị. Khác biệt theo mùa là mô tả của **giai đoạn này**, không "
        "ngoại suy được sang năm khác hay trạm khác.",
        "2. **Tự tương quan chưa được hiệu chỉnh vào p-value.** p của bốn kiểm định xác nhận vẫn "
        "dựa trên giả định độc lập; block bootstrap chỉ sửa khoảng tin cậy. Vì vậy p được đọc là "
        "**chỉ báo độ tương thích**, không phải bằng chứng chính xác tuyệt đối.",
        "3. **Block bootstrap là xấp xỉ.** Block 7 ngày giữ cấu trúc tuần nhưng không mô phỏng được "
        "phụ thuộc dài hạn (lag 14 vẫn còn tương quan). Với so sánh hai nhóm, resample theo từng "
        "nhóm bỏ qua tương quan chéo nhóm — kiểm tra ghép cặp theo tuần ở mục 8.1 là biện pháp bù.",
        "4. **Ngưỡng 18/24 giờ** là quy ước phân tích (độ phủ 75%), không phải điều khoản QCVN. "
        "Đổi ngưỡng sẽ đổi n; notebook in bảng nhật ký lọc để việc đổi ngưỡng là minh bạch.",
        "5. **QCVN 05:2023/BTNMT quy định ở điều kiện chuẩn (µg/Nm³, 25 °C, 760 mmHg)**, còn trạm "
        "OpenAQ báo nồng độ môi trường (µg/m³). So sánh định lượng với ngưỡng vì vậy là xấp xỉ.",
        "6. **Không có kết luận nhân quả.** Khác biệt theo mùa/ngày trong tuần là liên hệ thống kê; "
        "nguồn phát thải, khí tượng và điều kiện biên không được phân tách ở đây.",
        "",
        "---",
        "",
        "## 12. Tái lập",
        "",
        "```bash",
        "python -m unittest tests.test_inference -v          # kiểm thử tất định",
        "python -c \"from src.inference import run_inference, render_inference_report, DEFAULT_REPORT_PATH; \" \\",
        "          \"DEFAULT_REPORT_PATH.write_text(render_inference_report(run_inference()), encoding='utf-8')\"",
        "```",
        "",
        f"Mọi con số tái lập được với seed {meta['bootstrap_seed']} và {format_int_vi(meta['n_bootstrap'])} "
        "lặp bootstrap. Sai khác duy nhất có thể có là phiên bản NumPy/SciPy (đã ghi ở đầu báo cáo).",
        "",
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Hình bổ sung cho Issue #11 — FIG-08 … FIG-12
# ---------------------------------------------------------------------------

FIGURE_DIR: Path = REPO_ROOT / "figures"

#: Tên tệp cố định. Đây là **hình bổ sung của Issue #11**, không thuộc bộ bảy
#: hình ấn phẩm FIG-01…FIG-07 của Issue #9.
INFERENCE_FIGURES: Dict[str, str] = {
    "distribution": "FIG-08.png",
    "season": "FIG-09.png",
    "weekday": "FIG-10.png",
    "qcvn": "FIG-11.png",
    "autocorrelation": "FIG-12.png",
}


def _box_style(palette: Mapping[str, str]) -> Dict[str, Any]:
    """Tham số boxplot dùng chung cho FIG-09/FIG-10 — một nguồn sự thật."""
    return {
        "patch_artist": True,
        "widths": 0.55,
        "showfliers": True,
        "medianprops": {"color": palette["mean_line"], "linewidth": 1.6},
        "whiskerprops": {"color": palette["spine"], "linewidth": 0.9},
        "capprops": {"color": palette["spine"], "linewidth": 0.9},
        "flierprops": {
            "marker": "o",
            "markersize": 3.0,
            "markerfacecolor": palette["hourly_raw"],
            "markeredgecolor": "none",
            "alpha": 0.55,
        },
    }


def _strip_offsets(n: int) -> np.ndarray:
    """
    Độ lệch ngang tất định cho strip plot (không RNG → hình tái lập byte-identical).

    Dùng dãy tỉ lệ vàng: phân bố đều trong [-0,17; +0,17] mà không cần seed.
    """
    if n <= 0:
        return np.zeros(0, dtype=float)
    frac = (np.arange(n, dtype=float) * 0.6180339887498949) % 1.0
    return (frac - 0.5) * 0.34


def _naive_dates(values: pd.Series) -> np.ndarray:
    """Bỏ tz trước khi đưa trục thời gian cho Matplotlib (tránh cảnh báo tz-aware)."""
    ts = pd.to_datetime(values)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_localize(None)
    return ts.to_numpy()


def _figure_distribution(results: Mapping[str, Any]):
    """FIG-08 — histogram + mật độ chuẩn và Q-Q plot của trung bình ngày."""
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    diag = results["diagnostics"]
    values = results["panel"]["frame"]["pm25_mean"].to_numpy(dtype=float)
    values = values[np.isfinite(values)]

    fig, (ax_hist, ax_qq) = plt.subplots(1, 2, figsize=(12.2, 4.9))
    apply_tufte_style(ax_hist, grid_axis="y")
    apply_tufte_style(ax_qq, grid_axis="both")

    ax_hist.hist(
        values,
        bins=30,
        density=True,
        color=PALETTE["hourly_raw"],
        edgecolor="white",
        linewidth=0.5,
        alpha=0.8,
        label=f"Trung bình ngày (n = {format_int_vi(diag['n'])})",
    )
    grid = np.linspace(values.min(), values.max(), 400)
    ax_hist.plot(
        grid,
        stats.norm.pdf(grid, loc=diag["mean"], scale=diag["sd"]),
        color=PALETTE["qcvn_24h"],
        linewidth=2.0,
        label="Phân phối chuẩn cùng mean và SD",
    )
    ax_hist.axvline(
        diag["median"],
        color=PALETTE["median_line"],
        linewidth=1.8,
        label=f"Trung vị = {format_number_vi(diag['median'])} µg/m³",
    )
    ax_hist.axvline(
        diag["mean"],
        color=PALETTE["mean_line"],
        linestyle="--",
        linewidth=1.6,
        label=f"Trung bình = {format_number_vi(diag['mean'])} µg/m³",
    )
    ax_hist.set_xlabel("PM2.5 trung bình 24 giờ (µg/m³)")
    ax_hist.set_ylabel("Mật độ xác suất")
    ax_hist.set_title("(a) Hình dạng phân phối thực nghiệm", loc="left", fontsize=11)
    ax_hist.legend(frameon=False, fontsize=8.6, loc="upper right")
    ax_hist.text(
        0.02,
        0.97,
        (
            f"Skewness = {format_number_vi(diag['skewness'], 3)}\n"
            f"Kurtosis thừa = {format_number_vi(diag['excess_kurtosis'], 3)}\n"
            f"Shapiro-Wilk p = {format_scientific_vi(diag['shapiro_p'])}\n"
            f"D'Agostino p = {format_scientific_vi(diag['dagostino_p'])}"
        ),
        transform=ax_hist.transAxes,
        va="top",
        ha="left",
        fontsize=8.6,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "alpha": 0.85, "edgecolor": PALETTE["grid"]},
    )

    qq = qq_points(values)
    ax_qq.scatter(
        qq["theoretical"],
        qq["sample"],
        s=14,
        color=PALETTE["rolling_24h"],
        alpha=0.7,
        edgecolors="none",
        label="Điểm Q-Q (Blom)",
    )
    limits = [
        float(min(qq["theoretical"].min(), qq["sample"].min())),
        float(max(qq["theoretical"].max(), qq["sample"].max())),
    ]
    ax_qq.plot(
        limits,
        limits,
        color=PALETTE["median_line"],
        linestyle="--",
        linewidth=1.3,
        label="Chuẩn lý thuyết (y = x)",
    )
    ax_qq.set_xlabel("Phân vị chuẩn lý thuyết (z)")
    ax_qq.set_ylabel("Giá trị chuẩn hoá thực nghiệm (z)")
    ax_qq.set_title("(b) Q-Q plot so với phân phối chuẩn", loc="left", fontsize=11)
    ax_qq.legend(frameon=False, fontsize=8.6, loc="upper left")

    fig.suptitle(
        "Hình 8 — Chẩn đoán phân phối PM2.5 trung bình ngày (Issue #11)",
        fontsize=12.5,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    return fig


def _figure_season(results: Mapping[str, Any]):
    """FIG-09 — phân bố trung bình ngày theo bốn mùa kèm kết quả Kruskal-Wallis."""
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    test = results["tests"]["season_kruskal"]
    panel = results["panel"]["frame"]
    groups, labels = [], []
    for season in SEASON_DISPLAY_ORDER:
        values = panel.loc[panel["season"] == season, "pm25_mean"].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size:
            groups.append(values)
            labels.append(
                f"{SEASON_LABELS_VI[season]}\n(n = {format_int_vi(values.size)})"
            )

    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    apply_tufte_style(ax, grid_axis="y")
    artists = ax.boxplot(groups, tick_labels=labels, **_box_style(PALETTE))
    for patch in artists["boxes"]:
        patch.set_facecolor(PALETTE["hourly_raw"])
        patch.set_edgecolor(PALETTE["spine"])
        patch.set_alpha(0.75)

    ax.set_ylabel("PM2.5 trung bình ngày (µg/m³)")
    ax.set_xlabel("Mùa (theo tháng dương lịch)")
    ax.set_title(
        "Hình 9 — Khác biệt PM2.5 theo mùa: Kruskal-Wallis bốn nhóm",
        loc="left",
        fontsize=12,
    )
    ax.text(
        0.99,
        0.98,
        (
            f"H = {format_number_vi(test['statistic'], 3)}, df = {test['df']}\n"
            f"p = {format_scientific_vi(test['p_value'])}\n"
            f"p hiệu chỉnh Holm = {format_scientific_vi(test['p_holm'])}\n"
            f"ε² = {format_number_vi(test['effect_size'], 4)}"
        ),
        transform=ax.transAxes,
        va="top",
        ha="right",
        fontsize=9,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.88, "edgecolor": PALETTE["grid"]},
    )
    fig.text(
        0.01,
        0.01,
        "Hộp = IQR, đường giữa = trung vị, râu = 1,5·IQR; điểm = quan sát ngoài râu.",
        fontsize=8.4,
        color="#4a4a4a",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def _figure_weekday(results: Mapping[str, Any]):
    """FIG-10 — ngày làm việc vs cuối tuần, boxplot + strip tất định."""
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    test = results["tests"]["weekday_mannwhitney"]
    panel = results["panel"]["frame"]
    weekday = panel.loc[panel["is_weekend"] == 0, "pm25_mean"].to_numpy(dtype=float)
    weekend = panel.loc[panel["is_weekend"] == 1, "pm25_mean"].to_numpy(dtype=float)
    weekday = weekday[np.isfinite(weekday)]
    weekend = weekend[np.isfinite(weekend)]

    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    apply_tufte_style(ax, grid_axis="y")
    artists = ax.boxplot(
        [weekday, weekend],
        tick_labels=[
            f"Ngày làm việc\n(n = {format_int_vi(weekday.size)})",
            f"Cuối tuần\n(n = {format_int_vi(weekend.size)})",
        ],
        **_box_style(PALETTE),
    )
    for patch in artists["boxes"]:
        patch.set_facecolor(PALETTE["hourly_raw"])
        patch.set_edgecolor(PALETTE["spine"])
        patch.set_alpha(0.75)

    for position, values in ((1, weekday), (2, weekend)):
        ordered = np.sort(values)
        ax.scatter(
            position + _strip_offsets(ordered.size),
            ordered,
            s=10,
            color=PALETTE["rolling_24h"],
            alpha=0.35,
            edgecolors="none",
            zorder=3,
        )

    ci = test["ci"]
    ax.set_ylabel("PM2.5 trung bình ngày (µg/m³)")
    ax.set_title(
        "Hình 10 — Ngày làm việc và cuối tuần: Mann-Whitney U",
        loc="left",
        fontsize=12,
    )
    ax.text(
        0.99,
        0.98,
        (
            f"Trung vị: {format_number_vi(test['median_a'])} so với "
            f"{format_number_vi(test['median_b'])} µg/m³\n"
            f"Chênh lệch trung vị = {format_number_vi(test['median_difference'])} "
            f"[{format_number_vi(ci['ci_low'])}; {format_number_vi(ci['ci_high'])}]\n"
            f"U = {format_number_vi(test['statistic'], 1)}, "
            f"p = {format_number_vi(test['p_value'], 4)}, "
            f"p hiệu chỉnh Holm = {format_number_vi(test['p_holm'], 4)}\n"
            f"r_rb = {format_number_vi(test['effect_size'], 4)}"
        ),
        transform=ax.transAxes,
        va="top",
        ha="right",
        fontsize=8.8,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.88, "edgecolor": PALETTE["grid"]},
    )
    fig.tight_layout()
    return fig


def _figure_qcvn(results: Mapping[str, Any]):
    """FIG-11 — chuỗi trung bình ngày và ngưỡng QCVN 24 giờ (50 µg/m³)."""
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    ctx = results["qcvn_context"]
    panel = results["panel"]["frame"]
    dates = _naive_dates(panel["date"])
    values = panel["pm25_mean"].to_numpy(dtype=float)
    over = values >= ctx["limit"]

    fig, ax = plt.subplots(figsize=(12.2, 4.9))
    apply_tufte_style(ax, grid_axis="y")
    ax.plot(
        dates,
        values,
        color=PALETTE["rolling_24h"],
        linewidth=0.9,
        alpha=0.8,
        label="Trung bình 24 giờ của ngày đủ độ phủ",
    )
    ax.scatter(
        dates[over],
        values[over],
        s=16,
        color=PALETTE["mean_line"],
        alpha=0.85,
        edgecolors="none",
        label=f"Ngày có trung bình ≥ {format_number_vi(ctx['limit'], 0)} µg/m³",
        zorder=3,
    )
    ax.axhline(
        ctx["limit"],
        color=PALETTE["qcvn_24h"],
        linestyle="--",
        linewidth=1.5,
        label=f"QCVN 05:2023/BTNMT — trung bình 24 giờ = {format_number_vi(ctx['limit'], 0)} µg/m³",
    )
    ax.set_ylabel("PM2.5 trung bình ngày (µg/m³)")
    ax.set_xlabel("Thời gian (giờ Việt Nam)")
    ax.set_title(
        "Hình 11 — Chuỗi trung bình ngày và ngưỡng QCVN 24 giờ",
        loc="left",
        fontsize=12,
    )
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.legend(frameon=False, fontsize=8.6, loc="upper left")

    ci_low, ci_high = ctx["panel_days_equal_or_over_ci"]
    note = (
        f"{format_int_vi(ctx['panel_days_over'])}/{format_int_vi(ctx['panel_days'])} ngày "
        f"= {format_number_vi(ctx['panel_share'] * 100, 2)}% "
        f"(CI Wilson 95%: {format_number_vi(ci_low * 100, 2)}–{format_number_vi(ci_high * 100, 2)}%)\n"
        f"Cửa sổ trượt 24 giờ: {format_int_vi(ctx['rolling_windows_over'])}/"
        f"{format_int_vi(ctx['rolling_windows_valid'])} = "
        f"{format_number_vi(ctx['rolling_share'] * 100, 2)}% — mẫu số khác, không gộp"
    )
    ax.text(
        0.99,
        0.98,
        note,
        transform=ax.transAxes,
        va="top",
        ha="right",
        fontsize=8.6,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "alpha": 0.88, "edgecolor": PALETTE["grid"]},
    )
    fig.tight_layout()
    return fig


def _figure_autocorrelation(results: Mapping[str, Any]):
    """FIG-12 — ACF của chuỗi ngày và chuỗi giờ (bằng chứng cho block bootstrap)."""
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    dependence = results["dependence"]
    daily = dependence["daily_acf"]
    hourly = dependence["hourly_acf"]
    n_eff = dependence["daily_effective_n"]["n_effective"]
    band = 1.959963984540054 / math.sqrt(n_eff)

    fig, (ax_day, ax_hour) = plt.subplots(1, 2, figsize=(12.2, 4.7))
    apply_tufte_style(ax_day, grid_axis="y")
    apply_tufte_style(ax_hour, grid_axis="y")

    day_lags = sorted(int(lag) for lag in daily)
    day_values = [daily[lag] for lag in day_lags]
    ax_day.vlines(day_lags, 0.0, day_values, color=PALETTE["rolling_24h"], linewidth=1.4)
    ax_day.scatter(day_lags, day_values, s=26, color=PALETTE["rolling_24h"], zorder=3)
    ax_day.axhline(0.0, color=PALETTE["spine"], linewidth=0.8)
    ax_day.axhspan(-band, band, color=PALETTE["grid"], alpha=0.35, label=f"±1,96/√n_eff (n_eff = {format_number_vi(n_eff, 1)})")
    ax_day.set_xlabel("Độ trễ (ngày)")
    ax_day.set_ylabel("Tự tương quan mẫu")
    ax_day.set_title("(a) Chuỗi trung bình ngày", loc="left", fontsize=11)
    ax_day.set_xticks(day_lags)
    ax_day.set_ylim(min(0.0, min(day_values)) - 0.05, max(day_values) * 1.14 + 0.02)
    ax_day.legend(frameon=False, fontsize=8.4, loc="upper right")
    for lag in (1, 7, 14):
        if lag in daily:
            ax_day.annotate(
                format_number_vi(daily[lag], 3),
                xy=(lag, daily[lag]),
                xytext=(0, 7),
                textcoords="offset points",
                ha="center",
                fontsize=8.2,
                color="#2b2b2b",
            )

    hour_lags = sorted(int(lag) for lag in hourly)
    hour_values = [hourly[lag] for lag in hour_lags]
    positions = np.arange(len(hour_lags), dtype=float)
    ax_hour.plot(
        positions,
        hour_values,
        color=PALETTE["rolling_24h"],
        linewidth=1.3,
        marker="o",
        markersize=5,
    )
    ax_hour.axhline(0.0, color=PALETTE["spine"], linewidth=0.8)
    ax_hour.set_xlabel("Độ trễ (giờ)")
    ax_hour.set_ylabel("Tự tương quan mẫu")
    ax_hour.set_title("(b) Chuỗi PM2.5 theo giờ", loc="left", fontsize=11)
    ax_hour.set_xticks(positions)
    ax_hour.set_xticklabels([f"{lag}h" for lag in hour_lags])
    ax_hour.set_xlim(-0.4, len(positions) - 0.6)
    for position, lag in zip(positions, hour_lags):
        ax_hour.annotate(
            format_number_vi(hourly[lag], 3),
            xy=(position, hourly[lag]),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            fontsize=8.2,
            color="#2b2b2b",
        )

    fig.suptitle(
        "Hình 12 — Tự tương quan: vì sao đơn vị phân tích là ngày và CI dùng block bootstrap",
        fontsize=12.2,
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def plot_inference_figures(
    results: Mapping[str, Any],
    output_dir: Optional[Path] = None,
    *,
    dpi: int = 300,
) -> Dict[str, Path]:
    """
    Vẽ và ghi FIG-08…FIG-12 từ payload của `run_inference()`.

    Trả về map `key -> Path` để notebook in ra bằng chứng hình đã ghi. Không
    tính lại thống kê nào: mọi con số trên hình đọc từ `results`.
    """
    import matplotlib.pyplot as plt

    from src.visualizer import _save_figure, configure_vietnamese_fonts

    configure_vietnamese_fonts()
    target_dir = Path(output_dir) if output_dir is not None else FIGURE_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    builders = {
        "distribution": _figure_distribution,
        "season": _figure_season,
        "weekday": _figure_weekday,
        "qcvn": _figure_qcvn,
        "autocorrelation": _figure_autocorrelation,
    }
    written: Dict[str, Path] = {}
    for key, filename in INFERENCE_FIGURES.items():
        fig = builders[key](results)
        path = _save_figure(fig, target_dir / filename, dpi=dpi)
        plt.close(fig)
        if path is not None:
            written[key] = path
    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Chạy toàn bộ suy luận, ghi báo cáo và năm hình của Issue #11."""
    results = run_inference()
    report = render_inference_report(results)
    DEFAULT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT_PATH.write_text(report, encoding="utf-8")
    figures = plot_inference_figures(results)
    print(f"✓ Đã ghi {DEFAULT_REPORT_PATH} ({len(report)} ký tự)")
    for key, path in figures.items():
        print(f"✓ Đã ghi {path} ({key})")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
