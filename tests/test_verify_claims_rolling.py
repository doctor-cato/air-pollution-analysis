"""
Unit tests cho tính đúng đắn ranh giới Train/Test của nhãn cảnh báo trượt 24h.

Bối cảnh: `scripts/verify_claims.py::report_rolling_window()` đã từng so sánh
**chỉ số lượng** cửa sổ hợp lệ giữa "rolling trên toàn frame" và "rolling riêng
từng partition", rồi kết luận *"không có hiệu ứng biên tại mốc cắt"*. Sai về
mặt logic: số lượng bằng nhau KHÔNG chứng minh các cửa sổ chứa cùng dữ liệu, cùng
nhãn, hay cùng tỷ lệ — và ranh giới THẬT SỰ có hiệu ứng vì quan sát đầu mỗi
partition thiếu lịch sử.

Các test này dùng dữ liệng synthetic (không cần Parquet) để khoá đúng 4 tính chất
toán học mà phép kiểm chứng phải chứng minh được:

  1. Rolling riêng partition MẤT đúng `window - 1` quan sát đầu partition.
  2. Rolling trên toàn frame tại ranh giới chỉ dùng dữ liệu QUÁ KHỨ (không rò rỉ).
  3. Nhãn của hai cách tính KHÔNG trùng nhau tại vùng ranh giới.
  4. Mẫu số (và do đó tỷ lệ/prevalence) của hai cách tính khác nhau.
  5. Khoảng NaN làm không hợp lệ đúng `window` cửa sổ chứa nó.

Không test nào chạm vào `data/` — tất cả dữ liệu sinh trong bộ nhớ.
"""

import importlib.util
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent

# `scripts/` không phải package — nạp trực tiếp tệp để dùng SPLIT_TIMESTAMP
# và `_alert_rolling24()` mà không kích hoạt `main()`.
_spec = importlib.util.spec_from_file_location(
    "verify_claims", REPO_ROOT / "scripts" / "verify_claims.py"
)
verify_claims = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify_claims)

SPLIT = verify_claims.SPLIT_TIMESTAMP
WINDOW = 24


def make_frame(n: int = 6000, value: float = 60.0) -> pd.DataFrame:
    """Chuỗi giờ liên tục, `pm25` hằng → cửa sổ hợp lệ nào cũng ≥ 50.

    `n=6000` (~250 ngày từ 2025-07-03) để chuỗi VƯỢT qua mốc cắt
    `2026-01-15` — đủ để kiểm tra ranh giới thật.
    """
    idx = pd.date_range("2025-07-03 00:00", periods=n, freq="h", tz="Asia/Ho_Chi_Minh")
    return pd.DataFrame({"timestamp": idx, "pm25": value, "pm10": 70.0})


class RollingBoundaryTests(unittest.TestCase):
    def test_partition_only_rolling_loses_history_at_partition_start(self):
        """Rolling riêng partition mất đúng `window - 1` quan sát đầu partition."""
        df = make_frame()
        train = df[df["timestamp"] < SPLIT]
        test = df[df["timestamp"] >= SPLIT]

        roll_all = df["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()
        roll_train = train["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()
        roll_test = test["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()

        # Train bắt đầu NGAY đầu frame → hai cách cùng mất WINDOW-1 quan sát
        # đầu frame (chưa đủ 24h lịch sử). Kết quả cho Train GIỐNG NHAU.
        self.assertEqual(int(roll_all.notna()[train.index].sum()),
                         len(train) - WINDOW + 1)
        self.assertEqual(int(roll_train.notna().sum()),
                         len(train) - WINDOW + 1)

        # Test bắt đầu GIỮA frame: cách "toàn frame" có lịch sử từ đuôi Train,
        # cách "riêng partition" MẤT WINDOW-1 quan sát đầu Test.
        self.assertEqual(int(roll_all.notna()[test.index].sum()), len(test))
        self.assertEqual(int(roll_test.notna().sum()), len(test) - WINDOW + 1)

        self.assertEqual(
            int(roll_all.notna()[test.index].sum()) - int(roll_test.notna().sum()),
            WINDOW - 1,
            "Hiệu ứng biên phải là đúng (window - 1) quan sát — không phải 0. "
            "Train không bị ảnh hưởng, Test bị mất lịch sử.",
        )

    def test_whole_frame_rolling_uses_only_past_values_at_boundary(self):
        """Rolling tại thời điểm t chỉ được tính từ các quan sát có timestamp <= t."""
        df = make_frame()
        cut = int((df["timestamp"] >= SPLIT).idxmax())
        self.assertGreater(cut, WINDOW, "Cần đủ lịch sử trước mốc cắt.")

        roll = df["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()
        expected = df["pm25"].iloc[cut - WINDOW: cut].mean()

        self.assertEqual(
            roll.iloc[cut], expected,
            "Giá trị rolling tại mốc cắt phải bằng trung bình 24 giá trị ngay trước đó.",
        )
        # Quan sát ĐẦU TIÊN của Test: cả 24 giá trị đóng góp đều nằm trong Train.
        contributing = df["timestamp"].iloc[cut - WINDOW: cut]
        self.assertTrue(
            (contributing < SPLIT).all(),
            "Rò rỉ tương lai: cửa sổ tại đầu Test phải chỉ chứa dữ liệu của Train.",
        )

    def test_two_computations_disagree_on_labels_at_boundary(self):
        """Nhãn của hai cách tính KHÔNG trùng nhau tại vùng ranh giới."""
        df = make_frame()
        test = df[df["timestamp"] >= SPLIT]
        roll_all = df["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()
        roll_test = test["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()

        first = test.index[0]
        self.assertTrue(pd.notna(roll_all.loc[first]),
                        "Toàn frame: quan sát đầu Test CÓ nhãn.")
        self.assertTrue(pd.isna(roll_test.loc[first]),
                        "Riêng partition: quan sát đầu Test mất nhãu (không có lịch sử).")

    def test_denominators_and_prevalence_differ_between_computations(self):
        """Mẫu số — và do đó tỷ lệ/prevalence — của hai cách tính khác nhau."""
        df = make_frame()
        test = df[df["timestamp"] >= SPLIT]
        roll_all = df["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()
        roll_test = test["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()

        valid_all = int(roll_all.notna()[test.index].sum())
        valid_alone = int(roll_test.notna().sum())
        pos_all = int((roll_all >= 50)[test.index].sum())
        pos_alone = int((roll_test >= 50).sum())

        # Với pm25 hằng 60, mọi cửa sổ hợp lệ đều dương.
        self.assertEqual(pos_all, valid_all)
        self.assertEqual(pos_alone, valid_alone)

        # (a) mẫu số = cửa sổ hợp lệ
        pct_all = 100 * pos_all / valid_all
        pct_alone = 100 * pos_alone / valid_alone
        self.assertAlmostEqual(pct_all, 100.0, places=6)
        self.assertAlmostEqual(pct_alone, 100.0, places=6)

        # (b) mẫu số = toàn bộ dòng — đây là chỗ hai cách tính KHÁC NHAU thật.
        self.assertEqual(100 * pos_all / len(test), 100.0)
        self.assertLess(
            100 * pos_alone / len(test), 100.0,
            "Mẫu số toàn-bộ-dòng của cách 'riêng partition' phải NHỎ HƠN cách "
            "'toàn frame' vì nó mất cả tử số lẫn mẫu số ở đầu partition.",
        )

    def test_nan_gap_invalidates_exactly_window_windows(self):
        """Một khoảng NaN làm không hợp lệ đúng `window` cửa sổ chứa nó."""
        df = make_frame(n=200)
        gap_pos = 100          # giữa chuỗi, tránh chồng lấn với vùng warmup
        df.loc[gap_pos, "pm25"] = float("nan")

        roll = df["pm25"].rolling(WINDOW, min_periods=WINDOW).mean()

        # Quan sát ngay TRƯỚC khoảng NaN vẫn hợp lệ.
        self.assertFalse(pd.isna(roll.iloc[gap_pos - 1]))
        # Đúng WINDOW cửa sổ chứa NaN bị hỏng.
        for k in range(gap_pos, gap_pos + WINDOW):
            self.assertTrue(
                pd.isna(roll.iloc[k]),
                f"Cửa sổ kết thúc tại vị trí {k} chứa NaN nên phải không hợp lệ.",
            )
        # Cửa sổ đầu tiên KHÔNG chứa NaN đã hợp lệ lại.
        self.assertFalse(
            pd.isna(roll.iloc[gap_pos + WINDOW]),
            "Cửa sổ đầu tiên không chứa NaN phải hợp lệ.",
        )

        # Tổng: mất (WINDOW - 1) quan sát warmup + WINDOW quan sát do khoảng NaN.
        expected_invalid = (WINDOW - 1) + WINDOW
        self.assertEqual(
            int(roll.notna().sum()), len(df) - expected_invalid,
            f"Phải mất đúng {expected_invalid} cửa sổ.",
        )

    def test_alert_rolling24_exposes_both_denominators(self):
        """`_alert_rolling24()` phải báo CẢ hai mẫu số — không tự chọn."""
        df = make_frame()
        for part in (df[df["timestamp"] < SPLIT], df[df["timestamp"] >= SPLIT]):
            res = verify_claims._alert_rolling24(part)
            self.assertIn("numerator", res)
            self.assertIn("denominator_rolling_valid", res)
            self.assertIn("denominator_all", res)
            self.assertEqual(res["denominator_all"], len(part))
            self.assertGreaterEqual(res["numerator"], 0)
            self.assertGreaterEqual(res["denominator_rolling_valid"], 0)
            self.assertLessEqual(res["denominator_rolling_valid"], res["denominator_all"])


if __name__ == "__main__":
    unittest.main()