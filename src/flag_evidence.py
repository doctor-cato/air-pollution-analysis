"""
Issue #38 — Bằng chứng định lượng cho cờ chẩn đoán `is_high_humidity_fog`.

VÌ SAO CÓ MODULE NÀY
--------------------
`NON_PREDICTIVE_FLAGS` trong `src/cleaning_pipeline.py` loại `is_high_humidity_fog`
khỏi tập đặc trưng **mặc định** với hai lý do tách bạch, không được gộp:

  1. **Chưa có bằng chứng về giá trị dự báo MARGINAL** — tương quan và trung bình
     hai nhóm đều gần 0.
  2. **Cờ CÓ tương tác thật với MÙA** — hiệu ứng đổi dấu giữa các mùa, nên
     `corr ≈ 0` là hệ quả của việc trung bình qua các mùa, KHÔNG phải bằng
     chứng "không có quan hệ".

Trước Issue #38, cụm số `F = 16,78` / `p = 7,4·10⁻¹¹` chỉ tồn tại dưới dạng
comment và chuỗi hằng ở 6 chỗ — **không chỗ nào trong repo thực sự tính ra nó**.
Module này là **một chỗ duy nhất** sinh ra các con số đó:

  * `scripts/verify_claims.py` gọi `fog_flag_evidence()` để kiểm chứng (VERIFIED /
    MISMATCH) — không còn so chuỗi văn bản.
  * `scripts/build_progress_report.py` gọi `format_evidence_sentence()` để **sinh
    ra** câu trong báo cáo `.docx` từ kết quả thật.
  * `tests/test_flag_evidence.py` kiểm **hành vi** (F, p, df, chênh lệch theo mùa,
    xử lý thiếu cột / thiếu nhóm), không kiểm tra chuỗi `F = 16,78` trong source.

ĐỊNH NGHĨA ĐÓNG BĂNG TẠI ĐÂY (không suy diễn lúc chạy)
-------------------------------------------------------
1. **Tập quan sát.** Đọc `data/interim/air_quality_canonical.parquet` và
   `weather_canonical.parquet`, chạy lại đúng làm sạch tất định của Issue #6
   (`clean_weather` → `clean_air_quality`) rồi ghép bằng `merge_air_weather()`
   của Issue #7. Chỉ giữ dòng có **cả** `pm25` và `relative_humidity` khác NaN.
   → 7.495 dòng. (Cột `relative_humidity` nằm ở tập KHÍ TƯỢNG, không nằm ở tập
   ô nhiễm — nên phải ghép, không thể đọc một tệp.)
2. **Mùa.** Gán theo tháng: 12–2 = `Dong`, 3–5 = `Xuan`, 6–8 = `He`, 9–11 = `Thu`.
   Nhãn ASCII cố ý: patsy sắp xếp mức theo chuỗi, `Dong` là mức tham chiếu
   (mức đầu tiên sau khi sort) → hệ số `C(fog)[T.1]` chính là hiệu ứng của Đông.
3. **Mô hình.** OLS `pm25 ~ C(fog) + C(season) + C(fog):C(season)` (statsmodels).
4. **Kiểm định.** F-test **đồng thời** ba hệ số tương tác
   (`C(fog)[T.1]:C(season)[T.He]`, `[T.Thu]`, `[T.Xuan]`) bằng
   `results.f_test(R)` → F với `df_num = 3`, `df_denom = n - 8`.
5. **Chênh lệch theo mùa.** Ba cách nhìn, cùng điểm ước lượng nhưng khác khoảng tin
   cậy — vì tài liệu trích lẫn lộn nhiều định nghĩa:
   * `raw_mean_difference` — hiệu của hai trung bình nhóm thô;
   * `model_contrast` — tương phản tuyến tính trên mô hình (hệ số + tương tác),
     khoảng tin cậy 95% theo phân phối t (đây là nơi lấy `p = 0,024` của Đông);
   * `welch` — kiểm định t hai mẫu Welch trên trung bình thô, kèm CI 95% (đây là
     nơi lấy các CI `[−10,44; −7,38]` mà tài liệu trích).

CHỖ NÀO CHƯA ĐÓNG BĂNG — MUTUAL INFORMATION
-------------------------------------------
`MI = 0,0024` **không** được tái lập ở đây như một con số đã xác minh, vì định
nghĩa của nó không được đóng băng ở bất kỳ đâu trong repo. Cùng một bộ dữ liệu cho
ra 0,0024 với `mutual_info_score(pm25, cờ)` khi chia `pm25` thành **7, 8 hoặc 10**
nhóm phân vị — tức con số trùng hợp chứ không phải một định nghĩa duy nhất — và
0,0081 với `mutual_info_regression` (ước lượng liên tục, tiêu chuẩn của scikit-learn),
0,0105 với `mutual_info_classif` trên cùng 8 nhóm. Vì vậy `MI` được **ghi nhận là
UNVERIFIED** (`scripts/verify_claims.py`), còn `mutual_information_variants()`
chỉ in ra để người đọc tự định nghĩa. Không dùng `MI` làm căn cứ kết luận.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Hằng số quy ước — nguồn sự thật duy nhất cho Issue #38
# ---------------------------------------------------------------------------

TIMESTAMP_COLUMN = "timestamp"
TARGET_COLUMN = "pm25"
HUMIDITY_COLUMN = "relative_humidity"
FLAG_COLUMN = "is_high_humidity_fog"
SEASON_COLUMN = "season"

#: Nhãn mùa dùng **trong công thức** (ASCII không dấu). Xem `SEASON_MONTHS`.
SEASON_DONG = "Dong"
SEASON_XUAN = "Xuan"
SEASON_HE = "He"
SEASON_THU = "Thu"

#: Tháng (1–12) → mùa. Quy ước khí tượng Việt Nam: Đông 12–2, Xuân 3–5,
#: Hè 6–8, Thu 9–11.
SEASON_MONTHS: Dict[int, str] = {
    12: SEASON_DONG, 1: SEASON_DONG, 2: SEASON_DONG,
    3: SEASON_XUAN, 4: SEASON_XUAN, 5: SEASON_XUAN,
    6: SEASON_HE, 7: SEASON_HE, 8: SEASON_HE,
    9: SEASON_THU, 10: SEASON_THU, 11: SEASON_THU,
}

#: Nhãn tiếng Việt để hiển thị. Mức tham chiếu của mô hình là `Dong`.
SEASON_LABELS_VI: Dict[str, str] = {
    SEASON_DONG: "Đông",
    SEASON_XUAN: "Xuân",
    SEASON_HE: "Hè",
    SEASON_THU: "Thu",
}

#: Thứ tự hiển thị (theo mùa, không theo alphabet).
SEASON_DISPLAY_ORDER: Tuple[str, ...] = (
    SEASON_DONG, SEASON_XUAN, SEASON_HE, SEASON_THU,
)

#: Công thức OLS đóng băng — in ra báo cáo để người đọc kiểm chứng lại.
INTERACTION_FORMULA = f"{TARGET_COLUMN} ~ C(fog) + C(season) + C(fog):C(season)"

#: Công thức mô hình null (không tương tác) — in ra báo cáo để người đọc thấy
#: giả thuyết mà F-test đang bác bỏ.
REDUCED_FORMULA = f"{TARGET_COLUMN} ~ C(fog) + C(season)"

#: Tên cột sau khi `add_season()` — `fog` là bí danh ngắn cho cột cờ.
FOG_ALIAS = "fog"

#: Tập mẫu tối thiểu để còn ý nghĩa thống kê (mọi ô fog × mùa đều cần ≥ 2).
MIN_CELL_OBSERVATIONS = 2

#: Số nhóm phân vị khi in phương án MI (MI **không** phải claim đã xác minh).
MI_BIN_VARIANTS: Tuple[int, ...] = (7, 8, 10)

#: Lý do MI bị gắn UNVERIFIED — dùng nguyên văn trong `verify_claims.py`.
MUTUAL_INFORMATION_UNVERIFIED_REASON = (
    "MI = 0,0024 không đóng băng được định nghĩa: mutual_info_score(pm25, cờ) cho "
    "0,0024 khi chia pm25 thành 7, 8 HOẶC 10 nhóm phân vị (trùng hợp), còn "
    "mutual_info_regression (liên tục) cho 0,0081 và mutual_info_classif trên "
    "cùng 8 nhóm cho 0,0105. Không có định nghĩa MI nào được đóng băng trong repo "
    "nên không được coi 0,0024 là đã xác minh."
)


# ---------------------------------------------------------------------------
# Dựng khung phân tích
# ---------------------------------------------------------------------------


def add_season(
    df: pd.DataFrame,
    timestamp_col: str = TIMESTAMP_COLUMN,
) -> pd.DataFrame:
    """
    Gán cột mùa theo tháng.

    Raises
    ------
    KeyError
        Thiếu cột thời gian.
    ValueError
        Có timestamp không parse được (NaT), vì khi đó không xác định được mùa
        và dòng đó sẽ bị rơi khỏi mọi phép so sánh theo mùa một cách âm thầm.
    """
    if timestamp_col not in df.columns:
        raise KeyError(
            f"Không có cột thời gian '{timestamp_col}'. "
            f"Cột hiện có: {list(df.columns)}"
        )
    ts = pd.to_datetime(df[timestamp_col])
    n_nat = int(ts.isna().sum())
    if n_nat:
        raise ValueError(
            f"Cột '{timestamp_col}' có {n_nat} giá trị NaT — không gán được mùa. "
            "Xử lý timestamp trước khi gọi add_season()."
        )

    out = df.copy()
    out[SEASON_COLUMN] = ts.dt.month.map(SEASON_MONTHS)
    if out[SEASON_COLUMN].isna().any():  # pragma: no cover - month luôn trong 1..12
        raise ValueError(
            "Có tháng không nằm trong 1..12 nên chưa gán được mùa — kiểm tra lại "
            "bảng `SEASON_MONTHS`."
        )
    out[FOG_ALIAS] = out[FLAG_COLUMN].astype("int64")
    return out


def build_analysis_frame(
    air_interim_path: Path = Path("data/interim/air_quality_canonical.parquet"),
    weather_interim_path: Path = Path("data/interim/weather_canonical.parquet"),
) -> pd.DataFrame:
    """
    Dựng khung phân tích cho cờ sương mù từ hai tệp Canonical ở `data/interim/`.

    Chạy lại **đúng** làm sạch tất định của Issue #6 rồi ghép bằng
    `merge_air_weather()` của Issue #7. Hàm này **chỉ đọc**, không ghi gì xuống
    `data/`.

    Raises
    ------
    FileNotFoundError
        Thiếu một trong hai tệp Canonical.
    """
    from src.cleaning import clean_air_quality, clean_weather
    from src.cleaning_pipeline import merge_air_weather

    air_path = Path(air_interim_path)
    weather_path = Path(weather_interim_path)
    for path in (air_path, weather_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {path}. Chạy `python scripts/fetch_dataset.py` "
                "để tải dữ liệu gốc rồi chạy lại notebook 01."
            )

    df_air = pd.read_parquet(air_path)
    df_weather = pd.read_parquet(weather_path)

    # Thứ tự có ý nghĩa: khí tượng phải sạch TRƯỚC vì `clean_air_quality` tra cứu
    # độ ẩm bằng LEFT JOIN theo timestamp.
    df_weather_clean, _ = clean_weather(df_weather)
    df_air_clean, _ = clean_air_quality(df_air, df_weather_clean)

    return add_season(merge_air_weather(df_air_clean, df_weather_clean))


def analysis_frame_from(dataset: pd.DataFrame) -> pd.DataFrame:
    """
    Dựng khung phân tích từ một frame đã đóng băng (ví dụ
    `data/processed/air_pollution_final.parquet`).

    Dùng khi frame đã có sẵn cột cờ và cột khí tượng — tiết kiệm việc chạy lại
    làm sạch tất định. Raises `KeyError` nếu thiếu cột.
    """
    return add_season(dataset)


# ---------------------------------------------------------------------------
# Tiền kiểm tra
# ---------------------------------------------------------------------------


def _require_analysis_columns(df: pd.DataFrame) -> None:
    required = [TIMESTAMP_COLUMN, TARGET_COLUMN, HUMIDITY_COLUMN, FLAG_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(
            f"Khung phân tích thiếu cột {missing}. Cột hiện có: "
            f"{list(df.columns)}. Cần cả `pm25`, `relative_humidity` và cờ "
            "`is_high_humidity_fog` — cờ này do Issue #6 sinh ra, không có sẵn "
            "trong tệp Canonical gốc."
        )


def select_analysis_sample(df: pd.DataFrame) -> pd.DataFrame:
    """
    Chọn tập quan sát dùng cho mọi phép đo: dòng có **cả** `pm25` và
    `relative_humidity` khác NaN, cộng cột `season`/`fog`.

    `add_season()` luôn được gọi lại (và cố ý ghi đè mọi cột `season`/`fog` sẵn
    có) để mùa **luôn** được suy ra từ timestamp — nếu nhận cột mùa bên ngoài thì
    định nghĩa tập mẫu sẽ mơ hồ.

    Raises
    ------
    ValueError
        Không còn dòng nào, hoặc một ô `fog × mùa` không đủ quan sát để ước
        lượng tương tác.
    """
    _require_analysis_columns(df)
    frame = add_season(df)

    sample = frame[
        [TARGET_COLUMN, HUMIDITY_COLUMN, SEASON_COLUMN, FOG_ALIAS]
    ].dropna()

    if sample.empty:
        raise ValueError(
            "Không còn dòng nào có cả `pm25` và `relative_humidity`. Kiểm tra lại "
            "tập dữ liệu đầu vào."
        )

    counts = sample.groupby([SEASON_COLUMN, FOG_ALIAS]).size()
    thin = {
        f"{SEASON_LABELS_VI.get(str(s), s)} × fog={int(f)}": int(n)
        for (s, f), n in counts.items()
        if int(n) < MIN_CELL_OBSERVATIONS
    }
    if thin:
        raise ValueError(
            f"Các ô fog × mùa sau có dưới {MIN_CELL_OBSERVATIONS} quan sát: {thin}. "
            "Mô hình tương tác không ước lượng được — không được âm thầm bỏ qua ô."
        )
    return sample


# ---------------------------------------------------------------------------
# Vì sao dùng ASCII trong tên biến (`fog`)?
# ---------------------------------------------------------------------------


def _fit_interaction_model(sample: pd.DataFrame) -> Any:
    """Fit OLS `pm25 ~ C(fog) + C(season) + C(fog):C(season)`."""
    import statsmodels.formula.api as smf

    return smf.ols(INTERACTION_FORMULA, data=sample).fit()


def _interaction_terms(results: Any) -> List[str]:
    return [name for name in results.params.index if ":" in name]


def _contrast(results: Any, names: List[str], weights: Mapping[str, float]) -> Dict[str, float]:
    """Tương phản tuyến tính + CI 95% theo phân phối t."""
    vector = np.zeros(len(names))
    for name, weight in weights.items():
        vector[names.index(name)] = weight
    test = results.t_test(vector)
    ci = np.asarray(test.conf_int()).ravel()
    return {
        "estimate": float(np.asarray(test.effect).ravel()[0]),
        "std_error": float(np.ravel(test.sd)[0]),
        "p_value": float(np.ravel(test.pvalue)[0]),
        "ci_low": float(ci[0]),
        "ci_high": float(ci[1]),
    }


def mutual_information_variants(sample: pd.DataFrame) -> Dict[str, float]:
    """
    In ra **mọi** phương án MI cùng cho một mẫu — vì MI phụ thuộc ước lượng.

    KHÔNG dùng hàm này để "xác minh" `MI = 0,0024`: xem
    `MUTUAL_INFORMATION_UNVERIFIED_REASON`.
    """
    from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
    from sklearn.metrics import mutual_info_score

    y = sample[TARGET_COLUMN].to_numpy()
    fog = sample[FOG_ALIAS].to_numpy()
    out: Dict[str, float] = {}
    for bins in MI_BIN_VARIANTS:
        y_binned = pd.qcut(y, bins, labels=False, duplicates="drop")
        out[f"mutual_info_score(pm25_{bins}nhom, fog)"] = float(
            mutual_info_score(y_binned, fog)
        )
        out[f"mutual_info_classif(pm25_{bins}nhom, fog)"] = float(
            mutual_info_classif(fog.reshape(-1, 1), y_binned, random_state=42)[0]
        )
    out["mutual_info_regression(fog, pm25)"] = float(
        mutual_info_regression(fog.reshape(-1, 1), y, random_state=42)[0]
    )
    return out


# ---------------------------------------------------------------------------
# Phép tính chính
# ---------------------------------------------------------------------------


def fog_flag_evidence(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Tính TOÀN BỘ bằng chứng định lượng cho `is_high_humidity_fog`.

    Parameters
    ----------
    df : pd.DataFrame
        Frame đã có `timestamp`, `pm25`, `relative_humidity`,
        `is_high_humidity_fog`. Dùng `build_analysis_frame()` để dựng từ
        `data/interim/`.

    Returns
    -------
    dict
        Xem `flag_evidence` trong test. Không trả về con số nào là "kết luận" —
        đây là **số đo**, việc diễn giải thuộc tài liệu.

    Raises
    ------
    KeyError
        Thiếu cột bắt buộc.
    ValueError
        Không còn dòng dùng được, hoặc một ô `fog × mùa` quá mỏng.
    """
    sample = select_analysis_sample(df)

    target = sample[TARGET_COLUMN]
    humidity = sample[HUMIDITY_COLUMN]
    fog = sample[FOG_ALIAS]

    corr = float(target.corr(humidity))

    by_flag = target.groupby(fog)
    mean_by_flag = {int(k): float(v) for k, v in by_flag.mean().items()}
    n_by_flag = {int(k): int(v) for k, v in by_flag.size().items()}

    full = _fit_interaction_model(sample)
    names = list(full.params.index)
    terms = _interaction_terms(full)

    # F-test ĐỒNG THỜI các hệ số tương tác (null: cả 3 tương tác = 0).
    f_test = full.f_test(terms)
    f_statistic = float(np.ravel(f_test.fvalue)[0])
    f_p_value = float(np.ravel(f_test.pvalue)[0])
    f_df_num = int(np.ravel(f_test.df_num)[0])
    f_df_denom = float(np.ravel(f_test.df_denom)[0])

    # Hiệu ứng của cờ trong TỪNG mùa, theo mô hình (hệ số chính + tương tác).
    # Tên hệ số chính lấy TỪ `results.params.index` chứ không viết cứng, để đổi
    # cách mã hoá cờ (vd 0/1 → True/False) thì phép tính báo lỗi rõ thay vì âm
    # thầm trả về sai.
    main_terms = [n for n in names if n.startswith("C(fog)[")]
    if not main_terms:
        raise ValueError(
            f"Mô hình không sinh hệ số chính cho cờ — không xác định được hiệu ứng "
            f"cờ theo mùa. Tên tham số: {names}"
        )
    main = main_terms[0]
    season_effects: Dict[str, Dict[str, float]] = {}
    for season in SEASON_DISPLAY_ORDER:
        weights: Dict[str, float] = {main: 1.0}
        term = f"{main}:C(season)[T.{season}]"
        if term in names:
            weights[term] = 1.0
        season_effects[season] = _contrast(full, names, weights)

    # Chênh lệch trung bình THÔ + kiểm định Welch (khoảng tin cậy tài liệu).
    raw_difference: Dict[str, float] = {}
    welch: Dict[str, Dict[str, float]] = {}
    for season in SEASON_DISPLAY_ORDER:
        part = sample[sample[SEASON_COLUMN] == season]
        flagged = part[part[FOG_ALIAS] == 1][TARGET_COLUMN]
        unflagged = part[part[FOG_ALIAS] == 0][TARGET_COLUMN]
        raw_difference[season] = float(flagged.mean() - unflagged.mean())
        result = stats.ttest_ind(flagged, unflagged, equal_var=False)
        ci = result.confidence_interval()
        welch[season] = {
            "difference": raw_difference[season],
            "ci_low": float(ci.low),
            "ci_high": float(ci.high),
            "p_value": float(result.pvalue),
            "n_flagged": int(flagged.size),
            "n_unflagged": int(unflagged.size),
        }

    # Khác biệt kép: Đông so với (Xuân + Hè) gộp chung.
    xuan_he = sample[sample[SEASON_COLUMN].isin([SEASON_XUAN, SEASON_HE])]
    pooled = float(
        xuan_he[xuan_he[FOG_ALIAS] == 1][TARGET_COLUMN].mean()
        - xuan_he[xuan_he[FOG_ALIAS] == 0][TARGET_COLUMN].mean()
    )
    double_difference = raw_difference[SEASON_DONG] - pooled

    cell_counts = {
        f"{SEASON_LABELS_VI[s]} × fog={f}": int(n)
        for (s, f), n in sample.groupby([SEASON_COLUMN, FOG_ALIAS]).size().items()
    }

    return {
        "n_rows_input": int(len(df)),
        "n_rows_used": int(len(sample)),
        "season_counts": {
            SEASON_LABELS_VI[s]: int((sample[SEASON_COLUMN] == s).sum())
            for s in SEASON_DISPLAY_ORDER
        },
        "cell_counts": cell_counts,
        "marginal": {
            "corr_pm25_rh": corr,
            "mean_pm25_by_flag": mean_by_flag,
            "n_pm25_by_flag": n_by_flag,
            "mutual_information_variants": mutual_information_variants(sample),
            "mutual_information_verified": False,
        },
        "seasonal": {
            "formula": INTERACTION_FORMULA,
            "reduced_formula": REDUCED_FORMULA,
            "n_obs": int(full.nobs),
            "r_squared": float(full.rsquared),
            "f_statistic": f_statistic,
            "f_p_value": f_p_value,
            "f_df_num": f_df_num,
            "f_df_denom": f_df_denom,
            "reference_season": SEASON_LABELS_VI[SEASON_DONG],
            "interaction_terms": list(terms),
            "interaction_coefficients": {
                t: {
                    "coef": float(full.params[t]),
                    "p_value": float(full.pvalues[t]),
                }
                for t in terms
            },
            "raw_mean_difference": {
                SEASON_LABELS_VI[s]: raw_difference[s] for s in SEASON_DISPLAY_ORDER
            },
            "model_contrast": {
                SEASON_LABELS_VI[s]: season_effects[s] for s in SEASON_DISPLAY_ORDER
            },
            "welch": {
                SEASON_LABELS_VI[s]: welch[s] for s in SEASON_DISPLAY_ORDER
            },
            "double_difference_dong_vs_xuan_he": double_difference,
            "pooled_xuan_he_difference": pooled,
        },
    }


# ---------------------------------------------------------------------------
# Sinh câu chữ cho log / báo cáo — số liệu lấy từ kết quả, không hard-code
# ---------------------------------------------------------------------------


def _vi(value: float, digits: int = 2) -> str:
    """Định dạng số kiểu Việt Nam (dấu phẩy thập phân)."""
    return f"{value:.{digits}f}".replace(".", ",")


def format_number_vi(value: float, digits: int = 2) -> str:
    """
    Số thập phân dấu phẩy — dùng chung để báo cáo và log không lệch nhau.

    Dấu trừ dùng ``−`` (U+2212) cho khớp với cách viết trong tài liệu.
    """
    return _vi(value, digits).replace("-", "−")


def format_int_vi(value: int) -> str:
    """Số nguyên có dấu chấm phân tách nghìn kiểu Việt Nam: ``2.384``."""
    return f"{int(value):,}".replace(",", ".")


def format_signed_vi(value: float, digits: int = 2) -> str:
    """Số có dấu ``+``/``−`` — dùng cho chênh lệch theo mùa."""
    return ("+" if value >= 0 else "−") + _vi(abs(value), digits)


_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def format_scientific_vi(value: float, digits: int = 1) -> str:
    """Định dạng số cực nhỏ kiểu Việt Nam: ``7,4·10⁻¹¹``."""
    mantissa, exponent = f"{value:.{digits}e}".split("e")
    superscript = exponent.translate(_SUPERSCRIPT)
    return f"{mantissa.replace('.', ',')}·10{superscript}"


def format_evidence_sentence(evidence: Mapping[str, Any]) -> str:
    """
    Sinh câu mô tả bằng chứng cờ `is_high_humidity_fog` từ kết quả.

    Mọi con số trong câu trả về đều lấy từ `evidence` — gọi lại hàm này sau khi
    đổi dữ liệu sẽ ra câu khác, không thể "trượt" về giá trị cũ. Đây là nguồn
    duy nhất để sinh văn bản: `scripts/build_progress_report.py` gọi hàm này.

    Raises
    ------
    KeyError
        Thiếu `evidence` không phải kết quả của `fog_flag_evidence()`.
    """
    marginal = evidence["marginal"]
    seasonal = evidence["seasonal"]
    raw = seasonal["raw_mean_difference"]
    welch = seasonal["welch"]
    dong = SEASON_LABELS_VI[SEASON_DONG]

    return (
        "Tương quan marginal corr(pm25, RH) = "
        f"{format_number_vi(marginal['corr_pm25_rh'], 4)} và PM2.5 trung bình "
        f"ở nhóm có cờ {format_number_vi(marginal['mean_pm25_by_flag'][1])} "
        f"(n = {format_int_vi(marginal['n_pm25_by_flag'][1])}) thấp hơn nhóm không cờ "
        f"{format_number_vi(marginal['mean_pm25_by_flag'][0])} "
        f"(n = {format_int_vi(marginal['n_pm25_by_flag'][0])}) trên "
        f"{format_int_vi(evidence['n_rows_used'])} dòng có cả pm25 và RH "
        "— chỉ chứng minh chưa có bằng chứng ở mức cộng dồn "
        "(mutual information chưa xác minh: định nghĩa ước lượng MI chưa được "
        "đóng băng nên không dùng làm căn cứ). "
        "Tách theo mùa thì dấu đảo chiều: "
        f"Đông {format_signed_vi(raw[dong])} µg/m³ "
        f"(p = {format_number_vi(seasonal['model_contrast'][dong]['p_value'], 3)} theo mô hình, "
        f"CI Welch [{format_number_vi(welch[dong]['ci_low'])}; "
        f"{format_number_vi(welch[dong]['ci_high'])}]), "
        f"Xuân {format_signed_vi(raw[SEASON_LABELS_VI[SEASON_XUAN]])} "
        f"(CI [{format_number_vi(welch[SEASON_LABELS_VI[SEASON_XUAN]]['ci_low'])}; "
        f"{format_number_vi(welch[SEASON_LABELS_VI[SEASON_XUAN]]['ci_high'])}]), "
        f"hè {format_signed_vi(raw[SEASON_LABELS_VI[SEASON_HE]])}, "
        f"Thu {format_signed_vi(raw[SEASON_LABELS_VI[SEASON_THU]])}. "
        f"Hồi quy {seasonal['formula']} cho "
        f"F({int(seasonal['f_df_num'])}, {int(seasonal['f_df_denom'])}) = "
        f"{format_number_vi(seasonal['f_statistic'])}, "
        f"p = {format_scientific_vi(seasonal['f_p_value'])}; "
        "khác biệt kép Đông so với Xuân+hè là "
        f"{format_signed_vi(seasonal['double_difference_dong_vs_xuan_he'])} µg/m³. "
        "Tức corr gần 0 là hệ quả của việc trung bình qua các mùa nơi "
        "tác dụng ngược nhau triệt tiêu, KHÔNG phải bằng chứng không "
        "có quan hệ. Khai thác được cần dạng mô hình tương tác "
        "fog × mùa — thuộc phạm vi Issue #8."
    )


__all__ = [
    "FLAG_COLUMN",
    "HUMIDITY_COLUMN",
    "INTERACTION_FORMULA",
    "REDUCED_FORMULA",
    "MUTUAL_INFORMATION_UNVERIFIED_REASON",
    "SEASON_COLUMN",
    "SEASON_DISPLAY_ORDER",
    "SEASON_LABELS_VI",
    "SEASON_MONTHS",
    "TARGET_COLUMN",
    "add_season",
    "analysis_frame_from",
    "build_analysis_frame",
    "fog_flag_evidence",
    "format_evidence_sentence",
    "format_int_vi",
    "format_number_vi",
    "format_scientific_vi",
    "format_signed_vi",
    "mutual_information_variants",
    "select_analysis_sample",
]
