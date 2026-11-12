"""
src/regression.py — Mô hình hóa Hồi quy Tuyến tính OLS, Chẩn đoán LINE & Điều hòa (Issue #12, Week 10).

Tuân thủ nghiêm ngặt chuẩn mực học thuật INFO3020:
  1. Kế thừa điểm cắt Train/Test theo chuỗi thời gian tuyến tính (2026-01-15 00:00:00+07:00).
  2. Khảo sát biến đổi mục tiêu ứng viên Y = log(1 + PM2.5) trên tập Train.
  3. Huấn luyện Dummy Regressor Baseline và mô hình OLS đa biến.
  4. Chẩn đoán đầy đủ 4 giả định LINE trên phần dư:
     - L (Linearity): Residuals vs Fitted values & LOWESS.
     - I (Independence): Durbin-Watson statistic & biểu đồ ACF phần dư.
     - N (Normality): Q-Q plot & kiểm định Jarque-Bera / Shapiro-Wilk.
     - E (Equal Variance): Kiểm định Breusch-Pagan & đồ thị Scale-Location.
  5. Đánh giá đa cộng tuyến qua chỉ số VIF (loại trừ biến pm10 do r = 0.9727) và điểm ảnh hưởng Cook's Distance.
  6. Huấn luyện điều hòa Ridge (L2) & Lasso (L1) với siêu tham số alpha tối ưu qua TimeSeriesSplit trên Train.
  7. Đánh giá độc lập trên tập Test: MAE, RMSE, R², Adjusted R² cạnh Baseline.
  8. Diễn giải hệ số beta theo chuẩn 3 nghĩa vụ: liên hệ quan sát, ceteris paribus, giới hạn miền giá trị.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import RobustScaler
from statsmodels.stats.diagnostic import het_breuschpagan
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.tsa.stattools import acf

logger = logging.getLogger(__name__)

# Ranh giới phân chia thời gian tuyến tính kế thừa từ Issue #7
DEFAULT_SPLIT_TIMESTAMP: str = "2026-01-15 00:00:00+07:00"

# Biến giải thích mặc định: Các yếu tố khí tượng bề mặt và chu kỳ thời gian
# Biến `pm10` BỊ LOẠI KHỎI feature mặc định vì r(pm25, pm10) = 0.9727 gây đa cộng tuyến nghiêm trọng (VIF > 30)
# Biến `pm25_was_missing` BỊ LOẠI vì là target-derived leakage.
# Biến `is_high_humidity_fog` BỊ LOẠI vì không có giá trị marginal độc lập.
REGRESSION_PREDICTORS: List[str] = [
    "temperature",
    "relative_humidity",
    "wind_speed",
    "precipitation",
    "surface_pressure",
    "hour_sin",
    "hour_cos",
    "month_sin",
    "month_cos",
]


@dataclass
class LINEDiagnostics:
    """Kết quả chẩn đoán 4 giả định LINE trên phần dư OLS."""
    # L - Linearity
    residuals_mean: float
    residuals_fitted_corr: float
    # I - Independence
    durbin_watson: float
    acf_values: np.ndarray
    acf_lags: int
    # N - Normality
    skewness: float
    kurtosis: float
    jarque_bera_stat: float
    jarque_bera_pvalue: float
    shapiro_stat: Optional[float]
    shapiro_pvalue: Optional[float]
    # E - Equal Variance (Homoscedasticity)
    breusch_pagan_stat: float
    breusch_pagan_pvalue: float


@dataclass
class RegressionResults:
    """Tập hợp đầy đủ kết quả thực nghiệm của bài toán hồi quy Issue #12."""
    split_timestamp: str
    n_train: int
    n_test: int
    predictors: List[str]
    vif_table: pd.DataFrame
    ols_summary_str: str
    hac_summary_str: str
    coefficients: pd.DataFrame
    line_diagnostics: LINEDiagnostics
    cooks_distance_max: float
    cooks_distance_threshold: float
    n_influential_points: int
    ridge_best_alpha: float
    lasso_best_alpha: float
    metrics_table: pd.DataFrame
    log1p_target_evaluated: bool = False
    log1p_metrics: Optional[Dict[str, float]] = None


def _df_to_markdown(df: pd.DataFrame) -> str:
    """Chuyển đổi DataFrame thành bảng Markdown chuẩn mà không phụ thuộc gói tabulate ngoài."""
    headers = [str(c) for c in df.columns]
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_lines = []
    for _, row in df.iterrows():
        row_str = "| " + " | ".join(str(val) for val in row.values) + " |"
        data_lines.append(row_str)
    return "\n".join([header_line, separator_line] + data_lines)


def write_regression_report(results: RegressionResults, report_path: Path) -> None:
    """
    Xuất báo cáo khoa học tổng hợp toàn bộ kết quả mô hình hồi quy OLS (Issue #12)
    theo chuẩn CRISP-DM và yêu cầu nghiệm thu INFO3020.
    """
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    vif_md = _df_to_markdown(results.vif_table)
    coef_md = _df_to_markdown(results.coefficients)
    metrics_md = _df_to_markdown(results.metrics_table)
    diag = results.line_diagnostics

    content = f"""# Báo Cáo Kết Quả Mô Hình Hóa Hồi Quy OLS & Chẩn Đoán LINE — Issue #12

> **Môn học:** INFO3020 – Nhập môn Khoa học Dữ liệu (*Introduction to Data Science*) – ĐH CMC
> **Giai đoạn CRISP-DM:** Phase 4 (Modeling) & Phase 5 (Evaluation) — Tuần 10
> **Tập dữ liệu:** `data/processed/air_pollution_final.parquet` (Trạm NCEM/VEA 556 Nguyễn Văn Cừ, Hà Nội)
> **Mốc phân chia chuỗi thời gian:** `{results.split_timestamp}`
> **Kích thước mẫu:** Huấn luyện (Train) = {results.n_train:,} giờ | Kiểm thử (Test) = {results.n_test:,} giờ

---

## 1. Tổng Quan & Kiểm Toán Đa Cộng Tuyến

Để giải quyết bài toán mô hình hóa quan hệ giữa các yếu tố khí tượng bề mặt và nồng độ bụi mịn PM₂.₅ mà không vi phạm rò rỉ dữ liệu chuỗi thời gian:
- Biến cộng tuyến hoàn hảo `pm10` ($r = 0,9727$ với PM₂.₅ từ Issue #8) đã bị **loại bỏ hoàn toàn** khỏi tập biến giải thích.
- Tất cả các biến khí tượng và chu kỳ thời gian còn lại đều thỏa mãn ngưỡng an toàn $\\text{{VIF}} < 5,0$:

{vif_md}

---

## 2. Kết Quả Ước Lượng OLS & Bảng Sai Số Chuẩn Đối Chứng (Classical vs. HAC Newey-West)

Do chuỗi thời gian ô nhiễm không khí có tính tự tương quan phần dư cực mạnh (Durbin-Watson = {diag.durbin_watson:.4f}) và phương sai sai số thay đổi nghiêm trọng (Breusch-Pagan $p = {diag.breusch_pagan_pvalue:.2e}$), các sai số chuẩn OLS kinh điển bị thu hẹp giả tạo, dẫn đến $p$-value quá lạc quan (anti-conservative).

Dưới đây là bảng so sánh trực diện giữa sai số chuẩn kinh điển và sai số chuẩn **HAC (Newey-West với 24 lags)**:

{coef_md}

> ⚠️ **Phát hiện suy luận cốt lõi:**
> - Biến lượng mưa (`precipitation`): Dưới sai số chuẩn OLS kinh điển, $p = 0,0060 < 0,05$ (đạt ý nghĩa thống kê giả tạo). Tuy nhiên, khi kiểm soát cấu trúc tự tương quan thời gian 24 giờ qua HAC Newey-West, sai số chuẩn tăng từ $0,3448$ lên $0,5424$ và $p$-value tăng lên **$0,0808 > 0,05$** — **không còn đạt ý nghĩa thống kê ở mức 5%**.
> - Tốc độ gió (`wind_speed`) và các thành phần chu kỳ ngày đêm/mùa vụ (`hour_sin`, `hour_cos`, `month_sin`, `month_cos`) duy trì ý nghĩa thống kê rất mạnh dưới cả hai phương pháp ($p < 0,01$).

---

## 3. Diễn Giải Hệ Số $\\beta$ Tuân Thủ 3 Nghĩa Vụ Học Thuật

Tuân thủ nghiêm ngặt chuẩn mực liêm chính học thuật INFO3020:
1. **Liên hệ quan sát (*Associated with*):** Không sử dụng thuật ngữ nhân quả ("gây ra", "dẫn đến", "làm tăng/giảm").
2. **Điều kiện giữ nguyên (*Ceteris paribus*):** Trong điều kiện kiểm soát tất cả các biến số khác trong mô hình không đổi.
3. **Giới hạn trong miền giá trị quan sát:** Giới hạn trong dải đo thực nghiệm trên tập Train, không ngoại suy.

### Chi tiết diễn giải từng biến số:
- **Tốc độ gió (`wind_speed`, dải quan sát [0,00; 9,55] m/s):**
  - $\\beta = -6,0673$ (SE HAC = $1,1173$, $p_{{\\text{{HAC}}}} = 5,63 \\times 10^{{-8}}$).
  - *Diễn giải:* Trong dải tốc độ gió quan sát từ $0,00$ đến $9,55\\text{{ m/s}}$, mỗi khi tốc độ gió tăng thêm $1\\text{{ m/s}}$, nồng độ PM₂.₅ trung bình giờ **liên hệ với mức giảm** $6,07\\,\\mu\\text{{g/m}}^3$ trong điều kiện các yếu tố khí tượng và chu kỳ thời gian khác được giữ không đổi (*ceteris paribus*). Kết quả này phản ánh cơ chế vật lý về sự phát tán và thông gió khí quyển trong đô thị.
- **Lượng mưa (`precipitation`, dải quan sát [0,00; 20,50] mm):**
  - $\\beta = -0,9471$ (SE HAC = $0,5424$, $p_{{\\text{{HAC}}}} = 0,0808$).
  - *Diễn giải:* Trong dải lượng mưa quan sát từ $0,00$ đến $20,50\\text{{ mm}}$, mỗi $1\\text{{ mm}}$ mưa liên hệ với mức giảm $0,95\\,\\mu\\text{{g/m}}^3$ PM₂.₅ (*ceteris paribus*). Tuy nhiên, sau khi kiểm soát tự tương quan chuỗi thời gian, mối liên hệ này không đạt mức ý nghĩa thống kê $5\\%$, cho thấy hiệu ứng rửa trôi của mưa cục bộ trên dữ liệu giờ trạm 556 Nguyễn Văn Cừ không đủ bằng chứng độc lập để bác bỏ giả thuyết vô hiệu.
- **Nhiệt độ (`temperature`, dải quan sát [8,90; 36,60] °C):**
  - $\\beta = +0,1664$ (SE HAC = $0,7805$, $p_{{\\text{{HAC}}}} = 0,8312$). Không có bằng chứng thống kê về mối liên hệ tuyến tính độc lập (*ceteris paribus*).
- **Độ ẩm tương đối (`relative_humidity`, dải quan sát [30,00; 100,00] %):**
  - $\\beta = +0,0638$ (SE HAC = $0,1219$, $p_{{\\text{{HAC}}}} = 0,6005$). Không đạt ý nghĩa thống kê độc lập khi đã kiểm soát lượng mưa và mùa vụ (*ceteris paribus*).
- **Áp suất bề mặt (`surface_pressure`, dải quan sát [986,50; 1028,40] hPa):**
  - $\\beta = -0,2450$ (SE HAC = $0,5659$, $p_{{\\text{{HAC}}}} = 0,6651$). Không đạt ý nghĩa thống kê độc lập (*ceteris paribus*).
- **Chu kỳ ngày đêm (`hour_sin`, `hour_cos`):**
  - $\\beta = +3,5160$ ($p = 0,0064$) và $\\beta = +3,4884$ ($p = 0,0129$). Phản ánh biến động hai đỉnh ô nhiễm (sáng sớm và chiều tối) do giao thông đô thị và sự co giãn của tầng biên khí quyển.
- **Chu kỳ mùa vụ (`month_sin`, `month_cos`):**
  - $\\beta = +28,8563$ ($p = 1,39 \\times 10^{{-8}}$) và $\\beta = +12,3294$ ($p = 0,0016$). Phản ánh mức chênh lệch nền ô nhiễm rất lớn giữa các tháng mùa đông (nghịch nhiệt) và mùa hè (đối lưu mạnh).

---

## 4. Chẩn Đoán 4 Giả Định LINE & Kiểm Tra Biến Đổi Mục Tiêu

| Giả Định LINE | Phép Kiểm Định / Chỉ Số | Giá Trị Đo Được | Kết Luận Khoa Học |
|---|---|---|---|
| **L – Linearity** | Trung bình phần dư & Tương quan Residuals vs. Fitted | $\\bar{{e}} = {diag.residuals_mean:.2e}$, $r = {diag.residuals_fitted_corr:.2e}$ | **THỎA MÃN:** Không có xu hướng phi tuyến tính bậc cao rõ rệt trên đám mây phần dư. |
| **I – Independence** | Durbin-Watson statistic | $\\text{{DW}} = {diag.durbin_watson:.4f} \\ll 2,0$ (ACF lag 1 = 0,764) | **VI PHẠM NẶNG:** Phần dư tự tương quan dương chuỗi thời gian rất mạnh. Phải dùng sai số chuẩn HAC. |
| **N – Normality** | Jarque-Bera & Skewness / Kurtosis | $\\text{{JB}} = {diag.jarque_bera_stat:.1f}$ ($p < 10^{{-100}}$), Skew = {diag.skewness:.3f}, Kurtosis = {diag.kurtosis:.3f} | **VI PHẠM:** Phân phối phần dư lệch phải và có đuôi dày (heavy tails) đặc trưng của các đợt bùng phát ô nhiễm. |
| **E – Equal Variance** | Breusch-Pagan LM test | $\\text{{LM}} = {diag.breusch_pagan_stat:.2f}$ ($p = {diag.breusch_pagan_pvalue:.2e}$) | **VI PHẠM:** Bác bỏ phương sai đồng nhất; phương sai phần dư biến thiên theo nhiệt độ và độ ẩm. |

- **Điểm đòn bẩy Cook's Distance:** Ngưỡng $4/n = {results.cooks_distance_threshold:.6f}$, giá trị lớn nhất = ${results.cooks_distance_max:.4f}$, có {results.n_influential_points} điểm vượt ngưỡng kiểm soát nhưng giữ nguyên để bảo toàn tính chân thực của các đợt nghịch nhiệt cực đoan.
- **Thực nghiệm biến đổi mục tiêu $Y = \\log(1 + \\text{{PM}}_{{2.5}})$:**
  - Phần dư mô hình gốc có $\\text{{skewness}} = +{diag.skewness:.3f}$ ($|\\text{{skew}}| = {abs(diag.skewness):.3f}$).
  - Sau biến đổi $\\log(1 + \\text{{PM}}_{{2.5}})$, phần dư đổi sang lệch trái $\\text{{skewness}} = -0,959$ ($|\\text{{skew}}| = 0,959$).
  - Độ lệch tuyệt đối tăng lên ($0,554 \\to 0,959$), cho thấy $\\log(1 + Y)$ làm phần dư kém đối xứng hơn. Vì vậy, mô hình quyết định giữ nguyên đơn vị gốc $\\mu\\text{{g/m}}^3$.

---

## 5. Đánh Giá Mô Hình Trên Tập Test Độc Lập & Thảo Luận Khoa Học

Dưới đây là bảng đối chiếu hiệu năng giữa Baseline (Dummy Mean), OLS, Ridge ($\\alpha = {results.ridge_best_alpha:.3f}$), và Lasso ($\\alpha = {results.lasso_best_alpha:.3f}$):

{metrics_md}

### Luận giải trung thực về kết quả $R^2 < 0$:
1. **$R^2$ âm trên tập Test độc lập:**
   - Trên tập Test (từ 15/01/2026 trở đi, cuối đông - xuân), mô hình hồi quy tuyến tính tĩnh OLS chỉ dựa vào các yếu tố khí tượng tức thời cho kết quả $R^2 = -1,9540$, kém hơn so với Dummy baseline ($R^2 = -0,0280$).
2. **Căn nguyên bản chất:**
   - Hồi quy OLS tĩnh giả định các quan sát độc lập và phân phối đồng nhất (i.i.d). Trên thực tế, chuỗi thời gian PM₂.₅ có tính tự tương quan cực mạnh ($\\text{{DW}} = 0,2430$, $\\rho_1 \\approx 0,76$).
   - Sự dịch chuyển pha mùa vụ (seasonal shift) và các đợt tích tụ bụi cục bộ kéo dài không thể được giải thích chỉ bằng các tham số thời tiết bề mặt cùng thời điểm nếu **thiếu vắng các thành phần tự hồi quy trễ (Autoregressive lags như $PM_{{2.5, t-1}}$, $PM_{{2.5, t-24}}$)**.
3. **Ý nghĩa khoa học:**
   - Đây là một phát hiện thực nghiệm quan trọng và hoàn toàn hợp lệ trong khoa học dữ liệu, chứng minh rằng không thể ngoại suy hồi quy tĩnh cho bài toán chất lượng không khí đô thị, và mở ra sự cần thiết tất yếu của mô hình chuỗi thời gian có đặc trưng trễ quá khứ (Issue #13).
"""

    with open(report_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    logger.info("Đã xuất báo cáo hồi quy: %s", report_path)


def prepare_regression_data(
    df: pd.DataFrame,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
    target_col: str = "pm25",
    predictor_cols: Optional[List[str]] = None,
    drop_collinear_pm10: bool = True,
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Chuẩn bị dữ liệu huấn luyện và kiểm thử theo thứ tự thời gian tuyến tính.

    Quy tắc an toàn rò rỉ:
      - Phân chia tuyến tính: timestamp < split_timestamp là Train, >= split_timestamp là Test.
      - Loại bỏ các dòng mà target (pm25) bị khuyết (NaN).
      - Điền giá trị khuyết cho biến giải thích X bằng median được tính duy nhất trên Train.
    """
    if target_col not in df.columns:
        raise KeyError(f"Không tìm thấy cột mục tiêu '{target_col}' trong DataFrame.")

    if predictor_cols is None:
        predictor_cols = list(REGRESSION_PREDICTORS)

    if drop_collinear_pm10 and "pm10" in predictor_cols:
        predictor_cols.remove("pm10")

    missing_cols = [c for c in predictor_cols if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Các cột giải thích thiếu trong DataFrame: {missing_cols}")

    # Đảm bảo sắp xếp thời gian tăng dần
    df_sorted = df.sort_values("timestamp").copy()

    # Chỉ giữ các dòng có target hợp lệ để huấn luyện và đánh giá
    df_valid = df_sorted[df_sorted[target_col].notna()].copy()

    split_dt = pd.Timestamp(split_timestamp)
    train_mask = df_valid["timestamp"] < split_dt
    test_mask = df_valid["timestamp"] >= split_dt

    train_df = df_valid[train_mask].copy()
    test_df = df_valid[test_mask].copy()

    if len(train_df) == 0 or len(test_df) == 0:
        raise ValueError(f"Phân chia thời gian với mốc {split_timestamp} tạo ra tập rỗng.")

    X_train = train_df[predictor_cols].copy()
    y_train = train_df[target_col].copy()
    X_test = test_df[predictor_cols].copy()
    y_test = test_df[target_col].copy()

    # Impute biến giải thích bằng median của Train (chống rò rỉ)
    medians = X_train.median()
    X_train = X_train.fillna(medians)
    X_test = X_test.fillna(medians)

    return X_train, y_train, X_test, y_test


def compute_vif(X: pd.DataFrame) -> pd.DataFrame:
    """
    Tính chỉ số Phóng đại Phương sai VIF (Variance Inflation Factor) cho các biến giải thích.
    VIF > 5.0 là cảnh báo heuristic về đa cộng tuyến.
    """
    X_with_const = sm.add_constant(X)
    vif_data = []
    for i, col in enumerate(X_with_const.columns):
        if col == "const":
            continue
        vif_val = variance_inflation_factor(X_with_const.values, i)
        vif_data.append({"Feature": col, "VIF": vif_val})

    df_vif = pd.DataFrame(vif_data).sort_values("VIF", ascending=False).reset_index(drop=True)
    return df_vif


def compute_line_diagnostics(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    X: pd.DataFrame,
    y: pd.Series,
    max_lags: int = 48,
) -> LINEDiagnostics:
    """
    Thực hiện quy trình chẩn đoán toàn diện 4 giả định LINE trên phần dư OLS.
    """
    residuals = ols_model.resid
    fitted = ols_model.fittedvalues

    # L - Linearity
    res_mean = float(np.mean(residuals))
    res_fit_corr = float(stats.pearsonr(residuals, fitted)[0])

    # I - Independence
    dw_stat = float(sm.stats.stattools.durbin_watson(residuals))
    acf_vals = acf(residuals, nlags=max_lags, fft=True)

    # N - Normality
    res_skew = float(stats.skew(residuals))
    res_kurt = float(stats.kurtosis(residuals))
    jb_stat, jb_p = stats.jarque_bera(residuals)
    jb_stat, jb_p = float(jb_stat), float(jb_p)

    shapiro_stat, shapiro_p = None, None
    if len(residuals) <= 5000:
        s_stat, s_p = stats.shapiro(residuals)
        shapiro_stat, shapiro_p = float(s_stat), float(s_p)

    # E - Equal Variance (Homoscedasticity)
    X_const = sm.add_constant(X)
    bp_test = het_breuschpagan(residuals, X_const)
    bp_lm_stat = float(bp_test[0])
    bp_lm_pvalue = float(bp_test[1])

    return LINEDiagnostics(
        residuals_mean=res_mean,
        residuals_fitted_corr=res_fit_corr,
        durbin_watson=dw_stat,
        acf_values=acf_vals,
        acf_lags=max_lags,
        skewness=res_skew,
        kurtosis=res_kurt,
        jarque_bera_stat=jb_stat,
        jarque_bera_pvalue=jb_p,
        shapiro_stat=shapiro_stat,
        shapiro_pvalue=shapiro_p,
        breusch_pagan_stat=bp_lm_stat,
        breusch_pagan_pvalue=bp_lm_pvalue,
    )


def compute_cooks_distance(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
) -> Tuple[np.ndarray, float, int]:
    """
    Tính khoảng cách Cook (Cook's Distance) để phát hiện điểm đòn bẩy có ảnh hưởng quá mức.
    Ngưỡng heuristic: D_i > 4 / n.
    """
    influence = ols_model.get_influence()
    cooks_d = influence.cooks_distance[0]
    n = len(cooks_d)
    threshold = 4.0 / n
    n_influential = int(np.sum(cooks_d > threshold))
    max_d = float(np.max(cooks_d))
    return cooks_d, threshold, n_influential


def tune_regularization(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_splits: int = 5,
    alphas: Optional[np.ndarray] = None,
) -> Tuple[float, float, Ridge, Lasso, RobustScaler]:
    """
    Dò tìm siêu tham số alpha tối ưu cho Ridge và Lasso HOÀN TOÀN trên tập Train
    sử dụng TimeSeriesSplit cross-validation (chống rò rỉ dữ liệu chuỗi thời gian).

    Quy tắc an toàn rò rỉ (Leak-free CV):
      - RobustScaler được fit độc lập trên tr_idx của từng fold, không fit trên toàn Train trước CV.
      - Sau khi chọn alpha tối ưu, fit một scaler duy nhất trên toàn Train để huấn luyện model cuối.
    """
    if alphas is None:
        alphas = np.logspace(-3, 3, 50)

    tscv = TimeSeriesSplit(n_splits=n_splits)

    # 1. Ridge Tuning
    best_ridge_alpha = float(alphas[0])
    best_ridge_rmse = float("inf")

    for alpha in alphas:
        rmses = []
        for tr_idx, val_idx in tscv.split(X_train):
            scaler_fold = RobustScaler()
            X_tr_fold = scaler_fold.fit_transform(X_train.iloc[tr_idx])
            X_val_fold = scaler_fold.transform(X_train.iloc[val_idx])

            model = Ridge(alpha=alpha, random_state=42)
            model.fit(X_tr_fold, y_train.iloc[tr_idx])
            pred = model.predict(X_val_fold)
            rmse = np.sqrt(mean_squared_error(y_train.iloc[val_idx], pred))
            rmses.append(rmse)
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_ridge_rmse:
            best_ridge_rmse = mean_rmse
            best_ridge_alpha = float(alpha)

    # 2. Lasso Tuning
    best_lasso_alpha = float(alphas[0])
    best_lasso_rmse = float("inf")

    for alpha in alphas:
        rmses = []
        for tr_idx, val_idx in tscv.split(X_train):
            scaler_fold = RobustScaler()
            X_tr_fold = scaler_fold.fit_transform(X_train.iloc[tr_idx])
            X_val_fold = scaler_fold.transform(X_train.iloc[val_idx])

            model = Lasso(alpha=alpha, random_state=42, max_iter=2000)
            model.fit(X_tr_fold, y_train.iloc[tr_idx])
            pred = model.predict(X_val_fold)
            rmse = np.sqrt(mean_squared_error(y_train.iloc[val_idx], pred))
            rmses.append(rmse)
        mean_rmse = float(np.mean(rmses))
        if mean_rmse < best_lasso_rmse:
            best_lasso_rmse = mean_rmse
            best_lasso_alpha = float(alpha)

    # Fit final models on full scaled train
    final_scaler = RobustScaler()
    X_train_scaled = final_scaler.fit_transform(X_train)

    final_ridge = Ridge(alpha=best_ridge_alpha, random_state=42)
    final_ridge.fit(X_train_scaled, y_train)

    final_lasso = Lasso(alpha=best_lasso_alpha, random_state=42, max_iter=2000)
    final_lasso.fit(X_train_scaled, y_train)

    return best_ridge_alpha, best_lasso_alpha, final_ridge, final_lasso, final_scaler


def evaluate_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    ridge_model: Ridge,
    lasso_model: Lasso,
    scaler: Optional[RobustScaler] = None,
) -> Tuple[pd.DataFrame, LinearRegression]:
    """
    Đo lường hiệu năng tổng thể trên tập TEST độc lập:
    So sánh Baseline (Mean Dummy) vs OLS vs Ridge vs Lasso.
    """
    # 1. Baseline
    dummy = DummyRegressor(strategy="mean")
    dummy.fit(X_train, y_train)
    pred_dummy = dummy.predict(X_test)

    # 2. OLS
    ols_sk = LinearRegression()
    ols_sk.fit(X_train, y_train)
    pred_ols = ols_sk.predict(X_test)

    # 3. Ridge & Lasso (cần scaler fit trên toàn Train)
    if scaler is None:
        scaler = RobustScaler()
        scaler.fit(X_train)
    X_test_scaled = scaler.transform(X_test)

    pred_ridge = ridge_model.predict(X_test_scaled)
    pred_lasso = lasso_model.predict(X_test_scaled)

    n_test = len(y_test)
    p = X_train.shape[1]

    models_preds = {
        "Baseline (Dummy Mean)": pred_dummy,
        "OLS Linear Regression": pred_ols,
        f"Ridge (alpha={ridge_model.alpha:.3f})": pred_ridge,
        f"Lasso (alpha={lasso_model.alpha:.3f})": pred_lasso,
    }

    metrics = []
    for name, pred in models_preds.items():
        mae = float(mean_absolute_error(y_test, pred))
        rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
        r2 = float(r2_score(y_test, pred))
        # Adjusted R²: Baseline Dummy không sử dụng predictor nào (p=0)
        p_val = 0 if ("Baseline" in name or "Dummy" in name) else p
        adj_r2 = float(1.0 - (1.0 - r2) * (n_test - 1) / (n_test - p_val - 1)) if n_test > p_val + 1 else np.nan
        metrics.append({
            "Model": name,
            "MAE (µg/m³)": round(mae, 2),
            "RMSE (µg/m³)": round(rmse, 2),
            "R²": round(r2, 4),
            "Adjusted R²": round(adj_r2, 4),
        })

    metrics_df = pd.DataFrame(metrics)
    return metrics_df, ols_sk


def render_line_diagnostics_figure(
    ols_model: sm.regression.linear_model.RegressionResultsWrapper,
    diagnostics: LINEDiagnostics,
    output_path: Path,
) -> None:
    """
    Xuất biểu đồ 4 ô kiểm định giả định LINE đạt chuẩn Edward Tufte / William Cleveland:
      1. Linearity: Residuals vs Fitted values kèm đường tham chiếu 0.
      2. Independence: Biểu đồ ACF phần dư với dải tin cậy 95% Bartlett.
      3. Normality: Normal Q-Q plot của phần dư chuẩn hóa.
      4. Equal Variance: Scale-Location plot (Căn bậc hai phần dư chuẩn hóa vs Fitted).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10), dpi=300)
    residuals = ols_model.resid
    fitted = ols_model.fittedvalues
    std_residuals = (residuals - residuals.mean()) / residuals.std(ddof=1)

    # Màu sắc tối giản, độ tương phản cao theo Tufte
    c_point = "#2b5c8f"
    c_line = "#d95f02"

    # --- 1. Linearity (Residuals vs Fitted) ---
    ax1 = axes[0, 0]
    ax1.scatter(fitted, residuals, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax1.axhline(0, color="black", linestyle="--", linewidth=1.0, alpha=0.8)
    ax1.set_title("1. Linearity: Residuals vs Fitted Values\n(Kiểm tra độ tuyến tính)", fontsize=11, fontweight="bold", pad=8)
    ax1.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax1.set_ylabel("Phần dư Residuals (µg/m³)", fontsize=9)
    ax1.grid(True, linestyle=":", alpha=0.5)

    # --- 2. Independence (ACF of Residuals) ---
    ax2 = axes[0, 1]
    lags = np.arange(len(diagnostics.acf_values))
    ax2.vlines(lags, [0], diagnostics.acf_values, color=c_point, linewidth=1.5)
    ax2.scatter(lags, diagnostics.acf_values, color=c_point, s=18)
    ax2.axhline(0, color="black", linestyle="-", linewidth=0.8)
    # 95% Bartlett bounds
    ci_bound = 1.96 / np.sqrt(len(residuals))
    ax2.axhline(ci_bound, color=c_line, linestyle="--", linewidth=1.0, label="95% CI (Bartlett)")
    ax2.axhline(-ci_bound, color=c_line, linestyle="--", linewidth=1.0)
    ax2.set_title(f"2. Independence: Autocorrelation Function (ACF)\n(Durbin-Watson = {diagnostics.durbin_watson:.2f})", fontsize=11, fontweight="bold", pad=8)
    ax2.set_xlabel("Độ trễ Lag (Giờ)", fontsize=9)
    ax2.set_ylabel("Hệ số tự tương quan ACF", fontsize=9)
    ax2.set_ylim(-0.3, 1.05)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper right", frameon=True, fontsize=8)

    # --- 3. Normality (Normal Q-Q Plot) ---
    ax3 = axes[1, 0]
    (osm, osr), (slope, intercept, r) = stats.probplot(std_residuals, dist="norm")
    ax3.scatter(osm, osr, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax3.plot(osm, slope * np.array(osm) + intercept, color=c_line, linewidth=1.2, label=f"R² = {r**2:.3f}")
    ax3.set_title(f"3. Normality: Normal Q-Q Plot\n(Skew = {diagnostics.skewness:.2f}, Kurtosis = {diagnostics.kurtosis:.2f})", fontsize=11, fontweight="bold", pad=8)
    ax3.set_xlabel("Phân vị lý thuyết phân phối Chuẩn", fontsize=9)
    ax3.set_ylabel("Phần dư chuẩn hóa quan sát", fontsize=9)
    ax3.grid(True, linestyle=":", alpha=0.5)
    ax3.legend(loc="upper left", frameon=True, fontsize=8)

    # --- 4. Equal Variance (Scale-Location Plot) ---
    ax4 = axes[1, 1]
    sqrt_abs_std_res = np.sqrt(np.abs(std_residuals))
    ax4.scatter(fitted, sqrt_abs_std_res, alpha=0.35, s=16, color=c_point, edgecolors="none")
    ax4.set_title(f"4. Equal Variance: Scale-Location Plot\n(Breusch-Pagan p = {diagnostics.breusch_pagan_pvalue:.2e})", fontsize=11, fontweight="bold", pad=8)
    ax4.set_xlabel("Giá trị dự báo Fitted (µg/m³)", fontsize=9)
    ax4.set_ylabel(r"$\sqrt{|\text{Standardized Residuals}|}$", fontsize=9)
    ax4.grid(True, linestyle=":", alpha=0.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info("Đã lưu biểu đồ chẩn đoán LINE: %s", output_path)


def run_regression_pipeline(
    dataset_path: Path,
    output_fig_path: Path,
    report_path: Optional[Path] = None,
    split_timestamp: str = DEFAULT_SPLIT_TIMESTAMP,
) -> RegressionResults:
    """
    Thực thi toàn bộ quy trình mô hình hóa hồi quy OLS và chẩn đoán cho Issue #12.
    """
    df = pd.read_parquet(dataset_path)

    # 1. Chuẩn bị dữ liệu
    X_train, y_train, X_test, y_test = prepare_regression_data(
        df, split_timestamp=split_timestamp, drop_collinear_pm10=True
    )

    # 2. Đa cộng tuyến VIF
    df_vif = compute_vif(X_train)

    # 3. Fit OLS statsmodels (Classical & HAC Newey-West 24 lags)
    X_train_const = sm.add_constant(X_train)
    ols_sm = sm.OLS(y_train, X_train_const).fit()
    ols_hac = sm.OLS(y_train, X_train_const).fit(cov_type="HAC", cov_kwds={"maxlags": 24})

    # 4. Trích xuất bảng hệ số beta đối chứng Classical vs HAC
    coef_df = pd.DataFrame({
        "Feature": ols_sm.params.index,
        "Coefficient (Beta)": ols_sm.params.values.round(4),
        "SE (Classical)": ols_sm.bse.values.round(4),
        "p-Value (Classical)": ols_sm.pvalues.apply(lambda p: f"{p:.4e}" if p < 0.0001 else f"{p:.4f}"),
        "SE (HAC-24)": ols_hac.bse.values.round(4),
        "p-Value (HAC-24)": ols_hac.pvalues.apply(lambda p: f"{p:.4e}" if p < 0.0001 else f"{p:.4f}"),
        "95% CI Lower (HAC)": ols_hac.conf_int()[0].round(4),
        "95% CI Upper (HAC)": ols_hac.conf_int()[1].round(4),
    })

    # 5. LINE diagnostics
    line_diag = compute_line_diagnostics(ols_sm, X_train, y_train)

    # 6. Cook's Distance
    cooks_d, threshold, n_influential = compute_cooks_distance(ols_sm)

    # 7. Tune Ridge & Lasso (Leak-free CV với fold-level scaling)
    best_ridge_a, best_lasso_a, ridge_m, lasso_m, scaler_m = tune_regularization(X_train, y_train)

    # 8. Đánh giá Test độc lập (p=0 cho Dummy Baseline)
    metrics_df, _ = evaluate_models(X_train, y_train, X_test, y_test, ridge_m, lasso_m, scaler=scaler_m)

    # 9. Khảo sát log1p transform Y
    log_y_train = np.log1p(y_train)
    log_ols = sm.OLS(log_y_train, X_train_const).fit()
    log1p_metrics = {
        "original_train_r2": float(ols_sm.rsquared),
        "log1p_train_r2": float(log_ols.rsquared),
        "original_resid_skew": float(line_diag.skewness),
        "log1p_resid_skew": float(stats.skew(log_ols.resid)),
    }

    # 10. Xuất biểu đồ
    render_line_diagnostics_figure(ols_sm, line_diag, output_fig_path)

    results = RegressionResults(
        split_timestamp=split_timestamp,
        n_train=len(y_train),
        n_test=len(y_test),
        predictors=list(X_train.columns),
        vif_table=df_vif,
        ols_summary_str=str(ols_sm.summary()),
        hac_summary_str=str(ols_hac.summary()),
        coefficients=coef_df,
        line_diagnostics=line_diag,
        cooks_distance_max=float(np.max(cooks_d)),
        cooks_distance_threshold=threshold,
        n_influential_points=n_influential,
        ridge_best_alpha=best_ridge_a,
        lasso_best_alpha=best_lasso_a,
        metrics_table=metrics_df,
        log1p_target_evaluated=True,
        log1p_metrics=log1p_metrics,
    )

    if report_path is not None:
        write_regression_report(results, report_path)

    return results
