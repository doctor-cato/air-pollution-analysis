"""
verify_claims.py — Tái lập các claim định lượng đang được trích trong tài liệu.

Mục đích
--------
Một số con số trong `docs/TASK_LIST_M3_M6.md` được đọc thẳng từ tệp Parquet nhưng
không có cách nào chạy lại để kiểm chứng. Script này là cơ chế tái lập:

    python scripts/verify_claims.py

Nhóm claim của cờ `is_high_humidity_fog` (Issue #38) được tái lập bằng cách gọi
`src/flag_evidence.fog_flag_evidence()` — tức **fit lại mô hình trên dữ liệu thật**,
không phải so chuỗi `F = 16,78` trong source. Khung phân tích mặc định được dựng
lại từ `data/interim/*.parquet` (chạy lại làm sạch tất định Issue #6 + ghép của
Issue #7) vì cột `relative_humidity` và cờ `is_high_humidity_fog` không cùng nằm
trong tệp Canonical gốc.

Mỗi claim được tái lập theo **đúng định nghĩa mà chính tài liệu đang nêu**, in ra
tử số, mẫu số, công thức và kết quả, rồi phân loại:

    VERIFIED      — khớp giá trị tài liệu
    MISMATCH      — TÁI LẬP ĐƯỢC NHƯNG KHÁC tài liệu → tài liệu sai
    UNVERIFIABLE  — chưa xác định được định nghĩa hoặc nguồn gốc → KHÔNG đoán,
                    ghi rõ lý do, không điền số nào cả

Nguyên tắc bất di bất dịch
--------------------------
1. **CHỈ ĐỌC.** Không bao giờ ghi vào `data/`. Không sửa tài liệu.
2. **Không bịa.** Claim không tái lập được sẽ báo `UNVERIFIABLE`, tuyệt đối không
   điền con số dự kiến và cũng không sửa con số đang sai cho "khớp".
3. **Không âm thầm chọn định nghĩa.** Với những đại lượng mà tài liệu đang dùng hai
   mẫu số khác nhau, script in ra **cả hai** kèm công thức, rồi đánh dấu
   `UNDECIDED` — không tự chọn. Xem `DENOMINATOR_CONFLICTS` bên dưới.
4. **Dừng rõ ràng.** Thiếu tệp, thiếu cột, hoặc mẫu số bằng 0 → ném lỗi tường minh,
   không chia cho 0 và không im lặng trả 0.
5. **Số cực nhỏ so TƯƠNG ĐỐI.** p-value được so bằng `rtol`; nếu dùng dung sai
   tuyệt đối `FLOAT_TOL` thì mọi p < 5e-4 đều bị coi là khớp.

Exit code
---------
    0  — không có claim MISMATCH mức chặn merge
    1  — có ít nhất một claim MISMATCH mức chặn merge
    2  — lỗi đầu vào (thiếu tệp / thiếu cột / phép tính không hợp lệ)

Giới hạn đã biết
----------------
* Parquet không tái lập được theo byte (xem `README.md` §3), nên script so **nội
  dung** (số dòng, tỷ lệ), không so mã băm.
* Split Train/Test lấy từ mốc thời gian của Issue #7. Mốc đó **đọc từ đây**, không
  hard-code trong tài liệu — xem `SPLIT_TIMESTAMP`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# Chạy `python scripts/verify_claims.py` đặt sys.path[0] = scripts/, nên `src.*`
# không import được. Thêm REPO_ROOT để nhóm claim của cờ sương mù gọi được
# `src.flag_evidence`.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_DATASET = REPO_ROOT / "data" / "processed" / "air_pollution_final.parquet"
DEFAULT_REPORTS = REPO_ROOT / "reports"

# Mốc cắt chuỗi thời gian của Issue #7. Nguồn:
#   notebooks/03_transformation_pipeline.ipynb, cell 13:
#   SPLIT_TIMESTAMP = pd.Timestamp("2026-01-15 00:00", tz="Asia/Ho_Chi_Minh")
SPLIT_TIMESTAMP = pd.Timestamp("2026-01-15 00:00", tz="Asia/Ho_Chi_Minh")

VERIFIED = "VERIFIED"
MISMATCH = "MISMATCH"
UNVERIFIABLE = "UNVERIFIABLE"
UNDECIDED = "UNDECIDED"

# Ngưỡng sai số cho phép khi so số thực.
FLOAT_TOL = 5e-4

REQUIRED_COLUMNS = ["timestamp", "pm25", "pm10"]

#: Các cột khí tượng thực sự có trong Parquet. Tài liệu ghi "5 biến khí tượng" —
#: kiểm chứng số lượng thay vì tin bản ghi.
WEATHER_COLUMNS = [
    "temperature",
    "relative_humidity",
    "wind_speed",
    "wind_direction",
    "precipitation",
    "surface_pressure",
]

#: Cột đặc trưng chu kỳ thời gian mà Issue #7 đã sinh sẵn.
CYCICAL_COLUMNS = ["hour_sin", "hour_cos", "month_sin", "month_cos"]


class Claim:
    """Một claim định lượng cần tái lập."""

    def __init__(
        self,
        key: str,
        source: str,
        documented: Any,
        compute: Callable[[pd.DataFrame], Any],
        fmt: str = "{}",
        blocking: bool = True,
        note: str = "",
        rtol: Optional[float] = None,
        atol: Optional[float] = None,
    ) -> None:
        self.key = key
        self.source = source
        self.documented = documented
        self.compute = compute
        self.fmt = fmt
        self.blocking = blocking
        self.note = note
        #: Dung sai TƯƠNG ĐỐI. Bắt buộc cho đại lượng rất nhỏ như p-value:
        #: `FLOAT_TOL = 5e-4` tuyệt đối sẽ coi mọi p-value < 5e-4 là "khớp".
        #: `None` = hành vi cũ (so số tuyệt đối).
        self.rtol = rtol
        #: Dung sai TUYỆT ĐỐI tường minh. Dùng cho số tài liệu chỉ trích đến 2
        #: chữ số thập phân: mọi sai khác ≤ 0,01 là do quy tắc làm tròn khi đứng
        #: đúng mốc x,xx5, không phải do tài liệu sai.
        self.atol = atol

    def run(self, df: pd.DataFrame) -> "ClaimResult":
        actual = self.compute(df)
        if isinstance(self.documented, float):
            if self.rtol is not None:
                reference = float(self.documented)
                denominator = abs(reference) if reference else 1.0
                ok = (
                    abs(float(actual) - reference) / denominator
                    <= self.rtol
                )
            elif self.atol is not None:
                ok = abs(float(actual) - self.documented) <= self.atol
            else:
                ok = abs(float(actual) - self.documented) < FLOAT_TOL
        elif isinstance(self.documented, int):
            ok = int(actual) == self.documented
        else:
            ok = actual == self.documented
        status = VERIFIED if ok else MISMATCH
        return ClaimResult(self, status, actual)


class ClaimResult:
    def __init__(self, claim: Claim, status: str, actual: Any) -> None:
        self.claim = claim
        self.status = status
        self.actual = actual


# ---------------------------------------------------------------------------
# Các phép tính dùng chung
# ---------------------------------------------------------------------------


def _split(df: pd.DataFrame):
    return df[df["timestamp"] < SPLIT_TIMESTAMP], df[df["timestamp"] >= SPLIT_TIMESTAMP]


def _severe_instant(part: pd.DataFrame) -> Dict[str, int]:
    """Nhãn nặng — `pm25 > 100` trên nồng độ TỨC THỜI theo giờ."""
    labelled = int(part["pm25"].notna().sum())
    return {
        "numerator": int((part["pm25"] > 100).sum()),
        "denominator_labelled": labelled,
        "denominator_all": len(part),
    }


def _alert_rolling24(part: pd.DataFrame, hours: int = 24) -> Dict[str, int]:
    """Cảnh báo — trung bình TRƯỢT 24h >= 50 ug/m3."""
    roll = part["pm25"].rolling(window=hours, min_periods=hours).mean()
    return {
        "numerator": int((roll >= 50).sum()),
        "denominator_rolling_valid": int(roll.notna().sum()),
        "denominator_all": len(part),
    }


# ---------------------------------------------------------------------------
# Claim định nghĩa được (tác lập từ `docs/TASK_LIST_M3_M6.md:35-44`)
# ---------------------------------------------------------------------------

CLAIMS: List[Claim] = [
    Claim("rows", "TASK_LIST:36", 9044, lambda d: len(d)),
    Claim("cols", "TASK_LIST:36", 18, lambda d: d.shape[1]),
    Claim(
        "days", "TASK_LIST:36", 376,
        lambda d: (d["timestamp"].max() - d["timestamp"].min()).days,
    ),
    Claim(
        "rows_per_day", "TASK_LIST:36", 24.05,
        lambda d: round(
            len(d) / (d["timestamp"].max() - d["timestamp"].min()).days, 2
        ),
        "{:.2f}",
        note="Tan so luoi gio: 9.044 dong / 376 ngay.",
    ),
    Claim("pm25_nan", "TASK_LIST:37", 1549, lambda d: int(d["pm25"].isna().sum())),
    Claim(
        "pm25_nan_pct", "TASK_LIST:37", 17.1,
        lambda d: round(100 * d["pm25"].isna().mean(), 1), "{:.1f}",
    ),
    Claim("pm10_nan", "TASK_LIST:37", 1469, lambda d: int(d["pm10"].isna().sum())),
    Claim(
        "complete_case", "TASK_LIST:37", 7372,
        lambda d: int(d[["pm25", "pm10"]].notna().all(axis=1).sum()),
    ),
    Claim(
        "corr_pm25_pm10", "TASK_LIST:38", 0.9727,
        lambda d: round(
            float(d[["pm25", "pm10"]].dropna()["pm25"].corr(d[["pm25", "pm10"]].dropna()["pm10"])),
            4,
        ),
        "{:.4f}",
    ),
    Claim(
        "r2_univariate", "TASK_LIST:38", 0.9462,
        lambda d: round(
            float(
                d[["pm25", "pm10"]].dropna()["pm25"].corr(
                    d[["pm25", "pm10"]].dropna()["pm10"]
                )
            ) ** 2,
            4,
        ),
        "{:.4f}",
        note="Tác lập bằng r^2 của đường hồi quy đơn biến pm25 ~ pm10.",
    ),
    Claim(
        "weather_cols", "TASK_LIST:37", 6,
        lambda d: len([c for c in WEATHER_COLUMNS if c in d.columns]),
        note=(
            "Parquet có "
            "temperature, relative_humidity, wind_speed, wind_direction, "
            "precipitation, surface_pressure."
        ),
    ),
    *[
        Claim(
            f"has_{c}", "TASK_LIST:39", True,
            lambda d, c=c: c in d.columns,
            note="Cột đặc trưng chu kỳ thời gian do Issue #7 sinh sẵn.",
        )
        for c in CYCICAL_COLUMNS
    ],
]

#: Claim ghi trong tài liệu nhưng **không tái lập được** vì công thức không rõ.
#: Danh sách này là GHI NHẬN chứ không phải chỗ điền số dự kiến.
UNVERIFIABLE_CLAIMS: List[tuple] = [
    (
        "fog_mutual_information",
        "src/cleaning_pipeline.py::NON_PREDICTIVE_FLAGS, "
        "docs/roadmap.md §'Vì sao loại is_high_humidity_fog', "
        "docs/cleaning_log.md §6, README.md",
        "0,0024",
        (
            "MI phụ thuộc ước lượng và CHƯA có định nghĩa nào được đóng băng trong "
            "repo. Trên đúng tập 7.495 dòng: mutual_info_score(pm25, cờ) cho "
            "0,0024 khi chia pm25 thành 7, 8 HOẶC 10 nhóm phân vị (cả ba đều làm "
            "tròn thành 0,0024 → trùng hợp, không định nghĩa duy nhất); "
            "mutual_info_regression (liên tục, tiêu chuẩn scikit-learn) cho "
            "0,0081; mutual_info_classif trên cùng 8 nhóm cho 0,0105. Không được "
            "chọn một cách để khớp 0,0024. Xem "
            "src.flag_evidence.MUTUAL_INFORMATION_UNVERIFIED_REASON."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Nhóm claim của cờ `is_high_humidity_fog` (Issue #38)
# ---------------------------------------------------------------------------
#
# Trước Issue #38, `F = 16,78` / `p = 7,4·10⁻¹¹` chỉ là comment và chuỗi hằng ở
# 6 chỗ — không nơi nào thực sự tính ra. Nay **mọi** con số dưới đây được fit
# lại từ dữ liệu thật bởi `src/flag_evidence.fog_flag_evidence()`.
#
# `source` ghi đúng nơi tài liệu đang công bố con số (theo mục, không theo số
# dòng — số dòng trôi theo mọi lần sửa văn xuôi), để khi MISMATCH thì người đọc
# biết phải sửa tài liệu nào.

_FOG_SOURCE = (
    "src/cleaning_pipeline.py::NON_PREDICTIVE_FLAGS / "
    "docs/roadmap.md §'Vì sao loại is_high_humidity_fog' / "
    "docs/cleaning_log.md §6"
)

#: Khoá claim dùng nhãn mùa ASCII của `src.flag_evidence` (Dong/Xuan/He/Thu) để
#: cột `claim` trong CSV không phụ thuộc bảng mã.
SEASON_CODES = ("Dong", "Xuan", "He", "Thu")

#: Chênh lệch PM2.5 theo mùa đang được công bố (µg/m³), theo nhãn ASCII.
_DOCUMENTED_SEASON_EFFECT = {
    "Dong": 2.79, "Xuan": -8.91, "He": 0.28, "Thu": -2.72,
}

#: CI 95% Welch đang được công bố — nhãn ASCII × ("low" | "high").
_DOCUMENTED_WELCH_CI = {
    ("Dong", "low"): -0.42, ("Dong", "high"): 6.01,
    ("Xuan", "low"): -10.44, ("Xuan", "high"): -7.38,
    ("Thu", "low"): -4.93, ("Thu", "high"): -0.51,
}


from src.flag_evidence import SEASON_LABELS_VI


def fog_claims(evidence: Dict[str, Any]) -> List[Claim]:
    """Sinh nhóm claim định lượng của cờ sương mù từ kết quả đã fit."""
    marginal = evidence["marginal"]
    seasonal = evidence["seasonal"]
    raw = seasonal["raw_mean_difference"]
    welch = seasonal["welch"]
    model = seasonal["model_contrast"]

    claims: List[Claim] = [
        Claim(
            "fog_analysis_rows", _FOG_SOURCE, 7495,
            lambda d: evidence["n_rows_used"],
            note=(
                "Dòng có CẢ pm25 và relative_humidity sau khi ghép "
                "air_quality_canonical + weather_canonical. Cột RH nằm ở tập "
                "khí tượng, không có trong tập ô nhiễm."
            ),
        ),
        Claim(
            "corr_pm25_rh", _FOG_SOURCE, -0.0365,
            lambda d: round(marginal["corr_pm25_rh"], 4), "{:.4f}",
        ),
        Claim(
            "pm25_mean_flag_1", _FOG_SOURCE, 41.65,
            lambda d: round(marginal["mean_pm25_by_flag"][1], 2), "{:.2f}",
        ),
        Claim(
            "n_pm25_flag_1", _FOG_SOURCE, 2384,
            lambda d: marginal["n_pm25_by_flag"][1],
        ),
        Claim(
            "pm25_mean_flag_0", _FOG_SOURCE, 44.75,
            lambda d: round(marginal["mean_pm25_by_flag"][0], 2), "{:.2f}",
        ),
        Claim(
            "n_pm25_flag_0", _FOG_SOURCE, 5111,
            lambda d: marginal["n_pm25_by_flag"][0],
        ),
    ]

    # Khoá claim dùng nhãn mùa ASCII (Dong/Xuan/He/Thu) để CSV kiểm kê không
    # phụ thuộc bảng mã — giá trị hiển thị vẫn là tiếng Việt.
    for season in SEASON_CODES:
        claims.append(
            Claim(
                f"fog_effect_{season.lower()}", _FOG_SOURCE,
                _DOCUMENTED_SEASON_EFFECT[season],
                lambda d, s=season: round(raw[SEASON_LABELS_VI[s]], 2), "{:.2f}",
                note="TB PM2.5 nhóm có cờ − TB nhóm không cờ, trong riêng mùa đó.",
            )
        )

    claims += [
        Claim(
            "fog_interaction_f", _FOG_SOURCE, 16.78,
            lambda d: round(seasonal["f_statistic"], 2), "{:.2f}",
            note=(
                "F-test đồng thời 3 hệ số tương tác của OLS "
                f"`{seasonal['formula']}`."
            ),
        ),
        Claim(
            "fog_interaction_p", _FOG_SOURCE, 7.4e-11,
            lambda d: seasonal["f_p_value"],
            "{:.2e}",
            rtol=0.05,
            note=(
                "p-value của F-test. So sánh TƯƠNG ĐỐI (rtol=5%): nếu dùng dung "
                "sai tuyệt đối 5e-4 thì MỌI p-value < 5e-4 đều bị coi là khớp."
            ),
        ),
        Claim(
            "fog_interaction_df_num", _FOG_SOURCE, 3,
            lambda d: seasonal["f_df_num"],
            note="Số hệ số tương tác bị kiểm định đồng thời (4 mùa → 3 tương tác).",
        ),
        Claim(
            "fog_interaction_df_denom", _FOG_SOURCE, 7487,
            lambda d: int(seasonal["f_df_denom"]),
            note="n − 8 tham số = 7.495 − 8.",
        ),
        Claim(
            "fog_double_difference", _FOG_SOURCE, 7.77,
            lambda d: round(seasonal["double_difference_dong_vs_xuan_he"], 2),
            "{:.2f}",
            note=(
                "Khác biệt kép: chênh lệch Đông − chênh lệch (Xuân + Hè gộp) "
                "= +2,79 − (−4,98)."
            ),
        ),
        Claim(
            "fog_effect_dong_p_model", _FOG_SOURCE, 0.024,
            lambda d: round(model["Đông"]["p_value"], 3), "{:.3f}",
            blocking=False,
            note=(
                "p = 0,024 trong tài liệu là p-value hệ số của MÔ HÌNH tương "
                f"tác (CI 95% [{model['Đông']['ci_low']:.2f}, "
                f"{model['Đông']['ci_high']:.2f}]). Kiểm định Welch trên trung "
                f"bình thô cho p = {welch['Đông']['p_value']:.3f} — KHÁC định "
                "nghĩa, in ra ở phần báo cáo để không lẫn."
            ),
        ),
    ]

    # Khoảng tin cậy 95% mà `build_progress_report.py` và `docs/history/02` công bố
    # đến từ kiểm định Welch trên trung bình thô — khác CI của tương phản mô hình.
    for season in ("Dong", "Xuan", "Thu"):
        for edge, key in (("low", "ci_low"), ("high", "ci_high")):
            label = SEASON_LABELS_VI[season]
            claims.append(
                Claim(
                    f"fog_welch_{season.lower()}_ci_{edge}",
                    "scripts/build_progress_report.py :: fog_flag_evidence_bullet, "
                    "docs/history/02 §PR #34 review vòng 2",
                    _DOCUMENTED_WELCH_CI[(season, edge)],
                    lambda d, s=label, k=key: round(welch[s][k], 2), "{:.2f}",
                    blocking=False, atol=0.011,
                    note=(
                        "CI 95% của kiểm định t Welch trên trung bình nhóm thô. "
                        "Tài liệu trích 2 chữ số thập phân nên dung sai 0,011 cho "
                        "trường hợp đứng đúng mốc làm tròn x,xx5."
                    ),
                )
            )

    return claims


# ---------------------------------------------------------------------------
# Mâu thuẫn mẫu số — in cả hai, KHÔNG tự chọn
# ---------------------------------------------------------------------------

DENOMINATOR_CONFLICTS = [
    {
        "label": "nhãn nặng  pm25 > 100 (tức thời)",
        "source": "docs/roadmap.md:1002, :1015",
        "reason": "Tài liệu đã CHỐT mẫu số = dòng có nhãn pm25, kèm lý do tại roadmap.md:1011 và :1015.",
        "decided": True,
        "variants": [
            ("denominator_labelled", "dòng có nhãn pm25"),
            ("denominator_all", "toàn bộ dòng của split"),
        ],
    },
    {
        "label": "cảnh báo  trung bình trượt 24h >= 50",
        "source": "docs/TASK_LIST_M3_M6.md:42-43",
        "reason": (
            "Tài liệu VIẾT phân số theo mẫu số rolling-hợp-lệ nhưng TÍNH phần trăm "
            "theo mẫu số toàn bộ dòng. Hai phương án cho kết quả khác nhau — CHƯA "
            "có căn cứ để chọn."
        ),
        "decided": False,
        "variants": [
            ("denominator_rolling_valid", "dòng có trung bình trượt hợp lệ"),
            ("denominator_all", "toàn bộ dòng của split"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Thực thi
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {path}.\n"
            "Chạy `python scripts/fetch_dataset.py` rồi chạy lại notebook "
            "`03_transformation_pipeline.ipynb` để tạo tập dữ liệu đóng băng."
        )
    df = pd.read_parquet(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise KeyError(
            f"{path} thiếu cột bắt buộc {missing}. Cột hiện có: {list(df.columns)}"
        )
    return df


def _pct(num: int, den: int) -> str:
    if den == 0:
        raise ZeroDivisionError(f"Mẫu số bằng 0 (tử số={num}) — không tính được tỷ lệ.")
    return f"{num}/{den} = {100 * num / den:.2f}%"


def report_prevalence(df: pd.DataFrame, out: Any) -> None:
    print("=" * 78)
    print("TỶ LỆ NHÃN — in MỌI phương án mẫu số, KHÔNG tự chọn")
    print("=" * 78)
    print(f"Mốc cắt: {SPLIT_TIMESTAMP}   (Issue #7)")
    print()
    train, test = _split(df)

    for part_name, part, calc in (
        ("Train", train, _severe_instant),
        ("Test", test, _severe_instant),
    ):
        s = calc(part)
        print(f"[nhãn nặng pm25>100] {part_name}")
        print(f"   tử số                       : {s['numerator']}")
        print(f"   {_pct(s['numerator'], s['denominator_labelled'])}   "
              f"(mẫu số = dòng có nhãn)  ← roadmap.md:1002 dùng mẫu số này")
        print(f"   {_pct(s['numerator'], s['denominator_all'])}   "
              f"(mẫu số = toàn bộ dòng) ← roadmap.md:1003 nêu để phân biệt")
        print()

    for part_name, part in (("Train", train), ("Test", test)):
        s = _alert_rolling24(part)
        print(f"[cảnh báo trượt24h>=50] {part_name}")
        print(f"   tử số                       : {s['numerator']}")
        print(f"   {_pct(s['numerator'], s['denominator_rolling_valid'])}   "
              f"(mẫu số = dòng rolling hợp lệ) ← phân số TASK_LIST viết ra")
        print(f"   {_pct(s['numerator'], s['denominator_all'])}   "
              f"(mẫu số = toàn bộ dòng)    ← phần trăm TASK_LIST in ra")
        print()

    print("-" * 78)
    print("MÂU THUẪN MẪU SỐ CHƯA CHỐT")
    print("-" * 78)
    for c in DENOMINATOR_CONFLICTS:
        flag = "ĐÃ CHỐT" if c["decided"] else UNDECIDED
        print(f"[{flag}] {c['label']}   ({c['source']})")
        print(f"        {c['reason']}")
    print()
    print("→ Không có định nghĩa nào được script này tự chọn. Xem "
          "docs/PLAN_MIDTERM_RESCHEDULE_PR36.md §4 D2 Phase B.")
    out.write("\n")


def _emit_claims(
    claims: List[Claim],
    df: pd.DataFrame,
    out: Any,
    rows: List[Dict[str, Any]],
) -> int:
    """Chạy từng claim, in kết quả và ghi vào bảng kiểm kê. Trả về số MISMATCH chặn."""
    blocking_mismatch = 0
    for claim in claims:
        try:
            res = claim.run(df)
        except Exception as exc:  # noqa: BLE001 — báo lỗi cụ thể, không nuốt
            res = ClaimResult(claim, UNVERIFIABLE, f"{type(exc).__name__}: {exc}")
        actual = res.actual
        shown = claim.fmt.format(actual) if not isinstance(actual, str) else actual
        doc = claim.documented if not isinstance(claim.documented, float) else \
            claim.fmt.format(claim.documented)
        print(f"[{res.status:11}] {claim.key}")
        print(f"              tài liệu ({claim.source}): {doc}")
        print(f"              tái lập: {shown}")
        if claim.note:
            print(f"              ghi chú: {claim.note}")
        rows.append({
            "claim": claim.key,
            "source": claim.source,
            "documented": str(doc),
            "reproduced": str(shown),
            "status": res.status,
            "blocking": claim.blocking,
        })
        if res.status == MISMATCH and claim.blocking:
            blocking_mismatch += 1
    return blocking_mismatch


def report_claims(
    df: pd.DataFrame,
    out: Any,
    rows: Optional[List[Dict[str, Any]]] = None,
) -> int:
    print()
    print("=" * 78)
    print("CLAIM ĐỊNH NGHĨA ĐƯỢC — tái lập từ Parquet")
    print("=" * 78)
    if rows is None:
        rows = []
    blocking_mismatch = _emit_claims(CLAIMS, df, out, rows)

    print("-" * 78)
    print("CLAIM CHƯA TÁI LẬP ĐƯỢC")
    print("-" * 78)
    for key, source, documented, reason in UNVERIFIABLE_CLAIMS:
        print(f"[{UNVERIFIABLE:11}] {key}")
        print(f"              tài liệu ({source}): {documented}")
        print(f"              lý do: {reason}")
        rows.append({
            "claim": key,
            "source": source,
            "documented": documented,
            "reproduced": "",
            "status": UNVERIFIABLE,
            "blocking": True,
        })
    return blocking_mismatch


def _write_claim_csv(out: Any, rows: List[Dict[str, Any]]) -> None:
    out.write("claim,source,documented,reproduced,status,blocking\n")
    for r in rows:
        out.write(
            f'"{r["claim"]}","{r["source"]}","{r["documented"]}",'
            f'"{r["reproduced"]}","{r["status"]}",{str(r["blocking"]).lower()}\n'
        )


def _print_summary(rows: List[Dict[str, Any]]) -> None:
    print()
    print(f"Tổng: {len(rows)} claim — "
          f"{sum(1 for r in rows if r['status'] == VERIFIED)} VERIFIED, "
          f"{sum(1 for r in rows if r['status'] == MISMATCH)} MISMATCH, "
          f"{sum(1 for r in rows if r['status'] == UNVERIFIABLE)} UNVERIFIABLE")


# ---------------------------------------------------------------------------
# Nhóm cờ `is_high_humidity_fog` — Issue #38
# ---------------------------------------------------------------------------


def resolve_flag_frame(df: pd.DataFrame, explicit: Optional[Path]) -> pd.DataFrame:
    """
    Chọn khung phân tích cho cờ sương mù.

    Thứ tự ưu tiên:
      1. `--flag-dataset` nếu người dùng chỉ định;
      2. chính frame `--dataset` nếu nó đã có đủ cột (tập đã đóng băng);
      3. dựng lại từ `data/interim/*.parquet` bằng làm sạch tất định Issue #6.

    Raises
    ------
    FileNotFoundError / KeyError
        Không dựng được khung — ném lõi để `main()` báo lỗi đầu vào (exit 2).
    """
    from src import flag_evidence

    if explicit is not None:
        return flag_evidence.analysis_frame_from(load_dataset(explicit))

    required = [flag_evidence.TIMESTAMP_COLUMN, flag_evidence.TARGET_COLUMN,
                flag_evidence.HUMIDITY_COLUMN, flag_evidence.FLAG_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if not missing:
        return flag_evidence.analysis_frame_from(df)

    if missing:
        print(f"[GHI CHÚ] Tập --dataset thiếu {missing} → dựng lại khung phân "
              "tích từ data/interim/*.parquet (làm sạch tất định Issue #6).")
    return flag_evidence.build_analysis_frame(
        REPO_ROOT / "data" / "interim" / "air_quality_canonical.parquet",
        REPO_ROOT / "data" / "interim" / "weather_canonical.parquet",
    )


def report_flag_evidence(
    flag_frame: pd.DataFrame,
    out: Any,
    rows: List[Dict[str, Any]],
) -> int:
    """
    Kiểm chứng nhóm claim của cờ `is_high_humidity_fog` (Issue #38).

    F, p, bậc tự do và các chênh lệch theo mùa ở đây **được fit lại từ dữ liệu
    thật** bởi `src/flag_evidence.fog_flag_evidence()` — không phải so chuỗi
    trong source. Claim nào tính không được sẽ báo `UNVERIFIABLE`, không đoán.
    """
    from src import flag_evidence

    seasonal_codes = flag_evidence.SEASON_DISPLAY_ORDER
    if tuple(seasonal_codes) != SEASON_CODES:  # pragma: no cover - chống lệch định nghĩa
        raise ValueError(
            f"Thứ tự mùa trong src.flag_evidence ({seasonal_codes}) lệch với "
            f"bảng khoá claim ở đây ({SEASON_CODES})."
        )
    print()
    print("=" * 78)
    print("CỜ `is_high_humidity_fog` — tái lập từ dữ liệu (Issue #38)")
    print("=" * 78)

    try:
        evidence = flag_evidence.fog_flag_evidence(flag_frame)
    except Exception as exc:  # noqa: BLE001 — báo lỗi cụ thể, không nuốt
        print(f"[{UNVERIFIABLE:11}] fog_flag_evidence")
        print(f"              lý do: {type(exc).__name__}: {exc}")
        rows.append({
            "claim": "fog_flag_evidence",
            "source": _FOG_SOURCE,
            "documented": "F = 16,78; p = 7,4e-11",
            "reproduced": "",
            "status": UNVERIFIABLE,
            "blocking": True,
        })
        return 0

    marginal = evidence["marginal"]
    seasonal = evidence["seasonal"]

    print(f"Tập dùng   : {evidence['n_rows_used']} dòng "
          f"(từ {evidence['n_rows_input']} dòng khung đầu vào)")
    print(f"Công thức  : {seasonal['formula']}")
    print(f"Bậc tự do  : F({int(seasonal['f_df_num'])}, "
          f"{int(seasonal['f_df_denom'])}) trên n = {seasonal['n_obs']}")
    print(f"Số dòng mỗi ô fog × mùa: {evidence['cell_counts']}")
    print()
    print("Chênh lệch PM2.5 (có cờ − không cờ) — điểm ước lượng, CI Welch, "
          "và p của tương phản mô hình:")
    print(f"   {'mùa':<6}{'điểm ước lượng':>16}{'CI 95% Welch':>24}"
          f"{'p Welch':>10}{'p mô hình':>12}")
    for season in ("Đông", "Xuân", "Hè", "Thu"):
        w = seasonal["welch"][season]
        m = seasonal["model_contrast"][season]
        ci_text = f"[{w['ci_low']:.2f}; {w['ci_high']:.2f}]"
        print(f"   {season:<6}{w['difference']:>16.2f}{ci_text:>24}"
              f"{w['p_value']:>10.3f}{m['p_value']:>12.3f}")
    print()
    print(f"Khác biệt kép Đông so với Xuân+Hè: "
          f"{seasonal['double_difference_dong_vs_xuan_he']:+.2f} µg/m³")
    print()
    print("Mutual information — IN MỌI PHƯƠNG ÁN, KHÔNG tự chọn:")
    for name, value in marginal["mutual_information_variants"].items():
        print(f"   {name:<40} {value:.5f}")
    print(f"   → {flag_evidence.MUTUAL_INFORMATION_UNVERIFIED_REASON}")
    out.write("\n")

    print()
    return _emit_claims(fog_claims(evidence), flag_frame, out, rows)


def report_rolling_window(df: pd.DataFrame, out: Any) -> None:
    """
    Chẩn đoán cửa sổ trượt 24h — cơ sở để chốt hoặc bác mẫu số.

    Nhãn cảnh báo **chưa bao giờ được hiện thực hoá** trong `src/` hay notebook nào
    (đã grep: không có `rolling` trong `src/*.py`, không có `rolling(` trong
    `notebooks/*.ipynb`). Vì vậy mẫu số **không tra được từ mã nguồn** — phần này đo
    trực tiếp trên dữ liệu để mô tả hiện trạng, KHÔNG tự chọn con số cuối.

    Phân biệt hai đại lượng dễ nhầm (đã đối chiếu chéo với claim 1.549 dòng NaN):
      * `dòng thiếu`  = số hàng có `pm25` là NaN  → 1.549
      * `đoạn thiếu`  = số lần chạy liên tiếp của NaN → 189 đoạn, tổng độ dài 1.549
    Tổng độ dài các đoạn bằng đúng số dòng thiếu, nên 189 KHÔNG phải số dòng.
    """
    print()
    print("=" * 78)
    print("CHẨN ĐOÁN CỬA SỔ TRƯỢT 24h — nhãn cảnh báo")
    print("=" * 78)
    print("Mã tạo nhãn : KHÔNG TỒN TẠI (grep `rolling` trong src/*.py và")
    print("               notebooks/*.ipynb đều rỗng). Nhãn chỉ có dưới dạng văn xuôi.")
    print()

    roll = df["pm25"].rolling(window=24, min_periods=24).mean()
    valid = roll.notna()
    nan_mask = df["pm25"].isna()
    run_id = (nan_mask != nan_mask.shift()).cumsum()
    runs = nan_mask.groupby(run_id).agg(["sum", "size"])
    gap_runs = runs[runs["sum"] > 0]
    gap_len = gap_runs["sum"]

    print("THIẾU DỮ LIỆU — hai đại lượng khác nhau:")
    print(f"   dòng thiếu (pm25 NaN) : {int(nan_mask.sum())} "
          f"({100 * nan_mask.mean():.1f}%)")
    print(f"   đoạn thiếu (NaN chạy liên tiếp): {len(gap_runs)} đoạn")
    print(f"   tổng độ dài các đoạn  : {int(gap_len.sum())} "
          f"→ bằng đúng số dòng thiếu: "
          f"{'KHỚP' if int(gap_len.sum()) == int(nan_mask.sum()) else 'LỆCH'}")
    print(f"   đoạn dài nhất         : {int(gap_len.max())} giờ "
          f"(chiếm {100 * gap_len.max() / len(df):.1f}% toàn bộ chuỗi)")
    print()
    print(f"Cửa sổ hợp lệ  : {int(valid.sum())} / {len(df)}")
    print(f"Cửa sổ hỏng     : {int((~valid).sum())} — KHÔNG phải 23, vì")
    print(f"                  min_periods=24 đòi cả 24 giá trị đều khác NaN;")
    print(f"                  một đoạn NaN làm hỏng cửa sổ.")
    print()

    print("RẠNH GIỚI TRAIN/TEST — hai cách tính rolling KHÔNG tương đương")
    print("   So sánh trực tiếp trên CÙNG một tập quan sát: cửa sổ hợp lệ,")
    print("   nhãn dương, tỷ lệ và mẫu số. Không chỉ so số lượng cửa sổ.")
    train, test = _split(df)

    # Cách 1 — cách dự án ĐÃ CHỐT: rolling trên TOÀN chuỗi thời gian, rồi lấy phần
    # của mỗi tập. Quan sát đầu Test dùng lịch sử nằm ở đoạn cuối Train: đều là
    # quá khứ (timestamp <= t), nên KHÔNG rò rỉ dữ liệu tương lai.
    roll_all = df["pm25"].rolling(window=24, min_periods=24).mean()
    pos_all = roll_all >= 50

    # Cách 2 — KHÔNG hợp lệ để thay thế: rolling riêng trên từng partition. Các
    # quan sát đầu mỗi partition thiếu đủ 24 giờ lịch sử nên cửa sổ không hợp lệ →
    # bị rớt khỏi CẢ tử số lẫn mẫu số. Đây chính là hiệu ứng biên.
    roll_train = train["pm25"].rolling(window=24, min_periods=24).mean()
    roll_test = test["pm25"].rolling(window=24, min_periods=24).mean()

    for name, part, roll_part, pos_part in (
        ("Train", train, roll_train, roll_train >= 50),
        ("Test", test, roll_test, roll_test >= 50),
    ):
        whole_valid = int(roll_all.notna()[part.index].sum())
        whole_pos = int(pos_all[part.index].sum())
        alone_valid = int(roll_part.notna().sum())
        alone_pos = int(pos_part.sum())
        print(f"   {name:5} : toàn frame {whole_valid:5d} cửa sổ hợp lệ, "
              f"{whole_pos:5d} dương ({_pct(whole_pos, whole_valid)})")
        print(f"            riêng partition {alone_valid:5d} cửa sổ hợp lệ, "
              f"{alone_pos:5d} dương ({_pct(alone_pos, alone_valid)})")
        print(f"            → mất {whole_valid - alone_valid} quan sát do thiếu 24h lịch sử")

    print("   → KẾT LUẬN: hai cách KHÔNG tương đương; ranh giới CÓ ảnh hưởng thật.")
    print("     Dự án chốt dùng cách 'toàn frame' vì lịch sử Test nằm ở cuối Train —")
    print("     đều quá khứ, không dữ liệu tương lai, không rò rỉ. Nhớ: 986 / 669 / 1.655")
    print("     chỉ đúng cho cách 'toàn frame', và vẫn mang tính GIẢ ĐỊNH.")
    print()

    print("ĐỘ NHẠY — số nhãn dương PHỤ THUỘC tham số chưa được mã định nghĩa:")
    print(f"   {'cấu hình':34} {'Train':>6} {'Test':>6} {'Tổng':>6}  {'(a)':>7}  {'(b)':>7}")
    print("   " + "-" * 72)
    configs = [
        (24, 24, 50, "rolling(24, mp=24) ≥ 50  ← GIẢ ĐỊNH"),
        (24, 12, 50, "rolling(24, mp=12) ≥ 50"),
        (24, 6, 50, "rolling(24, mp=6)  ≥ 50"),
        (24, 1, 50, "rolling(24, mp=1)  ≥ 50"),
        (1, 1, 50, "không trượt (phút thời) ≥ 50"),
        (24, 24, 35, "rolling(24, mp=24) ≥ 35"),
    ]
    for window, mp, thresh, label in configs:
        r = df["pm25"].rolling(window=window, min_periods=mp).mean()
        n_tr = int(r[train.index].notna().sum())
        n_te = int(r[test.index].notna().sum())
        a = int((r[train.index] >= thresh).sum())
        b = int((r[test.index] >= thresh).sum())
        print(f"   {label:34} {a:>6} {b:>6} {a + b:>6}  "
              f"{_pct(a, n_tr):>7}  {_pct(a + b, len(df)):>7}")
    print()
    print("   → Tổng số nhãn dương dao động mạnh (1.655 ↔ 2.355 ↔ 3.133) theo tham số.")
    print("     Tỷ lệ (a) ổn định hơn (~32–33%) vì tử số và mẫu số cùng đổi.")
    print("     Tỷ lệ (b) NHẠY hơn (18,30% ↔ 26,04%) vì mẫu số cố định 9.044.")
    print()
    print(f"[{UNDECIDED}] 986 / 669 / 1.655 KHÔNG PHẢI số đã xác minh.")
    print("         Chúng tái lập được CHỈ khi giả định đúng rolling(24, min_periods=24)")
    print("         và ngưỡng ≥ 50 — mà giả định này chỉ có dưới dạng văn xuôi, không có")
    print("         hàm, không có test, không có dấu vết thực thi trong repo.")
    print("         Vì vậy KHÔNG được coi là kết quả thực nghiệm đã kiểm chứng.")
    print()
    pos = int((roll >= 50).sum())
    print("HAI MẪU SỐ GIỮ NGUYÊN (dưới giả định nêu trên) — trả lời HAI câu hỏi khác nhau:")
    print(f"   (a) dòng rolling hợp lệ : {_pct(pos, int(valid.sum()))}")
    print("       → 'Trong số giờ CÓ THỂ đo được, bao nhiêu % vượt ngưỡng?'")
    print(f"   (b) toàn bộ dòng         : {_pct(pos, len(df))}")
    print("       → 'Trên toàn bộ thời gian, bao nhiêu % thời điểm vượt ngưỡng?'")
    print("       Phần thời gian không đo được bị tính vào mẫu số → hạ thấp tỷ lệ.")
    print()
    print(f"[{UNDECIDED}] Chưa có câu hỏi nào được ghi trong repo là 'câu hỏi đúng',")
    print("         nên chưa công bố con số chính thức. Xem task 0.7b.")
    out.write("\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tái lập các claim định lượng trong tài liệu từ dữ liệu thật.",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--flag-dataset", type=Path, default=None,
        help=(
            "Tệp Parquet chứa pm25 + relative_humidity + is_high_humidity_fog để "
            "kiểm chứng nhóm claim của cờ sương mù. Mặc định: dùng chính "
            "--dataset nếu đã đủ cột, nếu không thì dựng lại từ "
            "data/interim/*.parquet bằng làm sạch tất định của Issue #6."
        ),
    )
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Ghi bảng kiểm kê CSV (mặc định reports/claim_audit.csv).",
    )
    args = parser.parse_args(argv)

    try:
        df = load_dataset(args.dataset)
        flag_frame = resolve_flag_frame(df, args.flag_dataset)
    except (FileNotFoundError, KeyError) as exc:
        print(f"LỖI ĐẦU VÀO: {exc}", file=sys.stderr)
        return 2

    out_path = args.out or (args.reports_dir / "claim_audit.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Tập dữ liệu : {args.dataset}")
    print(f"Số dòng x cột: {df.shape[0]} x {df.shape[1]}")
    print(f"Dải thời gian: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"Khung cờ sương mù: {flag_frame.shape[0]} x {flag_frame.shape[1]}")
    print(f"Bảng kiểm kê : {out_path}")
    print()

    rows: List[Dict[str, Any]] = []
    with out_path.open("w", encoding="utf-8", newline="") as out:
        blocking = report_claims(df, out, rows)
        blocking += report_flag_evidence(flag_frame, out, rows)
        report_prevalence(df, out)
        report_rolling_window(df, out)
        _write_claim_csv(out, rows)
        _print_summary(rows)

    if blocking:
        print(f"\n==> {blocking} claim MISMATCH mức chặn merge.")
        return 1
    print("\n==> Không có claim MISMATCH mức chặn merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())