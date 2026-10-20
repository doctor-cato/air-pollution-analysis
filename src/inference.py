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
4. **p-value phải được dựng lại dưới H₀ có xét phụ thuộc thời gian** (sửa theo
   review 5586524840 của PR #43). p-value của SciPy trên dữ liệu tự tương quan là
   **lạc quan**; block bootstrap ở điểm 2 chỉ sửa khoảng tin cậy, không sửa
   p-value. Phần "Suy luận có xét tới phụ thuộc thời gian" dựng lại **phân phối
   null dưới H₀** cho từng giả thuyết: block bootstrap trên chuỗi gộp (nhãn
   nhóm giữ theo vị trí lịch, **không** hoán đổi nhãn mùa), block bootstrap có
   áp đặt H₀ cho các kiểm định vị trí, và hồi quy **HAC/Newey–West** cho kiểm
   định mùa (tách mùa khỏi xu hướng thời gian). p-value cũ (giả định độc lập)
   được giữ lại **để đối chiếu**, không phải để kết luận.

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

#: Độ dài block (ngày) cho **mọi** resample có xét phụ thuộc thời gian.
#:
#: Đây là tham số **hiệu chỉnh phụ thuộc**, không phải tham số tự do: mô phỏng dưới
#: H₀ (mục mô phỏng trong báo cáo) cho thấy null bootstrap chỉ đạt size ≈ α khi
#: block ≥ 28 ngày; block 7 ngày (một tuần) còn **lạc quan** (size ≈ 0,17) vì ACF
#: của chuỗi ngày còn 0,32 ở lag 14 — phụ thuộc kéo dài quá hai tuần.
BLOCK_LENGTH_DAYS: int = 28

#: Số lặp cho **hiệu chỉnh phân phối null** (p-value). Tách khỏi CI bootstrap
#: (1.000 lặp) vì p-value bootstrap có **độ phân giải** 2/(B+1): với B = 1.000,
#: p hai phía nhỏ nhất chỉ có thể là 0,002 — mất thông tin về mức độ mạnh của
#: bằng chứng. B = 5.000 hạ độ phân giải xuống 0,0004.
N_NULL_BOOTSTRAP: int = 5_000

#: Lag Newey–West cho hiệp phương sai HAC (ngày). 28 = 4 chu kỳ tuần, khớp với
#: độ dài block bootstrap để hai phương pháp dùng cùng một "chiều sâu phụ thuộc".
HAC_LAG_DAILY: int = 28

#: Các lag HAC dùng cho kiểm tra độ nhạy của kết luận.
HAC_LAG_SENSITIVITY: Tuple[int, ...] = (7, 14, 21, 28, 42)

#: Các độ dài block dùng cho kiểm tra độ nhạy của kết luận.
BLOCK_LENGTH_SENSITIVITY: Tuple[int, ...] = (7, 14, 21, 28, 42)

#: Số lần lặp mô phỏng kiểm soát sai lầm loại I và power.
N_SIMULATIONS: int = 100

#: Số lặp bootstrap trong mô phỏng (nhỏ hơn để mô phỏng chạy nhanh).
N_SIMULATION_BOOTSTRAP: int = 500

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
# Suy luận có xét tới phụ thuộc thời gian
# ---------------------------------------------------------------------------
#
# VÌ SAO CẦN PHẦN NÀY
# ------------------
# Mann-Whitney, Kruskal-Wallis, Wilcoxon và t-test của SciPy đều giả định các
# quan sát **độc lập**. Ở mức ngày, giả định đó sai: ρ₁ ≈ 0,73 ⇒ n_eff ≈ 47 so
# với n = 299. Block bootstrap ở phần trên chỉ sửa **khoảng tin cậy**; p-value
# của SciPy vẫn là p-value của một bài kiểm giả định độc lập — tức **lạc quan**
# (quá nhỏ), và mức lạc quan tỉ lệ với lạm phát ×6,34 của cỡ mẫu hiệu dụng.
#
# Ở đây ta **dựng lại phân phối null dưới H₀** cho từng giả thuyết sao cho cấu
# trúc phụ thuộc của chuỗi được giữ:
#
#   * Hai kiểm định theo nhóm (mùa, weekday/weekend): **circular moving block
#     bootstrap trên chuỗi gộp**, giữ nguyên **nhãn lịch theo vị trí** (KHÔNG
#     hoán đổi nhãn mùa — hoán đổi như vậy phá vỡ cấu trúc mùa vụ), rồi tính
#     lại thống kê trên từng bản sao.
#   * Hai kiểm định vị trí (trung vị so 50, trung bình so 25): **áp đặt H₀** bằng
#     cách trừ mốc (d = x − μ), rồi block bootstrap trên chuỗi đã trừ mốc.
#   * Kiểm định mùa có thêm **hồi quy HAC (Newey–West)** với xu hướng thời gian:
#     bốn mùa là các **đoạn thời gian liên tiếp**, nên nếu không tách xu hướng
#     thì "khác biệt mùa" có thể chỉ là "khác biệt theo thời gian".
#
# KHÔNG dùng bootstrap trên chuỗi quan sát rồi đếm tỷ lệ thống kê cực đoan:
# mọi phân phối null ở đây đều được dựng **dưới H₀** (chuỗi gộp, hoặc chuỗi đã
# trừ mốc) trước khi tính thống kê.


def newey_west_covariance(
    X: np.ndarray, residuals: np.ndarray, lag: int
) -> np.ndarray:
    """
    Hiệp phương sai Newey–West (HAC) cho OLS — kernel Bartlett, hiệu chỉnh n/(n−k).

    Tự viết thay vì gọi statsmodels để `src/` không phụ thuộc thư viện thống kê
    nặng; `tests/test_inference.py` kiểm chứng lại bằng `statsmodels` (thư viện
    độc lập) — nếu hai bản lệch thì test đỏ.
    """
    design = np.asarray(X, dtype=float)
    resid = np.asarray(residuals, dtype=float).ravel()
    if design.ndim != 2:
        raise ValueError("X phải là ma trận 2 chiều.")
    n, k = design.shape
    if resid.size != n:
        raise ValueError(f"Số phần dư ({resid.size}) khác số hàng của X ({n}).")
    if lag < 0:
        raise ValueError(f"lag phải ≥ 0, nhận {lag}.")
    if n <= k:
        raise ValueError(f"Cần n > k, nhận n = {n}, k = {k}.")

    xtx_inv = np.linalg.pinv(design.T @ design)
    meat = np.zeros((k, k), dtype=float)
    for i in range(n):
        xi = design[i][:, None]
        meat += (resid[i] ** 2) * (xi @ xi.T)
    for lag_value in range(1, lag + 1):
        weight = 1.0 - lag_value / (lag + 1.0)
        cross = np.zeros((k, k), dtype=float)
        for i in range(lag_value, n):
            xi = design[i][:, None]
            xj = design[i - lag_value][:, None]
            cross += resid[i] * resid[i - lag_value] * (xi @ xj.T)
        meat += weight * (cross + cross.T)

    cov = xtx_inv @ meat @ xtx_inv
    cov *= n / (n - k)
    return cov


def hac_regression(
    y: Sequence[float],
    X: np.ndarray,
    *,
    lag: int = HAC_LAG_DAILY,
    names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    OLS với hiệp phương sai HAC (Newey–West) — sai số chịu tự tương quan.

    Giả định: sai số có tự tương quan tới bậc `lag` và không tương quan với
    biến giải thích; kernel Bartlett; `lag` đủ lớn để bao trọn phụ thuộc còn
    lại. Ước lượng điểm vẫn là OLS (nhất quán), nhưng hiệp phương sai và p-value
    được hiệu chỉnh cho phụ thuộc.
    """
    y_arr = np.asarray(y, dtype=float).ravel()
    design = np.asarray(X, dtype=float)
    if design.ndim != 2:
        raise ValueError("X phải là ma trận 2 chiều.")
    n, k = design.shape
    if y_arr.size != n:
        raise ValueError(f"Số quan sát của y ({y_arr.size}) khác số hàng của X ({n}).")
    if n <= k:
        raise ValueError(f"Cần n > k, nhận n = {n}, k = {k}.")

    xtx_inv = np.linalg.pinv(design.T @ design)
    beta = xtx_inv @ design.T @ y_arr
    resid = y_arr - design @ beta
    cov = newey_west_covariance(design, resid, lag)
    se = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    df_resid = n - k
    with np.errstate(divide="ignore", invalid="ignore"):
        t_stat = np.where(se > 0, beta / se, np.nan)
    p_values = 2.0 * stats.t.sf(np.abs(t_stat), df_resid)

    ss_resid = float(resid @ resid)
    ss_total = float(((y_arr - y_arr.mean()) ** 2).sum())
    return {
        "coef": beta,
        "cov": cov,
        "se": se,
        "t": t_stat,
        "p": p_values,
        "resid": resid,
        "n": int(n),
        "k": int(k),
        "df_resid": int(df_resid),
        "r2": float(1.0 - ss_resid / ss_total) if ss_total > 0 else float("nan"),
        "lag": int(lag),
        "names": list(names) if names is not None else None,
    }


def joint_wald_test(
    beta: np.ndarray,
    cov: np.ndarray,
    indices: Sequence[int],
    df_resid: int,
) -> Dict[str, float]:
    """
    Kiểm định Wald **đồng thời** cho một tập hệ số bằng 0, dùng hiệp phương sai HAC.

    Thống kê F = (W/q) với W ~ χ²_q; tham chiếu F(q, n−k) để bảo thủ ở mẫu vừa.
    """
    idx = [int(i) for i in indices]
    q = len(idx)
    if q == 0:
        raise ValueError("Cần ít nhất một hệ số để kiểm định Wald.")
    beta_arr = np.asarray(beta, dtype=float).ravel()
    cov_arr = np.asarray(cov, dtype=float)
    restrictions = np.zeros((q, beta_arr.size), dtype=float)
    for position, column in enumerate(idx):
        restrictions[position, column] = 1.0
    r_beta = restrictions @ beta_arr
    r_cov = restrictions @ cov_arr @ restrictions.T
    chi2 = float(r_beta @ np.linalg.pinv(r_cov) @ r_beta)
    f_stat = chi2 / q
    return {
        "statistic": f_stat,
        "chi2": chi2,
        "df1": int(q),
        "df2": int(df_resid),
        "p_value": float(stats.f.sf(f_stat, q, df_resid)),
    }


# ---------------------------------------------------------------------------
# Thống kê kiểm trên nhiều bản sao bootstrap (vector hoá theo hàng)
# ---------------------------------------------------------------------------


def _row_ranks(values_2d: np.ndarray) -> np.ndarray:
    """Hạng trung bình theo từng hàng — `scipy.stats.rankdata` hỗ trợ `axis`."""
    return np.asarray(stats.rankdata(values_2d, axis=1), dtype=float)


def kruskal_statistic_rows(
    values_2d: np.ndarray, group_masks: Sequence[np.ndarray]
) -> np.ndarray:
    """Thống kê H của Kruskal-Wallis cho **từng hàng** của `values_2d`."""
    matrix = np.asarray(values_2d, dtype=float)
    n = matrix.shape[1]
    ranks = _row_ranks(matrix)
    sizes = np.array([int(np.sum(mask)) for mask in group_masks], dtype=float)
    if np.any(sizes < 1):
        raise ValueError("Mỗi nhóm phải có ít nhất 1 quan sát.")
    group_rank_sums = np.vstack([ranks[:, mask].sum(axis=1) for mask in group_masks])
    h = (
        12.0
        / (n * (n + 1))
        * (group_rank_sums ** 2 / sizes[:, None]).sum(axis=0)
        - 3.0 * (n + 1)
    )
    return h


def mannwhitney_statistic_rows(values_2d: np.ndarray, mask_a: np.ndarray) -> np.ndarray:
    """Thống kê U của Mann-Whitney (U của nhóm A) cho **từng hàng**."""
    matrix = np.asarray(values_2d, dtype=float)
    n = matrix.shape[1]
    mask = np.asarray(mask_a, dtype=bool)
    n_a = int(mask.sum())
    if n_a < 1:
        raise ValueError("Nhóm A rỗng.")
    ranks = _row_ranks(matrix)
    return ranks[:, mask].sum(axis=1) - n_a * (n_a + 1) / 2.0


def signed_rank_statistic_rows(deviations_2d: np.ndarray) -> np.ndarray:
    """Thống kê W⁺ của Wilcoxon signed-rank cho **từng hàng**."""
    deviations = np.asarray(deviations_2d, dtype=float)
    ranks = _row_ranks(np.abs(deviations))
    return (ranks * (deviations > 0)).sum(axis=1)


def t_statistic_rows(deviations_2d: np.ndarray) -> np.ndarray:
    """Thống kê t một mẫu cho **từng hàng** (trung bình trên trục 1)."""
    deviations = np.asarray(deviations_2d, dtype=float)
    n = deviations.shape[1]
    means = deviations.mean(axis=1)
    stds = deviations.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(stds > 0, means / (stds / np.sqrt(n)), np.nan)


# ---------------------------------------------------------------------------
# Kiểm định bootstrap với phân phối null dựng DƯỚI H₀
# ---------------------------------------------------------------------------


def block_bootstrap_null_test(
    null_series: Sequence[float],
    *,
    statistic: Any,
    observed_statistic: float,
    alternative: str = "two-sided",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    null_construction: str = "",
    statistic_name: str = "",
) -> Dict[str, Any]:
    """
    Kiểm định bootstrap với **phân phối null dựng dưới H₀**.

    `null_series` là chuỗi **đã nằm trong giả thuyết không**: với kiểm định vị
    trí, đó là `x − μ`; với kiểm định theo nhóm, đó là chuỗi **gộp** của mọi
    nhóm (H₀: các nhóm cùng phân phối). Giá trị được **resample theo block**,
    còn **nhãn/nhóm đi theo vị trí lịch** — nhãn KHÔNG bị hoán đổi ngẫu nhiên.

    `statistic` nhận một ma trận shape ``(n_bootstrap, n)`` và trả về thống kê
    cho từng hàng (vector hoá để chạy nhanh).

    Vùng bác bỏ:
      * ``greater`` — đuôi trên (dùng cho thống kê omnibus không có chiều).
      * ``less`` — đuôi dưới.
      * ``two-sided`` — nhân đôi đuôi nhỏ hơn, chuẩn hoá tại 1.

    p-value dùng bộ hiệu chỉnh ``(1 + số bản sao cực đoan) / (B + 1)`` nên **không
    bao giờ bằng 0**; độ phân giải thấp nhất là ``2/(B+1)`` cho phép hai phía.
    """
    x = np.asarray(null_series, dtype=float).ravel()
    if x.size < 5:
        raise ValueError(f"Cần ≥ 5 quan sát để kiểm định bootstrap, nhận {x.size}.")
    if not np.all(np.isfinite(x)):
        raise ValueError("Chuỗi null chứa NaN/inf — không thể dựng phân phối null.")
    if alternative not in ("two-sided", "greater", "less"):
        raise ValueError(f"alternative không hợp lệ: {alternative!r}.")
    if n_bootstrap < 1:
        raise ValueError(f"n_bootstrap phải ≥ 1, nhận {n_bootstrap}.")

    block = min(block_length, x.size)
    indices = circular_block_indices(
        x.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed
    )
    replicates = np.asarray(statistic(x[indices]), dtype=float).ravel()
    finite = np.isfinite(replicates)
    dropped = int((~finite).sum())
    replicates = replicates[finite]
    if replicates.size == 0:
        raise ValueError("Mọi bản sao bootstrap đều không hữu hạn — không dựng được null.")

    observed = float(observed_statistic)
    n_extreme_ge = int(np.sum(replicates >= observed))
    n_extreme_le = int(np.sum(replicates <= observed))
    p_greater = (1 + n_extreme_ge) / (n_bootstrap + 1)
    p_less = (1 + n_extreme_le) / (n_bootstrap + 1)
    if alternative == "greater":
        p_value = p_greater
    elif alternative == "less":
        p_value = p_less
    else:
        p_value = min(1.0, 2.0 * min(p_greater, p_less))

    return {
        "p_value": float(p_value),
        "p_greater": float(p_greater),
        "p_less": float(p_less),
        "observed_statistic": observed,
        "replicate_median": float(np.median(replicates)),
        "replicate_sd": float(replicates.std(ddof=1)) if replicates.size > 1 else float("nan"),
        "n_bootstrap": int(n_bootstrap),
        "block_length": int(block),
        "seed": int(seed),
        "alternative": alternative,
        "n_extreme": int(n_extreme_ge if alternative == "greater" else n_extreme_le),
        "n_replicates_dropped": dropped,
        "resolution_floor": float(2.0 / (n_bootstrap + 1)),
        "at_resolution_floor": bool(p_value <= 2.0 / (n_bootstrap + 1) + 1e-12),
        "null_construction": null_construction,
        "statistic_name": statistic_name,
    }


# ---------------------------------------------------------------------------
# Thiết kế ma trận cho hồi quy HAC
# ---------------------------------------------------------------------------


def _time_index(panel: pd.DataFrame) -> np.ndarray:
    """Thời gian tính bằng **tháng** kể từ ngày đầu — đơn vị đọc được."""
    dates = pd.to_datetime(panel["date"])
    return (dates - dates.min()).dt.days.to_numpy(dtype=float) / 30.0


def season_design(
    panel: pd.DataFrame, *, trend: str = "linear"
) -> Tuple[np.ndarray, List[str]]:
    """
    Ma trận thiết kế cho hồi quy mùa: `[1, xu hướng, 3 dummy mùa]`.

    Mùa tham chiếu là mùa đầu trong `SEASON_DISPLAY_ORDER` (Đông). Xu hướng
    tuyến tính (hoặc bậc hai) là **bắt buộc** vì bốn mùa là bốn đoạn thời gian
    liên tiếp — không tách xu hướng thì "khác biệt mùa" lẫn với "khác biệt theo
    thời gian".
    """
    if trend not in ("linear", "quadratic"):
        raise ValueError(f"trend phải là 'linear' hoặc 'quadratic', nhận {trend!r}.")
    t = _time_index(panel)
    columns = [np.ones(t.size, dtype=float), t]
    names = ["intercept", "trend"]
    if trend == "quadratic":
        columns.append(t ** 2)
        names.append("trend²")
    seasons = panel["season"].to_numpy()
    for season in SEASON_DISPLAY_ORDER[1:]:
        columns.append((seasons == season).astype(float))
        names.append(season)
    return np.column_stack(columns), names


def weekend_design(
    panel: pd.DataFrame, *, trend: str = "linear"
) -> Tuple[np.ndarray, List[str]]:
    """Ma trận thiết kế `[1, xu hướng, dummy cuối tuần]`."""
    if trend not in ("linear", "quadratic"):
        raise ValueError(f"trend phải là 'linear' hoặc 'quadratic', nhận {trend!r}.")
    t = _time_index(panel)
    columns = [np.ones(t.size, dtype=float), t]
    names = ["intercept", "trend"]
    if trend == "quadratic":
        columns.append(t ** 2)
        names.append("trend²")
    columns.append(panel["is_weekend"].to_numpy(dtype=float))
    names.append("weekend")
    return np.column_stack(columns), names


# ---------------------------------------------------------------------------
# Bốn kiểm định xác nhận — CÓ xét tới phụ thuộc thời gian
# ---------------------------------------------------------------------------


def _status_from_agreement(
    primary_reject: bool,
    supporting: Sequence[bool],
    *,
    sensitivity_stable: bool = True,
) -> Tuple[str, str]:
    """
    Quy tắc hạ mức kết luận — **chốt trước khi xem kết quả**:

    1. Nếu phương pháp chính và phương pháp đối chứng **không cùng chiều kết
       luận** → hạ xuống ``exploratory``.
    2. Nếu kết quả **không ổn định** theo độ dài block / lag HAC → hạ xuống
       ``exploratory``.
    3. Nếu không tính được p hợp lệ → ``not_confirmable``.
    """
    if not sensitivity_stable:
        return "exploratory", (
            "Kết luận không ổn định theo độ dài block / lag HAC → hạ xuống thăm dò."
        )
    if any(bool(s) != bool(primary_reject) for s in supporting):
        return "exploratory", (
            "Phương pháp đối chứng cho kết luận khác chiều phương pháp chính → "
            "hạ xuống thăm dò."
        )
    return "confirmatory", "Phương pháp chính và phương pháp đối chứng cùng chiều."


def hac_signed_rank_test(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    lag: int = HAC_LAG_DAILY,
) -> Dict[str, Any]:
    """
    Wilcoxon signed-rank với **sai số chuẩn HAC (Newey–West)**.

    Thống kê: ``v_i = sign(x_i − μ) · rank(|x_i − μ|)``; kiểm định ``H₀: E[v] = 0``.

    Vì sao: dưới H₀ (quá trình đối xứng quanh μ) dấu của chênh lệch độc lập với
    hạng, nên ``E[v_i] = 0`` và tổng là một thống kê hạng quen thuộc. Với dữ liệu
    tự tương quan, phương sai của trung bình ``v`` **không** còn là công thức
    độc lập → dùng sandwich HAC. Giả định: tính đối xứng quanh μ (H₀) + sai số
    tự tương quan tới bậc L.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát, nhận {x.size}.")
    d = x - mu
    ranks = stats.rankdata(np.abs(d))
    v = np.sign(d) * ranks
    model = hac_regression(v, np.ones((x.size, 1)), lag=lag, names=["signed_rank"])
    return {
        "statistic_name": "t (signed-rank, HAC)",
        "statistic": float(model["t"][0]),
        "se": float(model["se"][0]),
        "p_value": float(model["p"][0]),
        "lag": int(lag),
        "mean_signed_rank": float(v.mean()),
        "n": int(x.size),
    }


def hac_mean_test(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    lag: int = HAC_LAG_DAILY,
) -> Dict[str, Any]:
    """
    t-test một mẫu với **sai số chuẩn HAC (Newey–West)**.

    Mô hình chỉ có hệ số chặn (giá trị trung bình của chuỗi); SE của hệ số
    chặn là ước lượng sandwich của phương sai dài hạn → kiểm định
    ``H₀: trung bình = μ`` có hiệu lực khi quan sát tự tương quan.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát, nhận {x.size}.")
    if float(x.std(ddof=1)) == 0.0:
        raise ValueError(
            "Chuỗi hằng: độ lệch chuẩn bằng 0 nên sai số HAC (và p-value) không xác định."
        )
    model = hac_regression(x, np.ones((x.size, 1)), lag=lag, names=["mean"])
    se = float(model["se"][0])
    t_stat = (float(model["coef"][0]) - float(mu)) / se
    df_resid = int(x.size - 1)
    return {
        "statistic_name": "t (HAC)",
        "statistic": float(t_stat),
        "se": se,
        "df": df_resid,
        "p_value": float(2.0 * stats.t.sf(abs(t_stat), df_resid)),
        "ci": {
            "ci_low": float(model["coef"][0] - stats.t.ppf(0.975, df_resid) * se),
            "ci_high": float(model["coef"][0] + stats.t.ppf(0.975, df_resid) * se),
        },
        "lag": int(lag),
        "n": int(x.size),
    }


def null_imposed_centered_test(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    statistic: str = "t",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    Kiểm định bootstrap **áp đặt H₀** cho một đại lượng vị trí.

    Cách dựng null (KHÔNG phải "bootstrap trên chuỗi quan sát rồi đếm tỷ lệ
    thống kê cực đoan"):

    1. Tách nhiễu ước lượng: ``ê = x − θ̂`` với ``θ̂`` là ước lượng vị trí của
       chính dữ liệu (trung bình hoặc trung vị).
    2. Resample ``ê`` theo block → ``ê*`` (giữ cấu trúc phụ thuộc).
    3. Dựng bản sao **dưới H₀**: ``x* = μ + ê*``.
    4. Tính thống kê trên ``x*`` (tức trên ``ê*``) → phân phối null.
    5. So thống kê quan sát (trên ``x − μ``) với phân phối null đó.

    Với trung bình, bước 1 dùng chính xác trung bình mẫu nên ``ê`` có trung
    bình bằng 0 và giả định H₀ được áp đặt đúng. Với trung vị, bước 1 dùng
    trung vị mẫu — đây là xấp xỉ (trung vị không phải hàm tuyến tính), nên kết
    quả được đọc cùng phương pháp HAC.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát, nhận {x.size}.")
    if statistic not in ("t", "signed_rank"):
        raise ValueError(f"statistic phải là 't' hoặc 'signed_rank', nhận {statistic!r}.")

    if statistic == "t":
        centre = float(x.mean())
        observed = float(stats.ttest_1samp(x, popmean=mu).statistic)
        stat_fn = t_statistic_rows
    else:
        centre = float(np.median(x))
        scipy_result = stats.wilcoxon(
            x - mu, alternative="two-sided", zero_method="wilcox", correction=False
        )
        observed = float(scipy_result.statistic)
        stat_fn = signed_rank_statistic_rows

    noise = x - centre
    block = min(block_length, x.size)
    indices = circular_block_indices(
        x.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed
    )
    replicates = np.asarray(stat_fn(noise[indices]), dtype=float).ravel()
    replicates = replicates[np.isfinite(replicates)]
    if replicates.size == 0:
        raise ValueError("Mọi bản sao bootstrap không hữu hạn.")
    p_greater = (1 + int(np.sum(replicates >= observed))) / (n_bootstrap + 1)
    p_less = (1 + int(np.sum(replicates <= observed))) / (n_bootstrap + 1)
    p_value = min(1.0, 2.0 * min(p_greater, p_less))
    return {
        "p_value": float(p_value),
        "observed_statistic": observed,
        "centre": centre,
        "mu": float(mu),
        "statistic": statistic,
        "block_length": int(block),
        "n_bootstrap": int(n_bootstrap),
        "seed": int(seed),
        "resolution_floor": float(2.0 / (n_bootstrap + 1)),
        "at_resolution_floor": bool(p_value <= 2.0 / (n_bootstrap + 1) + 1e-12),
    }


def bootstrap_percentile_pvalue(
    values: Sequence[float],
    *,
    mu: float,
    statistic: str = "median",
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    p-value **suy ra từ chính phân phối bootstrap** của ước lượng (đảo CI).

    ``p = P(|θ̂* − θ̂| ≥ |μ − θ̂|)`` với ``θ̂*`` là ước lượng trên mỗi bản sao
    block bootstrap. Ưu điểm: **nhất quán với khoảng tin cậy** cùng phương pháp
    (cùng một phân phối bootstrap) — người đọc có thể kiểm tra p bằng CI. Nhược
    điểm: không phải phân phối null dưới H₀ ⇒ dùng làm **đối chứng**, không
    dùng làm phương pháp chính.
    """
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 8:
        raise ValueError(f"Cần ≥ 8 quan sát, nhận {x.size}.")
    reducer = {"median": np.median, "mean": np.mean}.get(statistic)
    if reducer is None:
        raise ValueError(f"statistic phải là 'median' hoặc 'mean', nhận {statistic!r}.")
    block = min(block_length, x.size)
    indices = circular_block_indices(
        x.size, block_length=block, n_bootstrap=n_bootstrap, seed=seed
    )
    replicates = reducer(x[indices], axis=1)
    observed = float(reducer(x))
    deviation = abs(float(mu) - observed)
    p_value = (1 + int(np.sum(np.abs(replicates - observed) >= deviation))) / (n_bootstrap + 1)
    return {
        "p_value": float(p_value),
        "observed": observed,
        "mu": float(mu),
        "statistic": statistic,
        "block_length": int(block),
        "n_bootstrap": int(n_bootstrap),
        "seed": int(seed),
    }


def _season_effect_test(
    panel: pd.DataFrame,
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    hac_lag: int = HAC_LAG_DAILY,
) -> Dict[str, Any]:
    """
    Kiểm định 1 — khác biệt giữa bốn mùa, **có xét phụ thuộc thời gian**.

    H₀: trong một quá trình ổn định, phân phối trung bình ngày giống nhau ở cả
    bốn mùa. H₁: có ít nhất một mùa khác.

    * **Phương pháp chính:** Kruskal-Wallis với phân phối null dựng bằng
      **circular moving block bootstrap** trên chuỗi **gộp**; nhãn mùa **giữ
      theo vị trí lịch** (không hoán đổi nhãn). Mô phỏng cho thấy phương pháp
      này đạt size ≈ α khi block ≥ 28 ngày (mục mô phỏng trong báo cáo).
    * **Đối chứng:** hồi quy **HAC/Newey–West** `[1, xu hướng, 3 dummy mùa]`,
      kiểm định Wald đồng thời — dùng để **tách mùa khỏi xu hướng thời gian**
      (bốn mùa là bốn đoạn thời gian liên tiếp).
    """
    values = panel["pm25_mean"].to_numpy(dtype=float)
    seasons = panel["season"].to_numpy()
    masks = [np.asarray(seasons == season, dtype=bool) for season in SEASON_DISPLAY_ORDER]
    groups = [values[mask] for mask in masks]
    if min(group.size for group in groups) < 3:
        raise ValueError("Mỗi mùa cần ≥ 3 ngày để kiểm định.")

    kw = stats.kruskal(*groups)
    null_boot = block_bootstrap_null_test(
        values,
        statistic=lambda matrix: kruskal_statistic_rows(matrix, masks),
        observed_statistic=float(kw.statistic),
        alternative="greater",
        block_length=block_length,
        n_bootstrap=n_bootstrap,
        seed=seed,
        null_construction=(
            "Chuỗi gộp toàn bộ ngày, resample theo block tròn; nhãn mùa giữ theo "
            "vị trí lịch (không hoán đổi nhãn mùa)."
        ),
        statistic_name="H",
    )

    X, names = season_design(panel, trend="linear")
    model = hac_regression(values, X, lag=hac_lag, names=names)
    season_columns = [i for i, name in enumerate(names) if name not in ("intercept", "trend")]
    wald = joint_wald_test(model["coef"], model["cov"], season_columns, model["df_resid"])

    X_quad, names_quad = season_design(panel, trend="quadratic")
    model_quad = hac_regression(values, X_quad, lag=hac_lag, names=names_quad)
    wald_quad = joint_wald_test(
        model_quad["coef"],
        model_quad["cov"],
        [i for i, name in enumerate(names_quad) if name not in ("intercept", "trend")],
        model_quad["df_resid"],
    )
    lag_sensitivity = {}
    for lag_value in HAC_LAG_SENSITIVITY:
        lagged = hac_regression(values, X, lag=lag_value, names=names)
        lagged_wald = joint_wald_test(
            lagged["coef"], lagged["cov"], season_columns, lagged["df_resid"]
        )
        lag_sensitivity[str(lag_value)] = {
            "p_value": float(lagged_wald["p_value"]),
            "statistic": float(lagged_wald["statistic"]),
        }
    block_sensitivity = {}
    for block_value in BLOCK_LENGTH_SENSITIVITY:
        block_boot = block_bootstrap_null_test(
            values,
            statistic=lambda matrix: kruskal_statistic_rows(matrix, masks),
            observed_statistic=float(kw.statistic),
            alternative="greater",
            block_length=block_value,
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        block_sensitivity[str(block_value)] = {
            "p_value": block_boot["p_value"],
            "block_length": int(block_value),
        }

    primary_reject = bool(null_boot["p_value"] < ALPHA)
    supporting_reject = bool(wald["p_value"] < ALPHA)
    primary_stable = all(
        bool(entry["p_value"] < ALPHA) == primary_reject
        for entry in block_sensitivity.values()
    )
    status, reason = _status_from_agreement(
        primary_reject, [supporting_reject], sensitivity_stable=primary_stable
    )

    return {
        "test": "season_effect",
        "key": "season_effect",
        "label": "Mùa (4 nhóm, xét phụ thuộc thời gian)",
        "h0": (
            "Phân phối trung bình ngày giống nhau ở cả bốn mùa (trong một quá trình "
            "ổn định trong giai đoạn quan sát)."
        ),
        "h1": "Có ít nhất một mùa khác.",
        "unit": "Trung bình ngày (≥ 18/24 giờ có `pm25`).",
        "alternative": "omnibus (đuôi trên của H)",
        "statistic_name": "H",
        "statistic": float(kw.statistic),
        "df": 3,
        "p_value": float(null_boot["p_value"]),
        "p_value_independence": float(kw.pvalue),
        "effect_size_name": "epsilon_squared",
        "effect_size": float(min(max(kw.statistic / (values.size - 1), 0.0), 1.0)),
        "group_sizes": {
            season: int(mask.sum()) for season, mask in zip(SEASON_DISPLAY_ORDER, masks)
        },
        "group_medians": {
            season: float(np.median(group))
            for season, group in zip(SEASON_DISPLAY_ORDER, groups)
        },
        "n": int(values.size),
        "method": {
            "primary": "Kruskal-Wallis + null circular moving block bootstrap (chuỗi gộp)",
            "primary_block_length": int(block_length),
            "supporting": "OLS + HAC (Newey–West) với xu hướng thời gian, Wald đồng thời",
            "supporting_lag": int(hac_lag),
            "assumptions": (
                "Chuỗi gộp ổn định trong giai đoạn quan sát; block ≥ 28 ngày bao trọn "
                "phụ thuộc còn lại; nhãn mùa gắn theo vị trí lịch nên cấu trúc mùa "
                "vụ không bị phá vỡ; phương pháp đối chứng dùng HAC để tách mùa khỏi "
                "xu hướng."
            ),
        },
        "supporting_result": {
            "name": "F (HAC, có xu hướng)",
            "statistic": float(wald["statistic"]),
            "df1": int(wald["df1"]),
            "df2": int(wald["df2"]),
            "p_value": float(wald["p_value"]),
            "quadratic_trend_p": float(wald_quad["p_value"]),
            "trend_per_month": float(model["coef"][1]),
            "r2": float(model["r2"]),
        },
        "supporting_detail": {
            "coef": model["coef"],
            "se": model["se"],
            "t": model["t"],
            "p": model["p"],
            "names": names,
        },
        "null_bootstrap": null_boot,
        "sensitivity": {"block_length": block_sensitivity, "hac_lag": lag_sensitivity},
        "status": status,
        "status_reason": reason,
    }


def _weekday_effect_test(
    panel: pd.DataFrame,
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    hac_lag: int = HAC_LAG_DAILY,
) -> Dict[str, Any]:
    """
    Kiểm định 2 — ngày làm việc vs ngày cuối tuần, **có xét phụ thuộc thời gian**.

    H₀: phân phối trung bình ngày của ngày làm việc và ngày cuối tuần giống
    nhau. H₁: khác nhau.

    * **Phương pháp chính:** Mann-Whitney U với phân phối null dựng bằng
      **circular moving block bootstrap** trên chuỗi **gộp**; nhãn
      weekday/weekend **giữ theo vị trí lịch** → cấu trúc tuần không bị phá vỡ.
    * **Đối chứng:** hồi quy **HAC** `[1, xu hướng, dummy cuối tuần]`.
    """
    values = panel["pm25_mean"].to_numpy(dtype=float)
    is_weekend = panel["is_weekend"].to_numpy(dtype=int)
    mask_a = is_weekend == 0
    mask_b = ~mask_a
    if mask_a.sum() < 3 or mask_b.sum() < 3:
        raise ValueError("Mỗi nhóm cần ≥ 3 ngày để kiểm định.")

    mw = stats.mannwhitneyu(values[mask_a], values[mask_b], alternative="two-sided")
    null_boot = block_bootstrap_null_test(
        values,
        statistic=lambda matrix: mannwhitney_statistic_rows(matrix, mask_a),
        observed_statistic=float(mw.statistic),
        alternative="two-sided",
        block_length=block_length,
        n_bootstrap=n_bootstrap,
        seed=seed,
        null_construction=(
            "Chuỗi gộp toàn bộ ngày, resample theo block tròn; nhãn weekday/weekend "
            "giữ theo vị trí lịch (không hoán đổi nhãn)."
        ),
        statistic_name="U",
    )

    X, names = weekend_design(panel, trend="linear")
    model = hac_regression(values, X, lag=hac_lag, names=names)
    weekend_index = names.index("weekend")
    hac_t = float(model["t"][weekend_index])
    hac_p = float(model["p"][weekend_index])

    lag_sensitivity = {}
    for lag_value in HAC_LAG_SENSITIVITY:
        lagged = hac_regression(values, X, lag=lag_value, names=names)
        lag_sensitivity[str(lag_value)] = {
            "p_value": float(lagged["p"][weekend_index]),
            "statistic": float(lagged["t"][weekend_index]),
        }
    block_sensitivity = {}
    for block_value in BLOCK_LENGTH_SENSITIVITY:
        block_boot = block_bootstrap_null_test(
            values,
            statistic=lambda matrix: mannwhitney_statistic_rows(matrix, mask_a),
            observed_statistic=float(mw.statistic),
            alternative="two-sided",
            block_length=block_value,
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        block_sensitivity[str(block_value)] = {
            "p_value": block_boot["p_value"],
            "block_length": int(block_value),
        }

    primary_reject = bool(null_boot["p_value"] < ALPHA)
    supporting_reject = bool(hac_p < ALPHA)
    primary_stable = all(
        bool(entry["p_value"] < ALPHA) == primary_reject
        for entry in block_sensitivity.values()
    )
    status, reason = _status_from_agreement(
        primary_reject, [supporting_reject], sensitivity_stable=primary_stable
    )

    return {
        "test": "weekday_effect",
        "key": "weekday_effect",
        "label": "Ngày làm việc vs cuối tuần (xét phụ thuộc thời gian)",
        "h0": "Phân phối PM2.5 trung bình ngày của ngày làm việc và cuối tuần giống nhau.",
        "h1": "Hai phân phối khác nhau.",
        "unit": "Trung bình ngày (≥ 18/24 giờ có `pm25`).",
        "alternative": "hai phía",
        "statistic_name": "U",
        "statistic": float(mw.statistic),
        "p_value": float(null_boot["p_value"]),
        "p_value_independence": float(mw.pvalue),
        "n_a": int(mask_a.sum()),
        "n_b": int(mask_b.sum()),
        "n": int(values.size),
        "median_a": float(np.median(values[mask_a])),
        "median_b": float(np.median(values[mask_b])),
        "mean_a": float(values[mask_a].mean()),
        "mean_b": float(values[mask_b].mean()),
        "median_difference": float(np.median(values[mask_a]) - np.median(values[mask_b])),
        "mean_difference": float(values[mask_a].mean() - values[mask_b].mean()),
        "effect_size_name": "r_rb",
        "effect_size": float(2.0 * mw.statistic / (mask_a.sum() * mask_b.sum()) - 1.0),
        "method": {
            "primary": "Mann-Whitney U + null circular moving block bootstrap (chuỗi gộp)",
            "primary_block_length": int(block_length),
            "supporting": "OLS + HAC (Newey–West), hệ số dummy cuối tuần",
            "supporting_lag": int(hac_lag),
            "assumptions": (
                "Chuỗi gộp ổn định trong giai đoạn quan sát; block ≥ 28 ngày bao trọn "
                "phụ thuộc còn lại; nhãn nhóm đi theo vị trí lịch nên xen kẽ tuần được "
                "giữ nguyên."
            ),
        },
        "supporting_result": {"name": "t (HAC)", "p_value": hac_p, "statistic": hac_t},
        "null_bootstrap": null_boot,
        "sensitivity": {"block_length": block_sensitivity, "hac_lag": lag_sensitivity},
        "status": status,
        "status_reason": reason,
    }


def _location_effect_test(
    panel: pd.DataFrame,
    *,
    mu: float,
    kind: str,
    label: str,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    hac_lag: int = HAC_LAG_DAILY,
) -> Dict[str, Any]:
    """
    Kiểm định vị trí (hai ngưỡng QCVN), **có xét phụ thuộc thời gian**.

    ``kind="median"`` → H₀: trung vị của trung bình ngày = μ.
    ``kind="mean"``   → H₀: trung bình của trung bình ngày = μ.

    * **Phương pháp chính (mean):** t-test một mẫu với **sai số HAC
      (Newey–West)** — sandwich của phương sai dài hạn.
    * **Phương pháp chính (median):** kiểm định **tỷ lệ vượt ngưỡng** với HAC.
      H₀ "trung vị = μ" tương đương "P(x > μ) = 0,5" với phân phối liên tục; thống
      kê là tỷ lệ ngày vượt, SE là sandwich HAC. (Bản signed-rank có HAC cũng
      được tính, nhưng dãy chênh lệch lớn rất bền nên SE HAC của nó bị thổi
      phồng → kém sức; xem phần đối chứng.)
    * **Đối chứng:** bootstrap **áp đặt H₀** (tách nhiễu rồi dựng bản sao dưới
      H₀) và p-value suy ra từ chính phân phối bootstrap của ước lượng (đảo CI).
    """
    if kind not in ("median", "mean"):
        raise ValueError(f"kind phải là 'median' hoặc 'mean', nhận {kind!r}.")
    values = panel["pm25_mean"].to_numpy(dtype=float)
    if values.size < 8:
        raise ValueError(f"Cần ≥ 8 ngày, nhận {values.size}.")

    if kind == "mean":
        hac = hac_mean_test(values, mu=mu, lag=hac_lag)
        null_imposed = null_imposed_centered_test(
            values, mu=mu, statistic="t", block_length=block_length,
            n_bootstrap=n_bootstrap, seed=seed,
        )
        percentile = bootstrap_percentile_pvalue(
            values, mu=mu, statistic="mean", block_length=block_length,
            n_bootstrap=n_bootstrap, seed=seed,
        )
        signed_rank = hac_signed_rank_test(values, mu=mu, lag=hac_lag)
        effect_name = "cohen_d"
        effect = float((values.mean() - mu) / values.std(ddof=1))
        scipy_result = stats.ttest_1samp(values, popmean=mu, alternative="two-sided")
        primary_name = "t (HAC, Newey–West)"
        primary_description = (
            "t-test một mẫu với sai số chuẩn HAC: mô hình chỉ có hệ số chặn, SE là "
            "ước lượng sandwich của phương sai dài hạn."
        )
    else:
        share = (values > mu).astype(float)
        hac_share_model = hac_regression(
            share, np.ones((values.size, 1)), lag=hac_lag, names=["share"]
        )
        se_share = float(hac_share_model["se"][0])
        t_share = (float(hac_share_model["coef"][0]) - 0.5) / se_share
        df_resid = int(values.size - 1)
        hac = {
            "statistic_name": "t (share, HAC)",
            "statistic": float(t_share),
            "se": se_share,
            "df": df_resid,
            "p_value": float(2.0 * stats.t.sf(abs(t_share), df_resid)),
            "ci": {
                "ci_low": float(hac_share_model["coef"][0] - stats.t.ppf(0.975, df_resid) * se_share),
                "ci_high": float(hac_share_model["coef"][0] + stats.t.ppf(0.975, df_resid) * se_share),
            },
            "lag": int(hac_lag),
            "n": int(values.size),
            "share": float(share.mean()),
        }
        null_imposed = null_imposed_centered_test(
            values, mu=mu, statistic="signed_rank", block_length=block_length,
            n_bootstrap=n_bootstrap, seed=seed,
        )
        percentile = bootstrap_percentile_pvalue(
            values, mu=mu, statistic="median", block_length=block_length,
            n_bootstrap=n_bootstrap, seed=seed,
        )
        signed_rank = hac_signed_rank_test(values, mu=mu, lag=hac_lag)
        effect_name = "r_rb_pairs"
        d = values - mu
        ranks = stats.rankdata(np.abs(d))
        signs = np.sign(d)
        w_plus = float(ranks[signs > 0].sum())
        w_minus = float(ranks[signs < 0].sum())
        effect = (w_plus - w_minus) / (w_plus + w_minus) if (w_plus + w_minus) > 0 else float("nan")
        scipy_result = stats.wilcoxon(
            d, alternative="two-sided", zero_method="wilcox", correction=False
        )
        primary_name = "t (tỷ lệ vượt ngưỡng, HAC)"
        primary_description = (
            "H₀ 'trung vị = μ' tương đương 'P(trung bình ngày > μ) = 0,5' với phân "
            "phối liên tục; thống kê là tỷ lệ ngày vượt ngưỡng, SE là sandwich HAC."
        )

    lag_sensitivity = {}
    for lag_value in HAC_LAG_SENSITIVITY:
        if kind == "mean":
            entry = hac_mean_test(values, mu=mu, lag=lag_value)
        else:
            share = (values > mu).astype(float)
            model = hac_regression(share, np.ones((values.size, 1)), lag=lag_value)
            se_value = float(model["se"][0])
            t_value = (float(model["coef"][0]) - 0.5) / se_value
            entry = {
                "p_value": float(2.0 * stats.t.sf(abs(t_value), values.size - 1)),
                "statistic": float(t_value),
            }
        lag_sensitivity[str(lag_value)] = {
            "p_value": entry["p_value"],
            "statistic": entry["statistic"],
        }
    block_sensitivity = {}
    for block_value in BLOCK_LENGTH_SENSITIVITY:
        entry = null_imposed_centered_test(
            values, mu=mu,
            statistic="t" if kind == "mean" else "signed_rank",
            block_length=block_value, n_bootstrap=n_bootstrap, seed=seed,
        )
        block_sensitivity[str(block_value)] = {
            "p_value": entry["p_value"],
            "block_length": int(block_value),
        }

    primary_reject = bool(hac["p_value"] < ALPHA)
    supporting_reject = bool(null_imposed["p_value"] < ALPHA)
    primary_stable = all(
        bool(entry["p_value"] < ALPHA) == primary_reject for entry in lag_sensitivity.values()
    )
    status, reason = _status_from_agreement(
        primary_reject, [supporting_reject], sensitivity_stable=primary_stable
    )

    return {
        "test": f"{kind}_location",
        "key": f"qcvn_{'24h' if kind == 'median' else 'annual'}",
        "kind": kind,
        "mu": float(mu),
        "label": label,
        "h0": (
            f"{'Trung vị' if kind == 'median' else 'Trung bình'} của trung bình ngày "
            f"bằng {format_number_vi(mu, 0)} µg/m³."
        ),
        "h1": f"{'Trung vị' if kind == 'median' else 'Trung bình'} khác {format_number_vi(mu, 0)} µg/m³.",
        "unit": "Trung bình ngày (≥ 18/24 giờ có `pm25`).",
        "alternative": "hai phía",
        "statistic_name": hac["statistic_name"],
        "statistic": float(hac["statistic"]),
        "p_value": float(hac["p_value"]),
        "p_value_independence": float(scipy_result.pvalue),
        "n": int(values.size),
        "effect_size_name": effect_name,
        "effect_size": float(effect),
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)),
        "median": float(np.median(values)),
        "mean_difference": float(values.mean() - mu),
        "median_difference": float(np.median(values) - mu),
        "method": {
            "primary": primary_description,
            "primary_name": primary_name,
            "primary_lag": int(hac_lag),
            "supporting": "Bootstrap áp đặt H₀ + p-value đảo CI (cùng phân phối bootstrap)",
            "assumptions": (
                "Sai số tự tương quan tới bậc L và không tương quan với biến giải "
                "thích; L đủ lớn để bao trọn phụ thuộc còn lại; phân phối liên tục "
                "(để trung vị tương đương tỷ lệ vượt 50%); chuỗi ổn định trong giai "
                "đoạn quan sát."
            ),
        },
        "supporting_result": {
            "null_imposed_p": float(null_imposed["p_value"]),
            "percentile_p": float(percentile["p_value"]),
            "signed_rank_hac_p": float(signed_rank["p_value"]),
        },
        "hac_detail": hac,
        "null_imposed": null_imposed,
        "percentile": percentile,
        "signed_rank_hac": signed_rank,
        "sensitivity": {"hac_lag": lag_sensitivity, "block_length": block_sensitivity},
        "status": status,
        "status_reason": reason,
    }


# ---------------------------------------------------------------------------
# Chẩn đoán khả năng khái quát hóa theo mùa
# ---------------------------------------------------------------------------


def _season_year(dates: pd.Series, seasons: pd.Series) -> pd.Series:
    """
    Năm **của mùa** (không phải năm dương lịch).

    Mùa Đông (12–2) bắt đầu từ tháng 12 nên tháng 12/2025 và tháng 1–2/2026 là
    **cùng một mùa Đông**. Gán theo năm dương lịch sẽ tách một mùa thành hai
    "năm" và làm sai lệch mọi so sánh giữa các năm.
    """
    year = pd.Series(pd.to_datetime(dates)).dt.year.to_numpy(dtype=int)
    month = pd.Series(pd.to_datetime(dates)).dt.month.to_numpy(dtype=int)
    is_december_winter = (seasons.to_numpy() == "Dong") & (month == 12)
    return pd.Series(year + is_december_winter.astype(int), index=seasons.index)


def season_generalization_diagnostics(panel: pd.DataFrame) -> Dict[str, Any]:
    """
    Đo những gì cần để trả lời: "khác biệt mùa có suy rộng được sang năm khác không?"

    Bốn đại lượng:
      1. **Số chu kỳ mùa quan sát được** — dữ liệu chỉ có một vòng mùa.
      2. **Cân bằng mẫu và độ phủ giữa các mùa** — mùa nào nhiều ngày hơn, mùa
         nào mất nhiều ngày hơn (thiếu hụt không ngẫu nhiên).
      3. **Độ lớn xu hướng tuyến tính** so với độ lớn khác biệt mùa — để biết
         "mùa" có thể chỉ là "xu hướng" đến mức nào.
      4. **Cùng một mùa ở hai năm khác nhau** — mùa nào xuất hiện ở ≥ 2 mùa-vụ
         để đối chiếu được giữa các năm (chỉ Hè trong dữ liệu này, và chỉ một
         phần).
    """
    panel = panel.copy()
    dates = pd.to_datetime(panel["date"])
    panel["season_year"] = _season_year(dates, panel["season"])
    by_season_year = (
        panel.groupby(["season", "season_year"], observed=True)["pm25_mean"]
        .agg(["size", "median", "min", "max"])
        .reset_index()
    )
    seasons_with_years: Dict[str, List[int]] = {}
    for season in SEASON_DISPLAY_ORDER:
        years = sorted(
            int(y) for y in by_season_year.loc[by_season_year["season"] == season, "season_year"]
        )
        seasons_with_years[season] = years

    full_grid = pd.date_range(dates.min(), dates.max(), freq="D")
    calendar_season = full_grid.month.map(SEASON_MONTHS)
    calendar_counts = calendar_season.value_counts()
    kept_counts = panel["season"].value_counts()

    coverage = {}
    for season in SEASON_DISPLAY_ORDER:
        calendar_days = int(calendar_counts.get(season, 0))
        kept_days = int(kept_counts.get(season, 0))
        coverage[season] = {
            "calendar_days": calendar_days,
            "kept_days": kept_days,
            "dropped_days": max(0, calendar_days - kept_days),
            "kept_share": float(kept_days / calendar_days) if calendar_days else float("nan"),
        }

    values = panel["pm25_mean"].to_numpy(dtype=float)
    X, names = season_design(panel, trend="linear")
    model = hac_regression(values, X, lag=HAC_LAG_DAILY, names=names)
    trend_per_month = float(model["coef"][1])

    season_medians = {
        season: float(np.median(panel.loc[panel["season"] == season, "pm25_mean"]))
        for season in SEASON_DISPLAY_ORDER
    }
    contrast = max(season_medians.values()) - min(season_medians.values())

    repeated = {
        season: years for season, years in seasons_with_years.items() if len(years) >= 2
    }
    return {
        "n_seasonal_cycles": 1,
        "seasons_with_multiple_years": repeated,
        "season_year_breakdown": by_season_year,
        "coverage": coverage,
        "trend_per_month": trend_per_month,
        "trend_over_period": trend_per_month * 12.0,
        "season_medians": season_medians,
        "max_season_contrast": float(contrast),
        "trend_to_contrast_ratio": (
            float(abs(trend_per_month * 12.0) / contrast) if contrast > 0 else float("nan")
        ),
        "note": (
            "Một chu kỳ mùa duy nhất: mọi khác biệt mùa quan sát được đều trộn với "
            "xu hướng thời gian và với điều kiện khí tượng của chính năm đó."
        ),
    }


# ---------------------------------------------------------------------------
# Mô phỏng kiểm soát sai lầm loại I và power
# ---------------------------------------------------------------------------


def ar1_series(
    n: int, rho: float, *, sigma: float = 1.0, seed: int = 0, burn_in: int = 200
) -> np.ndarray:
    """
    Chuỗi AR(1): ``x_t = rho·x_{t−1} + ε_t`` — dùng cho mô phỏng kiểm soát size.

    `burn_in` bỏ đầu chuỗi để trạng thái khởi đầu không ảnh hưởng kết quả.
    """
    if n < 1:
        raise ValueError(f"n phải ≥ 1, nhận {n}.")
    if not -1.0 < rho < 1.0:
        raise ValueError(f"rho phải trong (-1, 1), nhận {rho}.")
    from scipy import signal

    rng = np.random.default_rng(seed)
    total = n + burn_in
    innovations = rng.normal(0.0, sigma, total)
    filtered = signal.lfilter([1.0], [1.0, -rho], innovations)
    return filtered[burn_in:]


def _simulation_procedures(
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_SIMULATION_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    hac_lag: int = HAC_LAG_DAILY,
) -> Dict[str, Dict[str, Any]]:
    """
    Bốn phép kiểm dưới dạng hàm nhận mảng giá trị (theo thứ tự lịch).

    Mỗi hàm trả về ba p-value:
      * ``p_independence`` — phép kiểm SciPy giả định quan sát độc lập;
      * ``p_dependence_aware`` — phương pháp **chính** đã hiệu chỉnh phụ thuộc;
      * ``p_supporting`` — phương pháp đối chứng đã hiệu chỉnh phụ thuộc.

    Quy ước nhóm trong mô phỏng (khớp với dữ liệu thật ở mức cấu trúc):
      * mùa: bốn đoạn liên tiếp, mỗi đoạn ``n/4`` ngày;
      * cuối tuần: mọi ngày có ``index % 7 >= 5``.
    """
    def season(values: np.ndarray) -> Dict[str, float]:
        n = values.size
        positions = np.arange(n)
        masks = [np.asarray((positions * 4 // n) == g, dtype=bool) for g in range(4)]
        groups = [values[m] for m in masks]
        kw = stats.kruskal(*groups)
        boot = block_bootstrap_null_test(
            values,
            statistic=lambda matrix: kruskal_statistic_rows(matrix, masks),
            observed_statistic=float(kw.statistic),
            alternative="greater",
            block_length=block_length,
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        design = np.column_stack(
            [np.ones(n), positions / 30.0] + [m.astype(float) for m in masks[1:]]
        )
        model = hac_regression(values, design, lag=hac_lag)
        wald = joint_wald_test(model["coef"], model["cov"], [2, 3, 4], model["df_resid"])
        return {
            "p_independence": float(kw.pvalue),
            "p_dependence_aware": float(boot["p_value"]),
            "p_supporting": float(wald["p_value"]),
        }

    def weekday(values: np.ndarray) -> Dict[str, float]:
        n = values.size
        positions = np.arange(n)
        mask_a = np.asarray((positions % 7) < 5, dtype=bool)
        mw = stats.mannwhitneyu(values[mask_a], values[~mask_a], alternative="two-sided")
        boot = block_bootstrap_null_test(
            values,
            statistic=lambda matrix: mannwhitney_statistic_rows(matrix, mask_a),
            observed_statistic=float(mw.statistic),
            alternative="two-sided",
            block_length=block_length,
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
        design = np.column_stack(
            [np.ones(n), positions / 30.0, (~mask_a).astype(float)]
        )
        model = hac_regression(values, design, lag=hac_lag)
        return {
            "p_independence": float(mw.pvalue),
            "p_dependence_aware": float(boot["p_value"]),
            "p_supporting": float(model["p"][2]),
        }

    def median(values: np.ndarray) -> Dict[str, float]:
        share = (values > 0.0).astype(float)
        model = hac_regression(share, np.ones((values.size, 1)), lag=hac_lag)
        se = float(model["se"][0])
        t_stat = (float(model["coef"][0]) - 0.5) / se
        hac_p = float(2.0 * stats.t.sf(abs(t_stat), values.size - 1))
        null_imposed = null_imposed_centered_test(
            values, mu=0.0, statistic="signed_rank",
            block_length=block_length, n_bootstrap=n_bootstrap, seed=seed,
        )
        return {
            "p_independence": float(
                stats.wilcoxon(values, alternative="two-sided").pvalue
            ),
            "p_dependence_aware": hac_p,
            "p_supporting": float(null_imposed["p_value"]),
        }

    def mean(values: np.ndarray) -> Dict[str, float]:
        hac = hac_mean_test(values, mu=0.0, lag=hac_lag)
        null_imposed = null_imposed_centered_test(
            values, mu=0.0, statistic="t",
            block_length=block_length, n_bootstrap=n_bootstrap, seed=seed,
        )
        return {
            "p_independence": float(stats.ttest_1samp(values, popmean=0.0).pvalue),
            "p_dependence_aware": float(hac["p_value"]),
            "p_supporting": float(null_imposed["p_value"]),
        }

    return {
        "season": {"callable": season, "effect": "seasonal"},
        "weekday": {"callable": weekday, "effect": "weekly"},
        "median": {"callable": median, "effect": "location"},
        "mean": {"callable": mean, "effect": "location"},
    }


def simulate_test_rates(
    *,
    n_days: int = 299,
    n_sim: int = N_SIMULATIONS,
    rho: float = 0.73,
    sigma: float = 1.0,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = ALPHA,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_SIMULATION_BOOTSTRAP,
    hac_lag: int = HAC_LAG_DAILY,
    apply_effect: bool = False,
) -> Dict[str, Dict[str, float]]:
    """
    Mô phỏng tỷ lệ bác bỏ dưới H₀ (``apply_effect=False``) và dưới H₁ có hiệu ứng
    (``apply_effect=True``) cho từng phép kiểm, trên chuỗi AR(1) có cùng mức tự
    tương quan như dữ liệu thật.

    Đây là **bằng chứng kiểm soát sai lầm loại I**: nếu một phép kiểm dùng p-value
    của SciPy (giả định độc lập) thì tỷ lệ bác bỏ dưới H₀ phải bằng α; mọi
    chênh lệch là do giả định độc lập sai.
    """
    procedures = _simulation_procedures(
        block_length=block_length, n_bootstrap=n_bootstrap, seed=seed, hac_lag=hac_lag
    )
    results: Dict[str, Dict[str, float]] = {}
    positions = np.arange(n_days)
    season_group = (positions * 4) // n_days
    weekend_mask = (positions % 7) >= 5

    for name, spec in procedures.items():
        callable_ = spec["callable"]
        effect_type = spec["effect"]
        rejects = {"p_independence": 0, "p_dependence_aware": 0, "p_supporting": 0}
        valid = 0
        for sim in range(n_sim):
            base = ar1_series(n_days, rho, sigma=sigma, seed=seed * 1_000_003 + sim)
            if apply_effect and effect_type == "seasonal":
                data = base + np.where(season_group == 0, 1.0, 0.0)
            elif apply_effect and effect_type == "weekly":
                data = base + np.where(weekend_mask, 1.0, 0.0)
            elif apply_effect and effect_type == "location":
                data = base + 1.0
            else:
                data = base
            outcome = callable_(data)
            values = {
                key: float(outcome[key])
                for key in ("p_independence", "p_dependence_aware", "p_supporting")
            }
            if not all(np.isfinite(v) for v in values.values()):
                continue
            valid += 1
            for key, value in values.items():
                rejects[key] += int(value < alpha)
        results[name] = {
            "n_sim": int(valid),
            "size_independence": float(rejects["p_independence"] / valid) if valid else float("nan"),
            "size_dependence_aware": float(rejects["p_dependence_aware"] / valid) if valid else float("nan"),
            "size_supporting": float(rejects["p_supporting"] / valid) if valid else float("nan"),
            "alpha": float(alpha),
            "rho": float(rho),
            "n_days": int(n_days),
            "n_bootstrap": int(n_bootstrap),
            "block_length": int(block_length),
            "hac_lag": int(hac_lag),
            "effect": effect_type,
        }
    return results


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
    test["p_value_independence"] = float(test["p_value"])
    # Biến thể có xét phụ thuộc: các chênh lệch tuần cũng tự tương quan
    # (những tuần liền nhau cùng đổi chiều), nên Wilcoxon giả định độc lập vẫn
    # lạc quan → dùng HAC/Newey–West trên chính chuỗi chênh lệch tuần.
    if diffs.size >= 8:
        hac_test = hac_signed_rank_test(diffs, mu=0.0, lag=4)
        test["p_value"] = float(hac_test["p_value"])
        test["statistic_name"] = "t (signed-rank, HAC)"
        test["statistic"] = float(hac_test["statistic"])
    test["df"] = int(diffs.size - 1)
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
    phụ thuộc vào giả định độc lập của từng ngày hay không. p-value cũng được
    dựng lại dưới H₀ bằng null block bootstrap (block 4 tuần).
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
    result["p_value_independence"] = float(result["p_value"])

    order = [season for season in SEASON_DISPLAY_ORDER if season in groups]
    weekly_sorted = weekly.sort_values("week_index")
    season_of_week = weekly_sorted["season"].to_numpy()
    masks = [np.asarray(season_of_week == season, dtype=bool) for season in order]
    null_boot = block_bootstrap_null_test(
        weekly_sorted[value_col].to_numpy(dtype=float),
        statistic=lambda matrix: kruskal_statistic_rows(matrix, masks),
        observed_statistic=float(result["statistic"]),
        alternative="greater",
        block_length=4,
        n_bootstrap=N_NULL_BOOTSTRAP,
        seed=BOOTSTRAP_SEED,
        null_construction=(
            "Chuỗi trung bình tuần, resample theo block 4 tuần; nhãn mùa giữ theo "
            "vị trí tuần."
        ),
        statistic_name="H",
    )
    result["p_value"] = float(null_boot["p_value"])
    result["null_bootstrap"] = null_boot
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


def _posthoc_pairs(
    panel: pd.DataFrame,
    groups: Mapping[str, np.ndarray],
    *,
    block_length: int = BLOCK_LENGTH_DAYS,
    n_bootstrap: int = N_NULL_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
) -> Dict[str, Any]:
    """
    Sáu cặp mùa bằng Mann-Whitney — family hậu định riêng, nhãn *exploratory*.

    p-value của mỗi cặp cũng được dựng lại **dưới H₀ có xét phụ thuộc**: null
    bootstrap trên **toàn bộ** chuỗi ngày (H₀ của phép kiểm hậu định là "các
    mùa không khác nhau"), với nhãn của **hai mùa được so sánh** giữ theo vị
    trí lịch. Hạng được tính **trong tập A ∪ B** để thống kê U của bản sao null
    và bản sao quan sát cùng thang đo.
    """
    names = [s for s in SEASON_DISPLAY_ORDER if s in groups]
    values = panel["pm25_mean"].to_numpy(dtype=float)
    seasons = panel["season"].to_numpy()
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
            result["p_value_independence"] = float(result["p_value"])

            mask_a_full = np.asarray(seasons == a, dtype=bool)
            mask_b_full = np.asarray(seasons == b, dtype=bool)
            selected = mask_a_full | mask_b_full
            mask_a = mask_a_full[selected]
            null_boot = block_bootstrap_null_test(
                values,
                statistic=lambda matrix, sel=selected, ma=mask_a: mannwhitney_statistic_rows(
                    matrix[:, sel], ma
                ),
                observed_statistic=float(result["statistic"]),
                alternative="two-sided",
                block_length=block_length,
                n_bootstrap=n_bootstrap,
                seed=seed,
                null_construction=(
                    "Chuỗi gộp toàn bộ ngày, resample theo block tròn; nhãn của hai "
                    "mùa so sánh giữ theo vị trí lịch."
                ),
                statistic_name="U",
            )
            result["p_value"] = float(null_boot["p_value"])
            result["null_bootstrap"] = null_boot
            pairs.append(result)

    adjusted = holm_adjust([p["p_value"] for p in pairs])
    adjusted_reference = holm_adjust([p["p_value_independence"] for p in pairs])
    for pair, p_holm, p_holm_ref in zip(pairs, adjusted, adjusted_reference):
        pair["p_holm"] = float(p_holm)
        pair["p_holm_independence"] = float(p_holm_ref)
        pair["reject_holm"] = bool(p_holm < ALPHA)
    return {
        "pairs": pairs,
        "n_pairs": len(pairs),
        "family": "posthoc_seasonal_pairs",
        "note": (
            "Family riêng, nhãn exploratory; p-value đã hiệu chỉnh phụ thuộc thời "
            "gian, cột p tham chiếu là phép kiểm giả định độc lập."
        ),
    }


def run_inference(
    df: Optional[pd.DataFrame] = None,
    *,
    data_path: Optional[Path] = None,
    min_valid_hours: int = MIN_VALID_HOURS_PER_DAY,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = BOOTSTRAP_SEED,
    include_simulation: bool = True,
    n_simulations: int = N_SIMULATIONS,
) -> Dict[str, Any]:
    """
    Chạy toàn bộ suy luận của Issue #11 và trả về một payload duy nhất.

    `df=None` thì đọc `data/processed/air_pollution_final.parquet`. Truyền `df`
    để test chạy trên dữ liệu tổng hợp mà không cần `data/`.

    `include_simulation=False` bỏ qua mô phỏng kiểm soát sai lầm loại I (dùng
    cho test nhanh); payload khi đó không có khối `simulation`.
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

    # --- Bốn kiểm định xác nhận — CÓ xét phụ thuộc thời gian -----------------
    season_groups = _season_groups(panel)
    if len(season_groups) < 2:
        raise ValueError("Cần ≥ 2 mùa có dữ liệu để so sánh.")
    season_test = _season_effect_test(panel, seed=seed)
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

    weekday_test = _weekday_effect_test(panel, seed=seed)
    weekday_values = panel.loc[panel["is_weekend"] == 0, "pm25_mean"].to_numpy(dtype=float)
    weekend_values = panel.loc[panel["is_weekend"] == 1, "pm25_mean"].to_numpy(dtype=float)
    weekday_test["ci"] = bootstrap_difference_ci(
        weekday_values,
        weekend_values,
        statistic="median",
        n_bootstrap=n_bootstrap,
        seed=seed,
    )
    weekday_power = minimum_detectable_difference(weekday_values, weekend_values)

    qcvn_24h_test = _location_effect_test(
        panel,
        mu=QCVN_2023_PM25_24H_LIMIT,
        kind="median",
        label="Trung bình 24h vs 50 µg/m³",
        seed=seed,
    )
    qcvn_24h_test["ci_bootstrap"] = bootstrap_ci(
        values, statistic="median", n_bootstrap=n_bootstrap, seed=seed
    )
    deviations_24h = values - QCVN_2023_PM25_24H_LIMIT
    qcvn_24h_test["w_plus"] = float(
        stats.rankdata(np.abs(deviations_24h))[deviations_24h > 0].sum()
    )
    qcvn_24h_test["w_minus"] = float(
        stats.rankdata(np.abs(deviations_24h))[deviations_24h < 0].sum()
    )

    annual_test = _location_effect_test(
        panel,
        mu=QCVN_2023_PM25_ANNUAL_LIMIT,
        kind="mean",
        label="Trung bình giai đoạn vs 25 µg/m³",
        seed=seed,
    )
    annual_test["ci_bootstrap"] = bootstrap_ci(
        values, statistic="mean", n_bootstrap=n_bootstrap, seed=seed
    )
    t_crit = float(stats.t.ppf(0.975, values.size - 1))
    se_naive = float(values.std(ddof=1) / np.sqrt(values.size))
    annual_test["ci_t"] = {
        "ci_low": float(annual_test["mean"] - t_crit * se_naive),
        "ci_high": float(annual_test["mean"] + t_crit * se_naive),
    }

    # --- Family xác nhận + Holm --------------------------------------------
    # Family **giữ nguyên 4 kiểm định như đã chốt trước khi xem dữ liệu**. Việc
    # một kiểm định bị hạ xuống "thăm dò" KHÔNG làm thay đổi family (thay đổi
    # family sau khi xem kết quả là p-hacking).
    confirmatory = [
        ("season_effect", "Mùa (4 nhóm, có xét phụ thuộc thời gian)", season_test),
        ("weekday_effect", "Ngày làm việc vs cuối tuần (có xét phụ thuộc thời gian)", weekday_test),
        ("qcvn_24h", "Trung bình 24h vs 50 µg/m³ (có xét phụ thuộc thời gian)", qcvn_24h_test),
        ("qcvn_annual", "Trung bình giai đoạn vs 25 µg/m³ (có xét phụ thuộc thời gian)", annual_test),
    ]
    adjusted = holm_adjust([test["p_value"] for _, _, test in confirmatory])
    adjusted_reference = holm_adjust(
        [test["p_value_independence"] for _, _, test in confirmatory]
    )
    holm_table = []
    for (key, label, test), p_holm, p_holm_ref in zip(confirmatory, adjusted, adjusted_reference):
        test["p_holm"] = float(p_holm)
        test["p_holm_independence"] = float(p_holm_ref)
        test["reject_holm"] = bool(p_holm < ALPHA)
        test["reject_raw"] = bool(test["p_value"] < ALPHA)
        holm_table.append(
            {
                "key": key,
                "label": label,
                "p_raw": float(test["p_value"]),
                "p_holm": float(p_holm),
                "p_raw_independence": float(test["p_value_independence"]),
                "p_holm_independence": float(p_holm_ref),
                "reject_raw": bool(test["p_value"] < ALPHA),
                "reject_holm": bool(p_holm < ALPHA),
                "reject_holm_independence": bool(p_holm_ref < ALPHA),
                "statistic_name": test["statistic_name"],
                "statistic": test["statistic"],
                "effect_size_name": test["effect_size_name"],
                "effect_size": test["effect_size"],
                "status": test["status"],
                "status_reason": test["status_reason"],
                "method": test["method"]["primary"],
            }
        )

    posthoc = _posthoc_pairs(panel, season_groups, seed=seed)
    sensitivity = {
        "paired_weeks": paired_weekly_differences(panel),
        "season_weekly": season_weekly_sensitivity(panel),
        "power_mde": weekday_power,
    }
    generalization = season_generalization_diagnostics(panel)
    context = qcvn_context(hourly, panel)

    simulation: Dict[str, Any] = {}
    if include_simulation:
        rho = float(dependence["daily_effective_n"]["rho_lag1"])
        simulation = {
            "size": simulate_test_rates(
                n_days=int(values.size),
                n_sim=n_simulations,
                rho=rho,
                seed=seed,
                apply_effect=False,
            ),
            "power": simulate_test_rates(
                n_days=int(values.size),
                n_sim=n_simulations,
                rho=rho,
                seed=seed,
                apply_effect=True,
            ),
            "rho_used": rho,
            "n_sim": int(n_simulations),
            "n_days": int(values.size),
            "note": (
                "Chuỗi AR(1) với ρ bằng ACF bậc 1 quan sát; hiệu ứng H₁: +1 đơn vị "
                "lên nhóm mùa đầu / ngày cuối tuần / toàn bộ chuỗi (tương ứng từng "
                "phép kiểm)."
            ),
        }

    return {
        "meta": {
            "issue": "#11",
            "alpha": ALPHA,
            "confidence_level": CONFIDENCE_LEVEL,
            "n_bootstrap": n_bootstrap,
            "n_null_bootstrap": N_NULL_BOOTSTRAP,
            "bootstrap_seed": seed,
            "block_length_days": BLOCK_LENGTH_DAYS,
            "hac_lag_days": HAC_LAG_DAILY,
            "min_valid_hours_per_day": min_valid_hours,
            "split_point_note": (
                "Không dùng Train/Test: các phép kiểm không fit mô hình. Điểm cắt "
                "2026-01-15 của Issue #7 giữ nguyên cho Issue #12–#13."
            ),
            "dependence_note": (
                "p-value xác nhận được dựng lại dưới H₀ có xét tự tương quan "
                "(review 5586524840 của PR #43): null block bootstrap cho các kiểm "
                "định theo nhóm, HAC/Newey–West cho các kiểm định vị trí."
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
            "season_effect": season_test,
            "weekday_effect": weekday_test,
            "qcvn_24h": qcvn_24h_test,
            "qcvn_annual": annual_test,
        },
        "holm_confirmatory": holm_table,
        "posthoc_season": posthoc,
        "sensitivity": sensitivity,
        "generalization": generalization,
        "simulation": simulation,
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


def _status_label(status: str) -> str:
    """Nhãn hiển thị cho trạng thái kết luận của một kiểm định."""
    return {
        "confirmatory": "XÁC NHẬN",
        "exploratory": "THĂM DÒ (EXPLORATORY)",
        "not_confirmable": "KHÔNG XÁC NHẬN ĐƯỢC",
    }.get(status, status)


def _sensitivity_rows(test: Mapping[str, Any], key: str, unit: str) -> str:
    """Bảng độ nhạy theo tham số phụ thuộc (độ dài block hoặc lag HAC)."""
    entries = test.get("sensitivity", {}).get(key, {})
    rows = []
    for name in sorted(entries, key=lambda value: int(value)):
        entry = entries[name]
        rows.append(
            f"| {unit} = {name} | {_p(entry['p_value'])} | "
            f"{'bác bỏ H₀' if entry['p_value'] < ALPHA else 'không bác bỏ H₀'} |"
        )
    return "\n".join(rows)


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
    season = tests["season_effect"]
    weekday = tests["weekday_effect"]
    q24 = tests["qcvn_24h"]
    annual = tests["qcvn_annual"]
    posthoc = results["posthoc_season"]
    sensitivity = results["sensitivity"]
    paired = sensitivity["paired_weeks"]
    weekly_season = sensitivity["season_weekly"]["weekly_kruskal"]
    mde = sensitivity["power_mde"]
    generalization = results["generalization"]
    simulation = results.get("simulation", {})
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
        f"{format_number_vi(row['effect_size'], 3)} | {_status_label(row['status'])} |"
        for row in results["holm_confirmatory"]
    )
    reference_rows = "\n".join(
        f"| {row['label']} | {_p(row['p_raw_independence'])} | {_p(row['p_holm_independence'])} | "
        f"{'bác bỏ H₀' if row['reject_holm_independence'] else 'không bác bỏ H₀'} |"
        for row in results["holm_confirmatory"]
    )
    posthoc_rows = "\n".join(
        f"| {pair['pair']} | {format_number_vi(pair['median_a'], 2)} | "
        f"{format_number_vi(pair['median_b'], 2)} | "
        f"{format_number_vi(pair['statistic'], 0)} | {_p(pair['p_value'])} | "
        f"{_p(pair['p_holm'])} | {_p(pair['p_value_independence'])} | "
        f"{format_number_vi(pair['effect_size'], 3)} | {_ci_text(pair['ci'])} |"
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
    weekday_ci = weekday["ci"]
    ci_includes_zero = bool(
        weekday_ci is not None and weekday_ci["ci_low"] <= 0.0 <= weekday_ci["ci_high"]
    )
    n_reject = sum(1 for row in results["holm_confirmatory"] if row["reject_holm"])
    n_reject_reference = sum(
        1 for row in results["holm_confirmatory"] if row["reject_holm_independence"]
    )
    n_exploratory = sum(
        1 for row in results["holm_confirmatory"] if row["status"] == "exploratory"
    )

    lines = [
        "# Kết quả Suy luận Thống kê — Issue #11 (W9)",
        "",
        "> **Tệp này được sinh tự động** bởi `src/inference.py::render_inference_report()`",
        "> từ `notebooks/05_statistical_inference.ipynb`. Không sửa tay: mọi con số",
        "> dưới đây lấy trực tiếp từ `run_inference()` trên dataset đã đóng băng.",
        "",
        "> **Phiên bản 2 — sửa theo review `5586524840` của PR #43.** Toàn bộ p-value",
        "> xác nhận được **dựng lại dưới H₀ có xét tới tự tương quan thời gian**;",
        "> p-value cũ (giả định quan sát độc lập) được giữ lại **để đối chiếu**, và",
        "> kết luận đã thay đổi — xem mục 8.",
        "",
        "| Trường | Giá trị |",
        "|---|---|",
        f"| Issue | {meta['issue']} |",
        f"| Mức ý nghĩa α (chốt trước khi xem dữ liệu) | {format_number_vi(meta['alpha'], 2)} |",
        f"| CI bootstrap | {format_int_vi(meta['n_bootstrap'])} lặp · block {meta['block_length_days']} ngày · seed {meta['bootstrap_seed']} · CI percentile {int(meta['confidence_level'] * 100)}% |",
        f"| Null bootstrap (p-value) | {format_int_vi(meta['n_null_bootstrap'])} lặp · block {meta['block_length_days']} ngày · seed {meta['bootstrap_seed']} |",
        f"| HAC (Newey–West) | lag {meta['hac_lag_days']} ngày |",
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
        "## 3. Tự tương quan, cỡ mẫu hiệu dụng — giả định nào bị vi phạm",
        "",
        f"- ACF chuỗi **giờ**: {acf_hourly}.",
        f"- ACF chuỗi **ngày**: {acf_daily}.",
        f"- AR(1) của chuỗi ngày: ρ = {format_number_vi(eff['rho_lag1'], 4)} → "
        f"n_eff ≈ **{format_number_vi(eff['n_effective'], 1)}** so với n = {format_int_vi(eff['n'])} "
        f"(hệ số lạm phát ×{format_number_vi(eff['inflation_factor'], 2)}).",
        "",
        "**Hệ quả — và cách xử lý sau review.** Mann-Whitney, Kruskal-Wallis, Wilcoxon và t-test "
        "đều giả định quan sát **độc lập**. Ở mức ngày, giả định đó **không** được bảo đảm "
        f"(ρ = {format_number_vi(eff['rho_lag1'], 2)}), nên p-value của chúng là **lạc quan**. "
        "Ở phiên bản trước, biện pháp duy nhất là block bootstrap cho **khoảng tin cậy** — "
        "**không** sửa p-value. Đó là thiếu sót mà review `5586524840` chỉ ra. "
        "Phiên bản này sửa đúng chỗ đó:",
        "",
        "1. Hạ đơn vị phân tích từ **giờ** xuống **ngày** (vẫn giữ).",
        "2. **Dựng lại phân phối null dưới H₀** cho từng kiểm định (mục 4) — đây mới là "
        "phần sửa p-value.",
        f"3. Mọi CI dùng **circular moving block bootstrap**, block {meta['block_length_days']} ngày "
        f"({format_int_vi(meta['n_bootstrap'])} lặp, seed {meta['bootstrap_seed']}).",
        "4. Kiểm soát sai lầm loại I bằng **mô phỏng dưới H₀** (mục 9).",
        "5. Mọi kết luận đọc kèm **effect size + CI**, không đọc p đơn độc.",
        "",
        "---",
        "",
        "## 4. Khung phương pháp: dựng phân phối null dưới H₀ có xét phụ thuộc thời gian",
        "",
        "Bốn kiểm định xác nhận dùng **bốn cách dựng null khác nhau**, mỗi cách được chọn vì "
        "hợp với cấu trúc dữ liệu và với H₀ của chính kiểm định đó:",
        "",
        "| Kiểm định | H₀ | Cách dựng phân phối null | Tham số phụ thuộc | Giả định chính |",
        "|---|---|---|---|---|",
        f"| Mùa | 4 mùa cùng phân phối (quá trình ổn định) | Null **circular moving block bootstrap** trên chuỗi **gộp**; nhãn mùa **giữ theo vị trí lịch**, KHÔNG hoán đổi nhãn | block {meta['block_length_days']} ngày | Chuỗi gộp ổn định; block bao trọn phụ thuộc còn lại |",
        f"| Weekday vs cuối tuần | Hai nhóm cùng phân phối | Null **circular moving block bootstrap** trên chuỗi **gộp**; nhãn nhóm giữ theo vị trí lịch | block {meta['block_length_days']} ngày | Như trên; xen kẽ tuần được giữ nguyên |",
        f"| QCVN 24h (trung vị = 50) | P(trung bình ngày > 50) = 0,5 | **HAC/Newey–West** cho tỷ lệ vượt ngưỡng (tương đương trung vị = 50 với phân phối liên tục) | lag {meta['hac_lag_days']} ngày | Sai số tự tương quan tới bậc L; phân phối liên tục |",
        f"| QCVN năm (trung bình = 25) | E(trung bình ngày) = 25 | **HAC/Newey–West** (mô hình chỉ có hệ số chặn) | lag {meta['hac_lag_days']} ngày | Như trên |",
        "",
        "**Ba điều kiện mà phương pháp này tuân thủ (và phương pháp cũ không tuân thủ).**",
        "",
        "1. **Null được dựng dưới H₀.** Với kiểm định theo nhóm, null là chuỗi **gộp** (H₀: các "
        "nhóm cùng phân phối). Với kiểm định vị trí, H₀ được **áp đặt** bằng cách dựng bản sao "
        "`x* = μ + resample(x − θ̂)` — tức mốc của H₀ nằm trong bản sao, không phải trong dữ liệu gốc.",
        "2. **Nhãn nhóm đi theo vị trí lịch, không bị hoán đổi ngẫu nhiên.** Hoán đổi nhãn mùa sẽ "
        "phá vỡ cấu trúc mùa vụ (mùa là các đoạn thời gian liên tiếp, không phải nhãn rời rạc).",
        "3. **CI ≠ p-value.** CI là khoảng tin cậy của ước lượng; p-value là xác suất của dữ liệu "
        "**có điều kiện H₀ đúng**. Báo cáo luôn in cả hai và không dùng CI để suy ra p (hay ngược lại).",
        "",
        "### 4.1. Quy tắc hạ mức kết luận — chốt trước khi xem kết quả",
        "",
        "Mỗi kiểm định mang một **trạng thái** được máy tính theo ba quy tắc cố định:",
        "",
        "| Quy tắc | Điều kiện | Hệ quả |",
        "|---|---|---|",
        "| R1 — Ổn định | Kết luận (bác bỏ / không bác bỏ) **đổi chiều** khi đổi độ dài block hoặc lag HAC trong lưới độ nhạy | Hạ xuống **THĂM DÒ** |",
        "| R2 — Đồng thuận | Phương pháp đối chứng cho kết luận **khác chiều** phương pháp chính tại tham số đã chốt | Hạ xuống **THĂM DÒ** |",
        "| R3 — Tính được | Không dựng được p hợp lệ | **KHÔNG XÁC NHẬN ĐƯỢC** |",
        "",
        "> **Family hiệu chỉnh Holm vẫn gồm đúng 4 kiểm định** như đã chốt trước khi xem dữ liệu.\n"
        "> Việc một kiểm định bị hạ xuống *thăm dò* **không** làm thay đổi family — thay đổi family\n"
        "> sau khi nhìn kết quả là p-hacking.",
        "",
        "---",
        "",
        "## 5. Kiểm định 1 — Khác biệt giữa bốn mùa",
        "",
        f"**H₀:** {season['h0']}",
        f"**H₁:** {season['h1']}",
        f"**α = {format_number_vi(ALPHA, 2)}, omnibus (đuôi trên của H).**",
        "",
        f"**Phương pháp chính:** {season['method']['primary']} "
        f"(block {season['method']['primary_block_length']} ngày, "
        f"{format_int_vi(meta['n_null_bootstrap'])} lặp, seed {meta['bootstrap_seed']}).",
        f"**Phương pháp đối chứng:** {season['method']['supporting']} "
        f"(lag {season['method']['supporting_lag']} ngày) — dùng để **tách mùa khỏi xu hướng**.",
        "",
        "| Mùa | n (ngày) | Trung vị (µg/m³) |",
        "|---|---|---|",
        season_rows,
        "",
        f"- **H = {format_number_vi(season['statistic'], 4)}**, df = {season['df']}, "
        f"n = {format_int_vi(season['n'])}.",
        f"- **p (hiệu chỉnh phụ thuộc thời gian) = {_p(season['p_value'])}** → "
        f"{_decision(season['p_value'])}; **p Holm = {_p(season['p_holm'])}** → "
        f"{_decision(season['p_holm'])}.",
        f"- p tham chiếu (giả định độc lập) = {_p(season['p_value_independence'])}.",
        f"- Effect size **ε² = {format_number_vi(season['effect_size'], 4)}** "
        "(tỷ lệ phương sai hạng giải thích bởi mùa).",
        f"- Đối chứng (HAC, có xu hướng): F = {format_number_vi(season['supporting_result']['statistic'], 3)} "
        f"({season['supporting_result']['df1']}, {season['supporting_result']['df2']}), "
        f"p = {_p(season['supporting_result']['p_value'])}; với xu hướng bậc hai: "
        f"p = {_p(season['supporting_result']['quadratic_trend_p'])}; xu hướng tuyến tính ước lượng "
        f"{format_number_vi(season['supporting_result']['trend_per_month'], 2)} µg/m³ mỗi tháng.",
    ]
    if season.get("ci_dong_vs_he"):
        ci = season["ci_dong_vs_he"]
        lines.append(
            f"- CI 95% block bootstrap cho chênh lệch trung vị **Đông − Hè**: "
            f"{format_number_vi(ci['point'], 2)} µg/m³, {_ci_text(ci)}."
        )
    lines += [
        "",
        "**Độ nhạy theo độ dài block (phương pháp chính).**",
        "",
        "| Block (ngày) | p | Kết luận |",
        "|---|---|---|",
        _sensitivity_rows(season, "block_length", "block"),
        "",
        "**Độ nhạy theo lag HAC (phương pháp đối chứng).**",
        "",
        "| Lag (ngày) | p | Kết luận |",
        "|---|---|---|",
        _sensitivity_rows(season, "hac_lag", "lag"),
        "",
        f"> **Trạng thái kết luận: {_status_label(season['status'])}.** {season['status_reason']} "
        "p-value của kiểm định mùa nhạy với lựa chọn cách hiệu chỉnh phụ thuộc (từ "
        f"{_p(season['sensitivity']['block_length']['7']['p_value'])} ở block 7 ngày tới "
        f"{_p(season['sensitivity']['block_length']['42']['p_value'])} ở block 42 ngày) — "
        "nghĩa là bằng chứng thống kê cho H₀ 'các mùa bằng nhau' **không vững**; khác biệt mùa "
        "vẫn được báo cáo như **mô tả** của giai đoạn 07/2025–07/2026 (mục 10), không phải quy luật "
        "nhiều năm.",
        "",
        "### 5.1. Hậu định sáu cặp mùa (exploratory — family Holm riêng)",
        "",
        "Sáu cặp này **không** thuộc family xác nhận: chúng được khảo sát sau khi kiểm định omnibus "
        "bác bỏ H₀, nên mang nhãn *exploratory* và được hiệu chỉnh Holm trong family riêng. "
        "p-value của mỗi cặp cũng được dựng lại dưới H₀ có xét phụ thuộc (null block bootstrap trên "
        "chuỗi gộp, nhãn của hai mùa so sánh giữ theo vị trí lịch).",
        "",
        "| Cặp | Trung vị A | Trung vị B | U | p (hiệu chỉnh) | p Holm | p tham chiếu | r_rb | CI 95% (A−B) |",
        "|---|---|---|---|---|---|---|---|---|",
        posthoc_rows,
        "",
        "---",
        "",
        "## 6. Kiểm định 2 — Ngày làm việc vs ngày cuối tuần",
        "",
        f"**H₀:** {weekday['h0']}",
        f"**H₁:** {weekday['h1']}",
        f"**α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        f"**Phương pháp chính:** {weekday['method']['primary']} "
        f"(block {weekday['method']['primary_block_length']} ngày).",
        f"**Phương pháp đối chứng:** {weekday['method']['supporting']} "
        f"(lag {weekday['method']['supporting_lag']} ngày).",
        "",
        f"- Ngày làm việc: n = {format_int_vi(weekday['n_a'])}, "
        f"trung vị {format_number_vi(weekday['median_a'], 2)} µg/m³.",
        f"- Ngày cuối tuần: n = {format_int_vi(weekday['n_b'])}, "
        f"trung vị {format_number_vi(weekday['median_b'], 2)} µg/m³.",
        f"- **U = {format_number_vi(weekday['statistic'], 1)}**, "
        f"**p (hiệu chỉnh phụ thuộc) = {_p(weekday['p_value'])}** → "
        f"{_decision(weekday['p_value'])}; **p Holm = {_p(weekday['p_holm'])}** → "
        f"{_decision(weekday['p_holm'])}.",
        f"- p tham chiếu (giả định độc lập) = {_p(weekday['p_value_independence'])}.",
        f"- Chênh lệch trung vị: **{format_number_vi(weekday['median_difference'], 2)} µg/m³**, "
        f"CI 95% block bootstrap {_ci_text(weekday['ci'])}.",
        f"- Effect size **r_rb = {format_number_vi(weekday['effect_size'], 4)}** "
        "(dương = ngày làm việc cao hơn).",
        f"- Đối chứng (HAC): t = {format_number_vi(weekday['supporting_result']['statistic'], 3)}, "
        f"p = {_p(weekday['supporting_result']['p_value'])}.",
        "",
        "**Độ nhạy theo độ dài block.**",
        "",
        "| Block (ngày) | p | Kết luận |",
        "|---|---|---|",
        _sensitivity_rows(weekday, "block_length", "block"),
        "",
        f"> **Trạng thái kết luận: {_status_label(weekday['status'])}.** {weekday['status_reason']}",
        "",
        "**Ý nghĩa thống kê ≠ ý nghĩa thực tiễn — và power có giới hạn.** Với SD gộp "
        f"{format_number_vi(mde['pooled_sd'], 2)} µg/m³, n₁ = {format_int_vi(mde['n_a'])}, "
        f"n₂ = {format_int_vi(mde['n_b'])}, chênh lệch nhỏ nhất phát hiện được ở power "
        f"{format_number_vi(mde['power'] * 100, 0)}%, α = 0,05 là **MDE ≈ "
        f"{format_number_vi(mde['mde'], 2)} µg/m³** (xấp xỉ chuẩn, tính hậu nghiệm từ SD quan sát "
        "— lưu ý: công thức này **giả định độc lập**, nên với chuỗi tự tương quan nó **đánh giá "
        "thấp** ngưỡng phân giải thực tế).",
        "",
        f"- Chênh lệch quan sát được là {format_number_vi(weekday['median_difference'], 2)} µg/m³, "
        f"nhỏ hơn MDE, và CI 95% block bootstrap {_ci_text(weekday['ci'])} "
        f"{'chứa 0' if ci_includes_zero else 'không chứa 0'}; |r_rb| = "
        f"{format_number_vi(abs(weekday['effect_size']), 3)}. "
        "Vì vậy dữ liệu **không đủ độ phân giải** để phân biệt 'không có khác biệt' với "
        "'khác biệt nhỏ hơn MDE' — đây không phải bằng chứng khẳng định hai nhóm bằng nhau.",
        "- Ước lượng điểm nằm trong khoảng sai số thực hành của một trạm đo, nên không được "
        "dùng để quy kết nguồn phát thải hay hành vi giao thông.",
        "",
        "---",
        "",
        "## 7. Kiểm định 3 — Đối chiếu QCVN 05:2023/BTNMT (đúng chu kỳ lấy mẫu)",
        "",
        "Hai ngưỡng được kiểm định **tách biệt**, mỗi ngưỡng đi với đúng chu kỳ trung bình của nó. "
        "Không có phép so sánh nào giữa một giờ đơn lẻ với ngưỡng ngày hoặc ngưỡng năm.",
        "",
        "### 7.1. Ngưỡng trung bình 24 giờ — 50 µg/m³",
        "",
        f"**H₀:** {q24['h0']}",
        f"**H₁:** {q24['h1']}",
        f"**α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        f"**Phương pháp chính:** {q24['method']['primary']}",
        f"**Phương pháp đối chứng:** {q24['method']['supporting']}.",
        "",
        f"- n = {format_int_vi(q24['n'])} ngày; trung vị {format_number_vi(q24['median'], 2)} µg/m³; "
        f"trung bình {format_number_vi(q24['mean'], 2)} ± {format_number_vi(q24['sd'], 2)} µg/m³.",
        f"- **t = {format_number_vi(q24['statistic'], 4)}** (tỷ lệ ngày vượt ngưỡng, SE HAC), "
        f"**p (hiệu chỉnh phụ thuộc) = {_p(q24['p_value'])}** → {_decision(q24['p_value'])}; "
        f"**p Holm = {_p(q24['p_holm'])}** → {_decision(q24['p_holm'])}.",
        f"- p tham chiếu (Wilcoxon giả định độc lập) = {_p(q24['p_value_independence'])}.",
        f"- Đối chứng: bootstrap áp đặt H₀ p = {_p(q24['supporting_result']['null_imposed_p'])}; "
        f"p suy ra từ phân phối bootstrap của ước lượng (đảo CI) = "
        f"{_p(q24['supporting_result']['percentile_p'])}; Wilcoxon có HAC "
        f"p = {_p(q24['supporting_result']['signed_rank_hac_p'])}.",
        f"- Effect size **r = {format_number_vi(q24['effect_size'], 4)}** "
        "(âm = trung vị nằm dưới ngưỡng).",
        f"- CI 95% block bootstrap cho trung vị: {_ci_text(q24['ci_bootstrap'])}.",
        f"- Số ngày có trung bình ≥ 50 µg/m³: **{format_int_vi(ctx['panel_days_over'])}/"
        f"{format_int_vi(ctx['panel_days'])} = {format_number_vi(ctx['panel_share'] * 100, 2)}%** "
        f"(CI 95% Wilson: {format_number_vi(ctx_ci[0] * 100, 2)}% – "
        f"{format_number_vi(ctx_ci[1] * 100, 2)}%).",
        "",
        "**Độ nhạy theo lag HAC.**",
        "",
        "| Lag (ngày) | p | Kết luận |",
        "|---|---|---|",
        _sensitivity_rows(q24, "hac_lag", "lag"),
        "",
        f"> **Trạng thái kết luận: {_status_label(q24['status'])}.** {q24['status_reason']} "
        "Lưu ý: bản **signed-rank** có HAC cho p lớn hơn bản tỷ lệ vượt ngưỡng, vì dãy chênh lệch "
        "lớn (ngày rất vượt ngưỡng) rất bền nên SE HAC của nó bị thổi phồng — đây là hạn chế **sức "
        "mạnh** của phép kiểm, không phải lỗi hiệu chỉnh.",
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
        "> **Không kết luận 'đạt/không đạt QCVN'.** Quy chuẩn quy định cách đánh giá tuân thủ "
        "(số ngày vượt được phép trong một năm) mà dự án **không** mã hoá và không có văn bản gốc "
        "đối chiếu. Kết quả trên chỉ nói: vị trí trung tâm của phân phối trung bình ngày nằm "
        "dưới 50 µg/m³, nhưng gần ba phần mười số ngày vượt ngưỡng — hai sự thật không mâu thuẫn.",
        "",
        "### 7.2. Ngưỡng trung bình năm — 25 µg/m³",
        "",
        f"**H₀:** {annual['h0']}",
        f"**H₁:** {annual['h1']}",
        f"**α = {format_number_vi(ALPHA, 2)}, hai phía.**",
        "",
        f"**Phương pháp chính:** {annual['method']['primary']}",
        f"**Phương pháp đối chứng:** {annual['method']['supporting']}.",
        "",
        f"- n = {format_int_vi(annual['n'])} ngày; trung bình {format_number_vi(annual['mean'], 2)} "
        f"± {format_number_vi(annual['sd'], 2)} µg/m³.",
        f"- **t = {format_number_vi(annual['statistic'], 4)}** (HAC), "
        f"**p (hiệu chỉnh phụ thuộc) = {_p(annual['p_value'])}** → "
        f"{_decision(annual['p_value'])}; **p Holm = {_p(annual['p_holm'])}** → "
        f"{_decision(annual['p_holm'])}.",
        f"- p tham chiếu (t-test giả định độc lập) = {_p(annual['p_value_independence'])}.",
        f"- Đối chứng: bootstrap áp đặt H₀ p = "
        f"{_p(annual['supporting_result']['null_imposed_p'])}; p suy ra từ phân phối bootstrap "
        f"của ước lượng = {_p(annual['supporting_result']['percentile_p'])}.",
        f"- Cohen's d = **{format_number_vi(annual['effect_size'], 4)}** (đơn vị: độ lệch chuẩn của "
        "trung bình ngày, không phải của một quan sát năm).",
        f"- CI 95% theo HAC (tôn trọng tự tương quan): {_ci_text(annual['hac_detail']['ci'])}; "
        f"CI 95% block bootstrap: {_ci_text(annual['ci_bootstrap'])}; "
        f"CI 95% theo t (giả định độc lập — tham chiếu): {_ci_text(annual['ci_t'])}.",
        "",
        "**Độ nhạy theo lag HAC.**",
        "",
        "| Lag (ngày) | p | Kết luận |",
        "|---|---|---|",
        _sensitivity_rows(annual, "hac_lag", "lag"),
        "",
        f"> **Trạng thái kết luận: {_status_label(annual['status'])}.** {annual['status_reason']}",
        "",
        "> **Giới hạn thiết kế:** dải dữ liệu là 07/2025–07/2026, **không** trùng năm dương lịch. "
        "Vì vậy đại lượng trên là trung bình **giai đoạn quan sát**, không phải 'trung bình năm' "
        "theo định nghĩa quy chuẩn. Nó là chỉ báo mức nền, không phải một phán quyết tuân thủ.",
        "",
        "---",
        "",
        "## 8. Family xác nhận — p thô, p Holm và trạng thái kết luận",
        "",
        "| Kiểm định | Thống kê | p (hiệu chỉnh phụ thuộc) | p Holm | Effect size | Trạng thái |",
        "|---|---|---|---|---|---|",
        holm_rows,
        "",
        f"**Kết luận sau hiệu chỉnh Holm: {n_reject}/4 kiểm định bác bỏ H₀** (α = "
        f"{format_number_vi(ALPHA, 2)}), trong đó {n_exploratory} kiểm định bị hạ xuống "
        "*thăm dò* theo quy tắc R1–R3 của mục 4.1.",
        "",
        "**Đối chiếu với phương pháp cũ (giả định quan sát độc lập).**",
        "",
        "| Kiểm định | p tham chiếu | p Holm (tham chiếu) | Kết luận (tham chiếu) |",
        "|---|---|---|---|",
        reference_rows,
        "",
        f"Phương pháp cũ cho **{n_reject_reference}/4 bác bỏ H₀**; phương pháp có xét phụ thuộc "
        f"thời gian cho **{n_reject}/4**. Đây là **thay đổi kết luận do phương pháp**, không phải "
        "do dữ liệu thay đổi: p-value của SciPy trên chuỗi tự tương quan coi "
        f"{format_int_vi(n)} ngày như {format_int_vi(n)} quan sát độc lập, trong khi thực tế "
        f"n_eff ≈ {format_number_vi(eff['n_effective'], 1)} (lạm phát ×"
        f"{format_number_vi(eff['inflation_factor'], 2)}) — p-value cũ vì vậy **lạc quan**. "
        "Mục 9 định lượng mức lạc quan đó bằng mô phỏng.",
        "",
        "---",
        "",
        "## 9. Kiểm soát sai lầm loại I bằng mô phỏng dưới H₀",
        "",
    ]

    if simulation:
        size_rows = []
        for name, entry in simulation["size"].items():
            power = simulation["power"].get(name, {})
            size_rows.append(
                f"| {name} | {format_number_vi(entry['size_independence'] * 100, 1)}% | "
                f"{format_number_vi(entry['size_dependence_aware'] * 100, 1)}% | "
                f"{format_number_vi(entry['size_supporting'] * 100, 1)}% | "
                f"{format_number_vi(power.get('size_independence', float('nan')) * 100, 1)}% | "
                f"{format_number_vi(power.get('size_dependence_aware', float('nan')) * 100, 1)}% | "
                f"{format_number_vi(power.get('size_supporting', float('nan')) * 100, 1)}% |"
            )
        lines += [
            "Mô phỏng trên chuỗi **AR(1)** có cùng mức tự tương quan như dữ liệu thật "
            f"(ρ = {format_number_vi(simulation['rho_used'], 4)}, n = {format_int_vi(simulation['n_days'])} "
            f"ngày, {format_int_vi(simulation['n_sim'])} lần lặp, seed {meta['bootstrap_seed']}). "
            "Cột **size** là tỷ lệ bác bỏ H₀ khi H₀ **đúng**; cột **power** là tỷ lệ bác bỏ khi "
            "có hiệu ứng +1 đơn vị.",
            "",
            "| Phép kiểm | size (giả định độc lập) | size (phương pháp chính) | size (đối chứng) | power (độc lập) | power (chính) | power (đối chứng) |",
            "|---|---|---|---|---|---|---|",
            "\n".join(size_rows),
            "",
            f"**Đọc kết quả.** Ở α = {format_number_vi(ALPHA, 0)}%, một phép kiểm hợp lệ phải bác bỏ "
            "khoảng 5% số lần dưới H₀. Các phép kiểm SciPy dùng trong phiên bản cũ bác bỏ **hàng "
            "chục tới gần 80%** số lần dưới H₀ — bằng chứng định lượng rằng chúng **không** kiểm "
            "soát được sai lầm loại I trên dữ liệu này. Phương pháp có xét phụ thuộc thời gian "
            "đưa tỷ lệ này về gần α (vẫn hơi lạc quan ở mức ~2–3 lần α do quá trình gần phân kỳ "
            "đơn vị và vì bản số hữu hạn).",
            "",
            "> **Giới hạn của bằng chứng này:** mô phỏng dùng chuỗi AR(1) — một xấp xỉ của phụ thuộc "
            "quan sát được. Nó **không** thay thế lý thuyết: mọi phương pháp hiệu chỉnh đều là xấp "
            "xỉ, và cỡ mẫu hiệu dụng nhỏ (n_eff ≈ "
            f"{format_number_vi(eff['n_effective'], 0)}) giới hạn mọi phép kiểm.",
            "",
        ]
    else:
        lines += [
            "> Mô phỏng kiểm soát sai lầm loại I **không có** trong payload này "
            "(`include_simulation=False`).",
            "",
        ]

    cov = generalization["coverage"]
    cov_rows = "\n".join(
        f"| {SEASON_LABELS_VI[season]} | {format_int_vi(cov[season]['calendar_days'])} | "
        f"{format_int_vi(cov[season]['kept_days'])} | {format_int_vi(cov[season]['dropped_days'])} | "
        f"{format_number_vi(cov[season]['kept_share'] * 100, 1)}% |"
        for season in SEASON_DISPLAY_ORDER
        if season in cov
    )
    breakdown = generalization["season_year_breakdown"]
    breakdown_rows = "\n".join(
        f"| {SEASON_LABELS_VI[row['season']]} | {int(row['season_year'])} | "
        f"{format_int_vi(row['size'])} | {format_number_vi(row['median'], 2)} |"
        for _, row in breakdown.iterrows()
    )
    repeated = generalization["seasons_with_multiple_years"]
    if repeated:
        repeated_text = (
            ", ".join(
                f"{SEASON_LABELS_VI[season]} (mùa-vụ {years[0]} và {years[1]})"
                for season, years in repeated.items()
            )
            + ". Ngay cả mùa đó cũng chỉ được quan sát **một phần**, nên chưa thể so sánh hai năm "
            "một cách có ý nghĩa."
        )
    else:
        repeated_text = (
            "**không mùa nào** xuất hiện ở hai mùa-vụ khác nhau — panel kết thúc ở "
            f"{audit['coverage_last']} nên mùa Hè 2026 chưa kịp vào panel. So sánh cùng một mùa "
            "giữa hai năm vì vậy **không khả thi** với bộ dữ liệu này."
        )
    lines += [
        "## 10. Khả năng khái quát hóa kết quả theo mùa",
        "",
        "Câu hỏi mà bốn kiểm định trên **không** trả lời được: khác biệt mùa quan sát được ở "
        "giai đoạn 07/2025–07/2026 có phải là quy luật mùa vụ ổn định nhiều năm không? Bốn dữ kiện "
        "dưới đây nói: **không thể khẳng định**.",
        "",
        f"1. **Chỉ một chu kỳ mùa.** Dải quan sát dài {format_int_vi(audit['span_days'])} ngày lịch "
        "và chứa **một** vòng mùa. Mỗi mùa là **một đoạn thời gian liên tiếp**, nên 'mùa' và "
        "'thời gian' là hai cách gọi khác nhau của cùng một biến — không thể tách chúng ngoài một "
        "chu kỳ.",
        f"2. **Xu hướng thời gian cùng cỡ với khác biệt mùa.** Hồi quy HAC ước lượng xu hướng tuyến "
        f"tính {format_number_vi(generalization['trend_per_month'], 2)} µg/m³ mỗi tháng, tức "
        f"{format_number_vi(abs(generalization['trend_over_period']), 1)} µg/m³ trên cả năm — bằng "
        f"{format_number_vi(generalization['trend_to_contrast_ratio'] * 100, 0)}% độ lớn khác biệt "
        f"lớn nhất giữa các mùa ({format_number_vi(generalization['max_season_contrast'], 1)} "
        "µg/m³). Xu hướng tuyến tính **không giải thích** khác biệt mùa, nhưng nó cho thấy hai "
        "cấu phần cạnh tranh; một mô hình xu hướng phi tuyến khác sẽ cho kết luận khác.",
        f"3. **Mẫu không cân bằng và thiếu hụt không ngẫu nhiên.** Số ngày giữ lại khác nhau theo "
        "mùa, và phần thiếu rơi không đều (mùa Đông mất nhiều ngày nhất). Điều này làm giảm "
        "cỡ mẫu hiệu dụng của mùa Đông — mùa có hiệu ứng mạnh nhất cũng là mùa bị thiếu dữ liệu "
        "nhiều nhất.",
        f"4. **Số mùa có mặt ở hai mùa-vụ khác nhau:** {repeated_text}",
        "",
        "| Mùa | Ngày lịch trong dải | Ngày giữ lại | Ngày bị loại | Tỷ lệ giữ lại |",
        "|---|---|---|---|---|",
        cov_rows,
        "",
        "| Mùa | Mùa-vụ (năm bắt đầu của mùa) | n ngày | Trung vị |",
        "|---|---|---|---|",
        breakdown_rows,
        "",
        "> **Kết luận về khả năng khái quát hóa.** Kết quả mùa trong báo cáo này là **mô tả của một "
        "giai đoạn quan sát duy nhất**, ở một trạm duy nhất, với điều kiện khí tượng của chính năm "
        "đó. Không có bằng chứng nào trong bộ dữ liệu cho phép nói rằng đây là quy luật mùa vụ "
        "ổn định nhiều năm. Vì vậy kiểm định mùa ở mục 5 bị hạ xuống **THĂM DÒ** và kết luận mùa "
        "được trình bày như **hiệu ứng mô tả**, không phải xác nhận.",
        "",
        "---",
        "",
        "## 11. Kiểm tra độ nhạy (exploratory, không thuộc family nào)",
        "",
        "### 11.1. Ghép cặp theo tuần cho weekday/weekend",
        "",
        f"- Số tuần đủ điều kiện (≥ {paired['min_weekdays']} ngày trong tuần và "
        f"≥ {paired['min_weekend_days']} ngày cuối tuần): **{format_int_vi(paired['n_weeks'])}**.",
        f"- Trung vị chênh lệch (weekday − weekend): "
        f"**{format_number_vi(paired['median_difference'], 2)} µg/m³**, "
        f"CI 95% bootstrap {_ci_text(paired['ci'])}.",
        f"- Tỷ lệ tuần có weekday cao hơn: "
        f"{format_number_vi(paired['share_weekday_higher'] * 100, 1)}%.",
        f"- Signed-rank có HAC (Newey–West, lag 4 tuần) trên "
        f"{format_int_vi(paired['test']['n'])} chênh lệch tuần: "
        f"t = {format_number_vi(paired['test']['statistic'], 3)}, "
        f"p = {_p(paired['test']['p_value'])} → "
        f"{'bác bỏ' if paired['test']['p_value'] < ALPHA else 'không bác bỏ'} H₀ ở α = 0,05 "
        f"(tham chiếu, giả định độc lập: p = {_p(paired['test']['p_value_independence'])}).",
        "",
        "Phép thử này loại bỏ biến thiên giữa các tuần và không dựa vào giả định các ngày độc "
        "lập. Nếu kết luận khác với kiểm định ở mục 6, kết luận đúng là **không ổn định** — và đó "
        "phải là điều được viết ra.",
        "",
        "### 11.2. Kruskal-Wallis trên trung bình tuần theo mùa",
        "",
        f"- Số tuần dùng được: {format_int_vi(sensitivity['season_weekly']['n_weeks'])}; "
        f"H = {format_number_vi(weekly_season['statistic'], 3)}, df = {weekly_season['df']}, "
        f"p (hiệu chỉnh phụ thuộc) = {_p(weekly_season['p_value'])}, "
        f"p tham chiếu = {_p(weekly_season['p_value_independence'])}, ε² = "
        f"{format_number_vi(weekly_season['effect_size'], 4)}.",
        "- Ở mức tuần, cỡ mẫu nhỏ hơn nhiều nên power thấp; p không có ý nghĩa **không** phủ định "
        "kết quả mức ngày, và p có ý nghĩa thì củng cố. Mục đích duy nhất là kiểm tra kết luận mùa "
        "có phụ thuộc vào giả định độc lập của từng ngày hay không.",
        "",
        "---",
        "",
        "## 12. Đọc p-value cho đúng (task 5.7)",
        "",
        "p-value là xác suất **của dữ liệu, có điều kiện H₀ đúng** — không phải xác suất H₀ đúng, "
        "cũng không phải xác suất kết quả lặp lại. Bốn sai lầm thường gặp và cách đọc đúng:",
        "",
        "| Sai lầm | Vì sao sai | Cách đọc đúng trong báo cáo này |",
        "|---|---|---|",
        "| p là xác suất H₀ đúng | p tính dưới giả định H₀; nó không phải xác suất hậu nghiệm | Chỉ nói 'dữ liệu không tương thích với H₀ ở mức α' |",
        "| 1 − p là xác suất H₁ đúng | H₁ thường là hợp, không có phân phối tiên nghiệm | Không gán xác suất cho H₁ |",
        "| p nhỏ = hiệu ứng lớn | p phụ thuộc cỡ mẫu; n_eff ≈ "
        f"{format_number_vi(eff['n_effective'], 0)} mới là cỡ mẫu có ý nghĩa ở đây | Luôn đọc kèm effect size và CI |",
        "| p > α = 'không có hiệu ứng' | Đó là 'không đủ bằng chứng', không phải bằng chứng không | Nêu rõ giới hạn power của từng phép kiểm |",
        "",
        "**Power = 1 − β, và độ phân giải của phép kiểm có giới hạn cụ thể.** Với SD gộp "
        f"{format_number_vi(mde['pooled_sd'], 2)} µg/m³, n₁ = {format_int_vi(mde['n_a'])}, "
        f"n₂ = {format_int_vi(mde['n_b'])}, chênh lệch nhỏ nhất phát hiện được ở power "
        f"{format_number_vi(mde['power'] * 100, 0)}%, α = 0,05 là **MDE ≈ "
        f"{format_number_vi(mde['mde'], 2)} µg/m³** (xấp xỉ chuẩn, giả định độc lập). Chênh lệch "
        f"trung vị quan sát ở mục 6 là {format_number_vi(abs(weekday['median_difference']), 2)} "
        f"µg/m³, tức {'nhỏ hơn' if mde['mde'] > abs(weekday['median_difference']) else 'không nhỏ hơn'} "
        "MDE. Vì thế kết quả ở mục 6 **không** chứng minh hai nhóm bằng nhau: nó chỉ cho thấy dữ liệu "
        "không đủ độ phân giải để tách 'không có khác biệt' khỏi 'khác biệt nhỏ hơn MDE'. Với bài toán "
        "cảnh báo, sai lầm loại II (bỏ lọt một đợt ô nhiễm) tốn kém hơn sai lầm loại I, nên ngưỡng "
        "vận hành của mô hình ở Issue #13 sẽ được chọn theo Recall chứ không theo Accuracy.",
        "",
        "---",
        "",
        "## 13. Prior probability và bẫy base-rate (task 5.8)",
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
        "## 14. Giới hạn khoa học",
        "",
        "1. **Một chu kỳ mùa, một trạm.** Dải 07/2025–07/2026 chỉ chứa một vòng mùa và toàn bộ dữ "
        "liệu đến từ một trạm đô thị. Khác biệt theo mùa là mô tả của **giai đoạn này**, không "
        "ngoại suy được sang năm khác hay trạm khác (mục 10).",
        "2. **Hiệu chỉnh phụ thuộc thời gian là xấp xỉ, không phải định nghĩa.** Mọi phương pháp ở "
        "mục 4 đều là phương pháp bậc cao với giả định ổn định; mô phỏng (mục 9) cho thấy tỷ lệ bác "
        "bỏ dưới H₀ còn cao hơn α khoảng 2–3 lần. p-value vì vậy là **chỉ báo độ tương thích**, "
        "không phải xác suất chính xác tuyệt đối.",
        "3. **Kết luận mùa đã bị hạ xuống thăm dò** vì p-value của kiểm định omnibus mùa không "
        "ổn định theo độ dài block (mục 5). Đây là hạn chế thật, không phải khiêm tốn hình thức.",
        "4. **Block bootstrap là xấp xỉ.** Block 28 ngày giữ cấu trúc theo tuần nhưng không mô "
        "phỏng được phụ thuộc dài hạn hơn nữa; với so sánh hai nhóm, resample trên chuỗi gộp bỏ "
        "qua tương quan chéo nhóm — kiểm tra ghép cặp theo tuần ở mục 11.1 là biện pháp bù.",
        "5. **Ngưỡng 18/24 giờ** là quy ước phân tích (độ phủ 75%), không phải điều khoản QCVN. "
        "Đổi ngưỡng sẽ đổi n; bảng nhật ký lọc ở mục 1 làm việc đổi ngưỡng trở nên minh bạch.",
        "6. **QCVN 05:2023/BTNMT quy định ở điều kiện chuẩn (µg/Nm³, 25 °C, 760 mmHg)**, còn trạm "
        "OpenAQ báo nồng độ môi trường (µg/m³). So sánh định lượng với ngưỡng vì vậy là xấp xỉ.",
        "7. **Không có kết luận nhân quả.** Khác biệt theo mùa/ngày trong tuần là liên hệ thống kê; "
        "nguồn phát thải, khí tượng và điều kiện biên không được phân tách ở đây.",
        "8. **Kết quả mô phỏng không thay thế lý thuyết và không được tái lập ngoài dữ liệu này** — "
        "mô phỏng dùng mô hình AR(1), không phải dữ liệu thật.",
        "",
        "---",
        "",
        "## 15. Tái lập",
        "",
        "```bash",
        "python -m unittest tests.test_inference -v          # kiểm thử tất định",
        "python -c \"from src.inference import run_inference, render_inference_report, DEFAULT_REPORT_PATH; \" \\",
        "          \"DEFAULT_REPORT_PATH.write_text(render_inference_report(run_inference()), encoding='utf-8')\"",
        "```",
        "",
        f"Mọi con số tái lập được với seed {meta['bootstrap_seed']}, {format_int_vi(meta['n_bootstrap'])} "
        f"lặp CI bootstrap và {format_int_vi(meta['n_null_bootstrap'])} lặp null bootstrap. Sai khác "
        "duy nhất có thể có là phiên bản NumPy/SciPy (đã ghi ở đầu báo cáo).",
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

    test = results["tests"]["season_effect"]
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
        "Hình 9 — Khác biệt PM2.5 theo mùa: Kruskal-Wallis, null bootstrap block",
        loc="left",
        fontsize=12,
    )
    ax.text(
        0.99,
        0.98,
        (
            f"H = {format_number_vi(test['statistic'], 3)}, df = {test['df']}\n"
            f"p (null bootstrap, có xét phụ thuộc) = {format_number_vi(test['p_value'], 4)}\n"
            f"p Holm = {format_number_vi(test['p_holm'], 4)}\n"
            f"p tham chiếu (giả định độc lập) = {format_scientific_vi(test['p_value_independence'])}\n"
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
        "Hộp = IQR, đường giữa = trung vị, râu = 1,5·IQR; điểm = quan sát ngoài râu. "
        "Kết luận mùa: THĂM DÒ (p không ổn định theo độ dài block).",
        fontsize=8.4,
        color="#4a4a4a",
    )
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def _figure_weekday(results: Mapping[str, Any]):
    """FIG-10 — ngày làm việc vs cuối tuần, boxplot + strip tất định."""
    import matplotlib.pyplot as plt

    from src.visualizer import PALETTE, apply_tufte_style

    test = results["tests"]["weekday_effect"]
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
        "Hình 10 — Ngày làm việc và cuối tuần: Mann-Whitney U, null bootstrap block",
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
            f"p (null bootstrap) = {format_number_vi(test['p_value'], 4)}, "
            f"p Holm = {format_number_vi(test['p_holm'], 4)}\n"
            f"p tham chiếu (độc lập) = {format_number_vi(test['p_value_independence'], 4)}\n"
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
        "Hình 12 — Tự tương quan: vì sao đơn vị phân tích là ngày và mọi resample phải theo block",
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
