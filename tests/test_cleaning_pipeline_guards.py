"""Test hồi quy cho 6 BLOCKER của Issue #7 (chặn rò rỉ). Viết TRƯỚC khi sửa.

Mỗi test ở đây PHẢI FAIL trên bản gốc `src/cleaning_pipeline.py` hiện tại và
PASS sau khi sửa. Đây là bằng chứng, không phải trang trí.
"""
from __future__ import annotations

import sys
import unittest
import unittest.mock
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import cleaning_pipeline as cp  # noqa: E402

TZ = "Asia/Ho_Chi_Minh"


def _wind_frame(n=200, level=0.0, start="2026-01-01 00:00", station="STATION_A"):
    ts = pd.date_range(start=start, periods=n, freq="h", tz=TZ)
    return pd.DataFrame({
        "timestamp": ts,
        "station_id": station,
        "pm25": level + np.linspace(10.0, 20.0, n),
        "pm10": level + np.linspace(12.0, 24.0, n),
    })


def _wx_frame(n=200, level=0.0, start="2026-01-01 00:00"):
    ts = pd.date_range(start=start, periods=n, freq="h", tz=TZ)
    return pd.DataFrame({
        "timestamp": ts,
        "temperature": level + np.linspace(18.0, 28.0, n),
        "relative_humidity": level + 60.0,
        "wind_speed": level + 3.0,
        "wind_direction": level + 120.0,
        "precipitation": level,
        "surface_pressure": level + 1010.0,
    })


class B1RandomSplitIsDetected(unittest.TestCase):
    """BLOCKER 1 — `validate_no_leakage()` không đọc `timestamp`, nên random split
    (vi phạm cam biên #1 của dự án) vẫn in ra '✓ No leakage'."""

    def setUp(self):
        self.air = _wind_frame(400, level=0.0)
        self.wx = _wx_frame(400, level=0.0)

    def test_guard_rejects_a_random_split(self):
        from sklearn.model_selection import train_test_split

        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = train_test_split(X, test_size=0.3, random_state=42)

        # Chuẩn bị: chứng minh split này THỰC SỰ vi phạm.
        ts = merged["timestamp"]
        self.assertGreater(ts.loc[X_tr.index].max(), ts.loc[X_te.index].min(),
                           "test fixture phải là random split thật")

        pipeline = cp.build_preprocessing_pipeline(feats, [])
        pipeline.fit(X_tr)
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(
                pipeline,
                X_train=X_tr,
                X_test=X_te,
                timestamps=ts.loc[X_tr.index],
                test_timestamps=ts.loc[X_te.index],
            )
        self.assertIn("thời gian", str(ctx.exception).lower())

    def test_guard_warns_when_the_chronology_layer_is_disabled(self):
        """Bỏ truyền timestamp KHÔNG được im lặng.

        Đo lại trên dữ liệu thật: random split + đúng X_train/X_test nhưng
        không truyền timestamp là **không bị bắt** — vì các lớp 2–3 chỉ so
        tham số học, mà split ngẫu nhiên vẫn học đúng trên "Train" của nó.
        Lớp 1 là lớp DUY NHẤT chống được random split, nên việc tắt nó phải
        nói to chứ không được để người gọi tin là đã kiểm chứng.
        """
        from sklearn.model_selection import train_test_split

        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = train_test_split(X, test_size=0.3, random_state=42)

        pipeline = cp.build_preprocessing_pipeline(feats, [])
        pipeline.fit(X_tr)
        with self.assertLogs("src.cleaning_pipeline", level="WARNING") as logs:
            cp.validate_no_leakage(pipeline, X_train=X_tr, X_test=X_te)
        self.assertTrue(
            any("THỨ TỰ THỜI GIAN" in m for m in logs.output),
            f"phải cảnh báo lớp thứ tự thời gian đang bị tắt; thấy: {logs.output}",
        )

    def test_guard_rejects_half_passed_timestamps(self):
        """Truyền `timestamps` mà không truyền `test_timestamps` là lỗi ghi
        nhầm, không phải ý định — phải ném lỗi chứ không tắt lớp kiểm chứng."""
        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = X.iloc[:120], X.iloc[120:]
        pipeline = cp.build_preprocessing_pipeline(feats, [])
        pipeline.fit(X_tr)

        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(
                pipeline, X_train=X_tr, X_test=X_te,
                timestamps=merged["timestamp"].iloc[:120],
            )
        self.assertIn("test_timestamps", str(ctx.exception))


class B2ScalerIsVerified(unittest.TestCase):
    """BLOCKER 2 — docstring hứa so 'tham số scale' nhưng code chỉ so median
    imputer; thay RobustScaler bằng bản fit trên Test vẫn qua."""

    def setUp(self):
        rng = np.random.default_rng(7)
        self.X_train = pd.DataFrame({
            "pm10": rng.normal(40.0, 5.0, 300),
            "temperature": rng.normal(22.0, 2.0, 300),
        })
        self.X_test = pd.DataFrame({
            "pm10": rng.normal(400.0, 5.0, 150),
            "temperature": rng.normal(60.0, 2.0, 150),
        })
        self.feats = ["pm10", "temperature"]

    def test_guard_rejects_a_scaler_fitted_on_test(self):
        pipeline = cp.build_preprocessing_pipeline(self.feats, [])
        pipeline.fit(self.X_train)                      # đúng
        num = pipeline.named_steps["preprocessor"].named_transformers_["num"]
        num.named_steps["scaler"].fit(self.X_test)     # rò rỉ ở scaler
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(
                pipeline, X_train=self.X_train, X_test=self.X_test
            )
        self.assertIn("scaler", str(ctx.exception).lower())

    def test_guard_rejects_a_whole_pipeline_fitted_on_test(self):
        pipeline = cp.build_preprocessing_pipeline(self.feats, [])
        pipeline.fit(self.X_test)
        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(pipeline, X_train=self.X_train, X_test=self.X_test)


class B3EveryTransformerIsChecked(unittest.TestCase):
    """BLOCKER 3 — guard chỉ nhìn transformer tên 'num'; transformer thứ hai học
    trên Test thì im lặng."""

    def test_guard_rejects_a_second_transformer_fitted_on_test(self):
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import RobustScaler

        feats = ["pm10"]
        X_train = pd.DataFrame({"pm10": np.linspace(1, 10, 100)})
        X_test = pd.DataFrame({"pm10": np.linspace(500, 509, 100)})

        pre = ColumnTransformer([
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")),
                              ("scaler", RobustScaler())]), feats),
            ("cyc", Pipeline([("imputer", SimpleImputer(strategy="median")),
                              ("scaler", RobustScaler())]), feats),
        ], remainder="drop")
        pipeline = Pipeline([("preprocessor", pre)])
        pipeline.fit(X_train)
        # Rò rỉ: transformer thứ hai học trên Test.
        pre.named_transformers_["cyc"].fit(X_test)

        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(pipeline, X_train=X_train, X_test=X_test)

    def test_guard_covers_a_second_branch_over_a_different_column_set(self):
        """
        Nhánh thứ hai dùng TẬP CỘT KHÁC nhánh `num`. Guard phải gom cả hai tập cột
        — nếu chỉ lấy tập của `num` thì lệnh refit sẽ không tìm thấy cột của
        nhánh kia và ném ValueError mù thay vì kết luận đúng.
        """
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import RobustScaler

        X_train = pd.DataFrame({
            "pm10": np.linspace(1, 10, 100),
            "hour_sin": np.linspace(0.0, 1.0, 100),
        })
        X_test = pd.DataFrame({
            "pm10": np.linspace(500, 509, 100),
            "hour_sin": np.linspace(-1.0, 1.0, 100),
        })
        pre = ColumnTransformer([
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")),
                              ("scaler", RobustScaler())]), ["pm10"]),
            ("cyc", Pipeline([("imputer", SimpleImputer(strategy="median")),
                              ("scaler", RobustScaler())]), ["hour_sin"]),
        ], remainder="drop")
        pipeline = Pipeline([("preprocessor", pre)])
        pipeline.fit(X_train)
        # Rò rỉ: nhánh `cyc` học trên Test.
        pre.named_transformers_["cyc"].fit(X_test)
        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(pipeline, X_train=X_train, X_test=X_test)


class B4ArgumentOrderCannotBeSwapped(unittest.TestCase):
    """BLOCKER 4 — đảo thứ tự `X_train, X_test` vô hiệu hóa toàn bộ guard."""

    def test_guard_rejects_swapped_positional_arguments(self):
        """
        Đảo thứ tự là lỗi ghi nhầm biến. Nay hai tham số keyword-only nên lỗi
        này bị Python chặn ngay — cấu trúc chống được, không phải "hy vọng
        guard nhận ra".
        """
        X_train = pd.DataFrame({"pm10": np.linspace(1, 10, 100)})
        X_test = pd.DataFrame({"pm10": np.linspace(500, 509, 100)})
        pipeline = cp.build_preprocessing_pipeline(["pm10"], [])
        pipeline.fit(X_test)  # fit trên Test
        with self.assertRaises(TypeError):
            cp.validate_no_leakage(pipeline, X_test, X_train)


class B5TargetIsNeverADefaultFeature(unittest.TestCase):
    """BLOCKER 5 — `NUMERIC_FEATURES` chứa sẵn target `pm25`; gọi hàm không tham số
    là đưa chính target vào X (R^2 = 1.0)."""

    def test_default_numeric_features_exclude_the_target(self):
        self.assertNotIn("pm25", cp.NUMERIC_FEATURES)
        self.assertNotIn(cp.TARGET_CANDIDATE, cp.NUMERIC_FEATURES)

    def test_builder_rejects_the_target_explicitly(self):
        with self.assertRaises(ValueError) as ctx:
            cp.build_preprocessing_pipeline(numeric_features=["pm25", "pm10"],
                                           cyclical_features=[])
        self.assertIn("target", str(ctx.exception).lower())

    def test_builder_rejects_the_target_in_the_cyclical_list_too(self):
        """Nhánh cyclical của guard target (`:337-338`) chưa có test nào chạm tới.

        Cột chu kỳ đi qua `passthrough` chứ không qua imputer, nên nếu target lọt
        vào đây thì nó được truyền thẳng ra ma trận đặc trưng — và
        `validate_no_leakage()` sẽ **không** bắt được, vì không có tham số nào
        được học trên nó. Đó là lý do guard phải chặn ở cả hai danh sách.
        """
        with self.assertRaises(ValueError) as ctx:
            cp.build_preprocessing_pipeline(numeric_features=["pm10"],
                                           cyclical_features=["pm25"])
        self.assertIn("target", str(ctx.exception).lower())

    def test_builder_rejects_duplicate_numeric_columns(self):
        """Cột lặp trong danh sách feature bị `ColumnTransformer` đếm hai lần.

        Không có test nào chạm nhánh `:340-342`. Hậu quả: `coef_` /
        `feature_importances_` đọc theo vị trí sẽ lệch, và cùng một tín hiệu bị
        đưa vào mô hình hai lần với hai trọng số độc lập.
        """
        with self.assertRaises(ValueError) as ctx:
            cp.build_preprocessing_pipeline(
                numeric_features=["pm10", "temperature", "pm10"],
                cyclical_features=[])
        self.assertIn("lặp", str(ctx.exception).lower())

    def test_default_builder_does_not_emit_the_target(self):
        df = pd.DataFrame({
            "pm25": np.linspace(10, 40, 50),
            "pm10": np.linspace(12, 45, 50),
            "temperature": np.linspace(18, 26, 50),
        })
        p = cp.build_preprocessing_pipeline(
            numeric_features=[c for c in cp.NUMERIC_FEATURES if c in df.columns],
            cyclical_features=[])
        p.fit(df)
        names = list(p.named_steps["preprocessor"].get_feature_names_out())
        self.assertFalse([n for n in names if n.endswith("__pm25")], names)


class B6MergeRejectsFullyUnmatchedWeather(unittest.TestCase):
    """BLOCKER 6 — `.agents/rules/data.md` §3.6 BẮT BUỘC
    `assert not df_merged['temperature'].isna().all()`; thiếu nên merge trả về
    6 cột khí tượng toàn NaN mà không nói gì."""

    def test_merge_rejects_weather_that_does_not_overlap_at_all(self):
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(10, start="2030-01-01 00:00")   # không giao nhau
        with self.assertRaises((AssertionError, ValueError)) as ctx:
            cp.merge_air_weather(air, wx)
        self.assertIn("nan", str(ctx.exception).lower())

    def test_merge_rejects_weather_shifted_out_of_the_window(self):
        """Lệch cửa sổ 1 ngày -> 0/10 dòng khớp -> toàn bộ cột khí tượng NaN."""
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(10, start="2026-01-02 00:00")
        with self.assertRaises((AssertionError, ValueError)):
            cp.merge_air_weather(air, wx)

    def test_merge_warns_when_coverage_is_partial(self):
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(6, start="2026-01-01 00:00")   # chỉ 6/10 giờ
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            merged = cp.merge_air_weather(air, wx)
        self.assertEqual(len(merged), len(air))
        self.assertTrue(any("coverage" in str(w.message).lower() or
                            "khớp" in str(w.message) for w in caught))

    def test_merge_rejects_colliding_column_names(self):
        """Hai bảng cùng tên cột ngoài khoá -> _x/_y, mất tên gốc."""
        air = _wind_frame(6).assign(pm25_was_missing=0)
        wx = _wx_frame(6).assign(pm25_was_missing=1)
        with self.assertRaises((AssertionError, ValueError)) as ctx:
            cp.merge_air_weather(air, wx)
        self.assertIn("pm25_was_missing", str(ctx.exception))


class B7TargetDerivedFlagIsNotAFeature(unittest.TestCase):
    """BLOCKER 7 — `pm25_was_missing` là hàm xác định của `pm25.isna()`, còn
    `SimpleImputer` lại điền median cho đúng những hàng đó -> mô hình học được
    `flag==1 => pm25 == median` đúng 100%. Đây là rò rỉ target theo cấu trúc."""

    def test_flag_is_declared_target_derived(self):
        self.assertIn("pm25_was_missing", cp.TARGET_DERIVED_FLAGS)
        self.assertNotIn("pm25_was_missing", cp.DIAGNOSTIC_FEATURES)

    def test_allowed_diagnostic_features_exclude_only_the_target_derived_one(self):
        self.assertIn("is_high_humidity_fog", cp.DIAGNOSTIC_FEATURES)
        self.assertIn("pm25_was_stuck", cp.DIAGNOSTIC_FEATURES)

    def test_the_leak_is_actually_deterministic(self):
        """Chứng minh cơ chế: mọi hàng flag=1 có target = median sau khi impute."""
        air = _wind_frame(300)
        air.loc[air.index[::7], "pm25"] = np.nan
        air["pm25_was_missing"] = air["pm25"].isna().astype(int)
        med = float(np.nanmedian(air["pm25"]))
        filled = air["pm25"].fillna(med)
        flag = air["pm25_was_missing"].astype(bool)
        self.assertGreater(int(flag.sum()), 0)
        self.assertEqual(int(((filled == med) & flag).sum()), int(flag.sum()))


class B8TransformNeverRefits(unittest.TestCase):
    """
    Reviewer 5 đo mutation score 44,7%: mutate `transform_with_pipeline()` thành
    *refit trên chính X truyền vào* — tức học tham số từ Test — thì 0/36 test cũ
    fail, vì không test nào gọi hàm này. Đây là biến thể nguy hiểm nhất của rò rỉ
    (âm thầm, không có cảnh báo nào) nên phải có test riêng.
    """

    def setUp(self):
        rng = np.random.default_rng(11)
        self.feats = ["pm10", "temperature"]
        self.X_train = pd.DataFrame({
            "pm10": rng.normal(30.0, 4.0, 300),
            "temperature": rng.normal(22.0, 2.0, 300),
        })
        # Test lệch mạnh: nếu bị refit, mọi tham số học đều đổi theo.
        self.X_test = pd.DataFrame({
            "pm10": rng.normal(300.0, 4.0, 150),
            "temperature": rng.normal(60.0, 2.0, 150),
        })
        self.pipeline = cp.fit_pipeline_on_train(
            cp.build_preprocessing_pipeline(self.feats, []), self.X_train
        )

    def _params(self):
        return cp._learned_arrays(self.pipeline.named_steps["preprocessor"])

    def test_fit_helper_returns_the_same_fitted_object(self):
        p = cp.build_preprocessing_pipeline(self.feats, [])
        returned = cp.fit_pipeline_on_train(p, self.X_train)
        self.assertIs(returned, p)
        self.assertTrue(hasattr(
            p.named_steps["preprocessor"].named_transformers_["num"]
            .named_steps["imputer"], "statistics_"))

    def test_transform_helper_does_not_change_any_fitted_parameter(self):
        before = {k: v.copy() for k, v in self._params().items()}
        cp.transform_with_pipeline(self.pipeline, self.X_test)
        after = self._params()
        self.assertEqual(set(before), set(after))
        for key in before:
            np.testing.assert_array_equal(
                before[key], after[key], err_msg=f"{key} bị thay đổi sau transform"
            )

    def test_transform_helper_output_matches_a_train_fitted_pipeline(self):
        out = cp.transform_with_pipeline(self.pipeline, self.X_test)
        # Nếu hàm bị mutate thành refit, cột nào cũng được scale lại theo Test
        # nên kết quả khác hẳn: median lệch, giá trị bị kéo về ~0.
        expected = self.pipeline.transform(self.X_test)
        np.testing.assert_allclose(out, expected)

    def test_transform_helper_output_is_not_centred_on_test(self):
        """Giá trị transform phải bám theo thang đo của Train, không phải của Test."""
        out = cp.transform_with_pipeline(self.pipeline, self.X_test)
        self.assertGreater(np.abs(out).max(), 1.0,
                           "output bị scale lại theo Test — tức đã refit")

    def test_transform_helper_is_callable_repeatedly_without_drift(self):
        first = cp.transform_with_pipeline(self.pipeline, self.X_test)
        second = cp.transform_with_pipeline(self.pipeline, self.X_test)
        np.testing.assert_array_equal(first, second)


class B9ChronologicalSplitIsNotSilent(unittest.TestCase):
    """
    MAJOR M3/M7 — `chronological_split()` âm thầm bỏ hàng `NaT` và không kiểm tra
    thứ tự. Mất dòng trong split thời gian là mất dữ liệu không có dấu vết.
    """

    def _frame(self, n=48, start="2026-01-01 00:00"):
        ts = pd.date_range(start=start, periods=n, freq="h", tz=TZ)
        return pd.DataFrame({
            "timestamp": ts,
            "pm10": np.linspace(10.0, 30.0, n),
            "pm25": np.linspace(8.0, 40.0, n),
        })

    CUT = pd.Timestamp("2026-01-01 20:00", tz=TZ)

    def test_split_rejects_nat_instead_of_dropping_rows(self):
        df = self._frame(48)
        df.loc[10, "timestamp"] = pd.NaT
        with self.assertRaises((ValueError, AssertionError)) as ctx:
            cp.chronological_split(df, self.CUT)
        msg = str(ctx.exception)
        # Phải là thông báo NaT, không phải thông báo "không tăng dần": NaT cũng
        # phá vỡ monotonicity, nên nếu chỉ kiểm "timestamp" thì test vẫn xanh khi
        # lớp kiểm chứng NaT bị xoá — đúng loại mutation sống sót.
        self.assertIn("NaT", msg)
        self.assertIn("timestamp", msg.lower())

    def test_split_rejects_rows_out_of_chronological_order(self):
        df = self._frame(48).iloc[::-1].reset_index(drop=True)
        with self.assertRaises((ValueError, AssertionError)) as ctx:
            cp.chronological_split(df, self.CUT)
        self.assertIn("tăng dần", str(ctx.exception).lower())

    def test_split_never_loses_a_single_row(self):
        df = self._frame(48)
        tr, te = cp.chronological_split(df, self.CUT)
        self.assertEqual(len(tr) + len(te), len(df))

    def test_split_is_strictly_disjoint_in_time(self):
        df = self._frame(48)
        tr, te = cp.chronological_split(df, self.CUT)
        self.assertLess(tr["timestamp"].max(), te["timestamp"].min())

    def test_sort_by_time_exists_and_sorts(self):
        """Docstring từng tham chiếu `sort_by_time()` — hàm đó không tồn tại."""
        df = self._frame(48).iloc[::-1].reset_index(drop=True)
        out = cp.sort_by_time(df)
        self.assertTrue(out["timestamp"].is_monotonic_increasing)
        self.assertEqual(len(out), len(df))
        # Phải trả về bản sao, không mutate input.
        self.assertFalse(df["timestamp"].is_monotonic_increasing)


class B10CyclicalFeaturesRefuseUnusableTimestamps(unittest.TestCase):
    """
    MAJOR M4 — `add_cyclical_time_features()` biến `NaT` thành 4 cột NaN. Nhánh
    `cyc` là `passthrough`, không có imputer, nên NaN đi thẳng vào ma trận và
    `RobustScaler` phía sau sẽ âm thầm biến NaN thành 0.
    """

    def test_cyclical_features_reject_nat(self):
        ts = pd.date_range("2026-01-01", periods=10, freq="h", tz=TZ).to_series()
        ts.iloc[3] = pd.NaT
        df = pd.DataFrame({"timestamp": ts.to_numpy()})
        with self.assertRaises((ValueError, AssertionError)) as ctx:
            cp.add_cyclical_time_features(df)
        self.assertIn("timestamp", str(ctx.exception).lower())


class B11ExportIsAtomicAndRefusesSilentOverwrite(unittest.TestCase):
    """
    MAJOR M8 — `export_to_parquet()` ghi thẳng vào đích rồi mới validate, nên
    validation fail để lại một file hỏng ở đường dẫn artifact; và ghi đè file
    đã tồn tại không cảnh báo, làm mất dấu vết chạy trước.
    """

    def setUp(self):
        import tempfile as _tf

        self._tmp = _tf.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.df = _wind_frame(20)

    def tearDown(self):
        self._tmp.cleanup()

    def test_export_refuses_to_overwrite_without_permission(self):
        out = self.tmp / "air_pollution_final.parquet"
        cp.export_to_parquet(self.df, out)
        self.assertTrue(out.exists())
        with self.assertRaises(FileExistsError):
            cp.export_to_parquet(self.df, out)
        # Bản cũ vẫn còn nguyên.
        self.assertEqual(len(pd.read_parquet(out)), len(self.df))

    def test_export_allows_explicit_overwrite(self):
        out = self.tmp / "air_pollution_final.parquet"
        cp.export_to_parquet(self.df, out)
        cp.export_to_parquet(self.df.head(5), out, overwrite=True)
        self.assertEqual(len(pd.read_parquet(out)), 5)

    def test_failed_validation_leaves_the_destination_untouched_and_no_temp_behind(self):
        """
        Bản gốc ghi thẳng vào đích rồi mới validate — validation fail để lại một
        artifact hỏng ngay tại đường dẫn chính. Nay ghi file tạm, validate, rồi
        mới `os.replace`, nên đích giữ nguyên trạng thái trước đó.
        """
        out = self.tmp / "air_pollution_final.parquet"
        good = _wind_frame(7)
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        # Buộc validation read-back thất bại: read trả về frame lệch schema.
        corrupt = good.head(3).rename(columns={"pm10": "pm10_renamed"})
        with unittest.mock.patch.object(
            cp.pd, "read_parquet", return_value=corrupt
        ):
            with self.assertRaises(AssertionError):
                cp.export_to_parquet(self.df, out, overwrite=True)

        self.assertEqual(out.read_bytes(), before, "file đích bị thay bằng bản hỏng")
        leftovers = list(self.tmp.glob("*.tmp"))
        self.assertEqual(leftovers, [], f"file tạm sót lại: {leftovers}")

    # --- Ba assert read-back phải bắt được TỪNG điều kiện một ------------------
    #
    # Test trên dùng `corrupt = good.head(3).rename(...)` — frame hỏng lệch
    # ĐỒNG THỜI cả số dòng lẫn tên cột, nên xoá bất kỳ assert nào trong ba
    # assert read-back thì assert còn lại vẫn bắt được. Ba test dưới đây mỗi
    # test làm hỏng ĐÚNG MỘT thuộc tính, để từng phải tự giữ mình.

    def test_readback_row_count_assert_fires_on_its_own(self):
        """Chỉ sai SỐ DÒNG — tên cột và dtype đều đúng.

        Frame truyền vào `export_to_parquet` phải là CHÍNH frame mà mock trả
        về, nếu không assert số dòng sẽ bắt trước và test không còn kiểm chứng
        điều tên mình.
        """
        good = _wind_frame(8)
        out = self.tmp / "rowcount.parquet"
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        short = good.head(3)
        self.assertEqual(list(short.columns), list(good.columns))
        with unittest.mock.patch.object(cp.pd, "read_parquet", return_value=short):
            with self.assertRaises(AssertionError) as ctx:
                cp.export_to_parquet(good, out, overwrite=True)
        self.assertIn("row count", str(ctx.exception).lower())
        self.assertEqual(out.read_bytes(), before)
        self.assertEqual(list(self.tmp.glob("*.tmp")), [])

    def test_readback_schema_assert_fires_on_its_own(self):
        """Chỉ sai TÊN CỘT — số dòng và dtype giữ nguyên."""
        good = _wind_frame(8)
        out = self.tmp / "schema.parquet"
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        # Ghi `good` (tên cột gốc); read-back trả về frame đã đổi tên cột.
        renamed = good.rename(columns={"pm10": "pm10_renamed"})
        self.assertEqual(len(renamed), len(good), "fixture phải giữ nguyên số dòng")
        with unittest.mock.patch.object(cp.pd, "read_parquet", return_value=renamed):
            with self.assertRaises(AssertionError) as ctx:
                cp.export_to_parquet(good, out, overwrite=True)
        self.assertIn("schema", str(ctx.exception).lower())
        self.assertEqual(out.read_bytes(), before)

    def test_readback_dtype_assert_fires_on_its_own(self):
        """Chỉ sai KIỂU DỮ LIỆU — số dòng và tên cột giữ nguyên.

        Đây là assert bắt được hỏng hóc mà hai assert kia bỏ lọt: Parquet có
        thể đổi bool/int khi round-trip mà không đổi số dòng hay tên cột, làm
        hỏng ký hiệu cờ chẩn đoán mà không ai nhận ra.
        """
        good = _wind_frame(8)
        out = self.tmp / "dtype.parquet"
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        # Ghi `good` (float64); read-back trả về bản float32.
        recast = good.copy()
        recast["pm25"] = recast["pm25"].astype("float32")   # float64 -> float32
        self.assertEqual(len(recast), len(good))
        self.assertEqual(list(recast.columns), list(good.columns))
        with unittest.mock.patch.object(cp.pd, "read_parquet", return_value=recast):
            with self.assertRaises(AssertionError) as ctx:
                cp.export_to_parquet(good, out, overwrite=True)
        self.assertIn("dtype", str(ctx.exception).lower())
        self.assertEqual(out.read_bytes(), before)


class B12FreezeAndLog1pAreHonest(unittest.TestCase):
    """
    MAJOR — `freeze_dataset()` báo `station_count=0` khi không có cột trạm
    (khẳng định sai sự thật), và mặc định nuốt cả cột chuỗi lẫn cờ phái sinh
    target. `evaluate_log1p_transform()` im lặng sinh NaN cho target âm.
    """

    def test_freeze_reports_none_when_station_column_is_absent(self):
        df = _wind_frame(10).drop(columns=["station_id"])
        info = cp.freeze_dataset(df)
        self.assertIsNone(info.station_count)

    def test_freeze_default_features_are_numeric_and_exclude_the_target_derived_flag(self):
        df = _wind_frame(10).assign(
            pm25_was_missing=0, is_high_humidity_fog=1, location="Ha Noi"
        )
        info = cp.freeze_dataset(df)
        self.assertNotIn("location", info.feature_columns)
        self.assertNotIn("station_id", info.feature_columns)
        self.assertNotIn(cp.TARGET_CANDIDATE, info.feature_columns)

    def test_log1p_refuses_negative_targets_instead_of_returning_nan(self):
        y = pd.Series([1.0, 2.0, -0.5, 3.0])
        with self.assertRaises(ValueError) as ctx:
            cp.evaluate_log1p_transform(y)
        self.assertIn("âm", str(ctx.exception))

    def test_log1p_reports_how_many_observations_it_used(self):
        y = pd.Series([1.0, 2.0, np.nan, 3.0, 40.0])
        out = cp.evaluate_log1p_transform(y)
        self.assertEqual(out["n_observations"], 4)
        self.assertEqual(out["n_negative"], 0)
        np.testing.assert_allclose(
            out["log1p_values"].to_numpy(), np.log1p(y.dropna().to_numpy())
        )


if __name__ == "__main__":
    warnings.simplefilter("error", FutureWarning)
    unittest.main(verbosity=2)
