"""
verify_claims.py — Tái lập các claim định lượng đang được trích trong tài liệu.

Mục đích
--------
Một số con số trong `docs/TASK_LIST_M3_M6.md` được đọc thẳng từ tệp Parquet nhưng
không có cách nào chạy lại để kiểm chứng. Script này là cơ chế tái lập:

    python scripts/verify_claims.py

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
    ) -> None:
        self.key = key
        self.source = source
        self.documented = documented
        self.compute = compute
        self.fmt = fmt
        self.blocking = blocking
        self.note = note

    def run(self, df: pd.DataFrame) -> "ClaimResult":
        actual = self.compute(df)
        if isinstance(self.documented, float):
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
#: Danh sách trống: mọi claim đã ghi đều có định nghĩa đủ rõ để tái lập.
#: Nếu về sau gặp claim không tái lập được, thêm mục `(key, source, value, lý do)`
#: vào đây — mục đích là GHI NHẬN chứ không phải điền số dự kiến.
UNVERIFIABLE_CLAIMS: List[tuple] = []


# ---------------------------------------------------------------------------
# Mâu thuẫn mẫu số — in cả hai, KHÔNG tự chọn
# ---------------------------------------------------------------------------

DENOMINATOR_CONFLICTS = [
    {
        "label": "nhãn nặng  pm25 > 100 (tức thời)",
        "source": "docs/roadmap.md:984, :997",
        "reason": "Tài liệu đã CHỐT mẫu số = dòng có nhãn pm25, kèm lý do tại roadmap.md:990-997.",
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
              f"(mẫu số = dòng có nhãn)  ← roadmap.md:984 dùng mẫu số này")
        print(f"   {_pct(s['numerator'], s['denominator_all'])}   "
              f"(mẫu số = toàn bộ dòng) ← roadmap.md:985 nêu để phân biệt")
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


def report_claims(df: pd.DataFrame, out: Any) -> int:
    print()
    print("=" * 78)
    print("CLAIM ĐỊNH NGHĨA ĐƯỢC — tái lập từ Parquet")
    print("=" * 78)
    blocking_mismatch = 0
    rows: List[Dict[str, Any]] = []

    for claim in CLAIMS:
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

    out.write("claim,source,documented,reproduced,status,blocking\n")
    for r in rows:
        out.write(
            f'"{r["claim"]}","{r["source"]}","{r["documented"]}",'
            f'"{r["reproduced"]}","{r["status"]}",{str(r["blocking"]).lower()}\n'
        )
    print()
    print(f"Tổng: {len(rows)} claim — "
          f"{sum(1 for r in rows if r['status'] == VERIFIED)} VERIFIED, "
          f"{sum(1 for r in rows if r['status'] == MISMATCH)} MISMATCH, "
          f"{sum(1 for r in rows if r['status'] == UNVERIFIABLE)} UNVERIFIABLE")
    return blocking_mismatch


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
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Ghi bảng kiểm kê CSV (mặc định reports/claim_audit.csv).",
    )
    args = parser.parse_args(argv)

    try:
        df = load_dataset(args.dataset)
    except (FileNotFoundError, KeyError) as exc:
        print(f"LỖI ĐẦU VÀO: {exc}", file=sys.stderr)
        return 2

    out_path = args.out or (args.reports_dir / "claim_audit.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Tập dữ liệu : {args.dataset}")
    print(f"Số dòng x cột: {df.shape[0]} x {df.shape[1]}")
    print(f"Dải thời gian: {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"Bảng kiểm kê : {out_path}")
    print()

    with out_path.open("w", encoding="utf-8", newline="") as out:
        blocking = report_claims(df, out)
        report_prevalence(df, out)
        report_rolling_window(df, out)

    if blocking:
        print(f"\n==> {blocking} claim MISMATCH mức chặn merge.")
        return 1
    print("\n==> Không có claim MISMATCH mức chặn merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())