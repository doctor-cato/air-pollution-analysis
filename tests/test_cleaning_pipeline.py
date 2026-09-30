"""
Unit tests cho `src/cleaning_pipeline.py` (Issue #7 — tiền xử lý chống rò rỉ).

Bổ trổ cho `tests/test_cleaning.py` (Issue #6). Toàn bộ test chạy offline và
tất định: không phụ thuộc mạng, không phụ thuộc `data/raw/`, seed cố định.

Trọng tâm của bộ test này là **chứng minh rò rỉ dữ liệu bị chặn**, không chỉ
kiểm tra pipeline chạy được. Ba test đầu là các test hồi quy: chúng sẽ FAIL
trên bản gốc của Issue #7 vì `validate_no_leakage()` chỉ kiểm tra "đã fit"
mà không so sánh với Train, và vì import `data_quality` thiếu tiền tố `src.`.
"""

from __future__ import annotations

import sys
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# Cho phép chạy `python -m unittest discover tests` từ thư mục gốc repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import cleaning_pipeline as cp  # noqa: E402
from src.cleaning import (  # noqa: E402
    assert_no_imputation,
    clean_air_quality,
    clean_weather,
    validate_cleaned_dataset,
)

TZ = "Asia/Ho_Chi_Minh"


def _frame(n_hours: int = 48, start: str = "2025-01-01 00:00") -> pd.DataFrame:
    """DataFrame giờ liên tục, múi giờ canonical, có đủ cột khí tượng."""
    ts = pd.date_range(start=start, periods=n_hours, freq="h", tz=TZ)
    return pd.DataFrame(
        {
            "timestamp": ts,
            "station_id": "STATION_A",
            "pm25": np.linspace(10.0, 40.0, n_hours),
            "pm10": np.linspace(15.0, 50.0, n_hours),
            "temperature": np.linspace(18.0, 26.0, n_hours),
            "relative_humidity": np.linspace(60.0, 95.0, n_hours),
            "wind_speed": np.full(n_hours, 3.0),
            "wind_direction": np.full(n_hours, 120.0),
            "precipitation": np.zeros(n_hours),
            "surface_pressure": np.full(n_hours, 1010.0),
        }
    )


def _air_frame(n_hours: int = 48, start: str = "2025-01-01 00:00") -> pd.DataFrame:
    """
    Frame ô nhiễm đúng Canonical Schema: timestamp + station_id + PM + cờ chẩn
    đoán, KHÔNG mang cột khí tượng thô.

    Hai lý do bỏ cột khí tượng:
      1. `attach_high_humidity_flag()` lấy độ ẩm từ tập khí tượng và cố tình
         không giữ lại trong artifact ô nhiễm.
      2. Schema thật (`data/interim/air_quality_canonical.parquet`) không có cột
         khí tượng nào, nên hai bảng ghép không trùng tên ngoài khóa. Fixture cũ
         để cả hai bảng mang `temperature`/`wind_speed`/... khiến merge sinh hậu
         tố `_x`/`_y` — chính là lỗi M2 mà `merge_air_weather()` nay chặn.
    """
    return _frame(n_hours, start).drop(
        columns=[
            "temperature",
            "relative_humidity",
            "wind_speed",
            "wind_direction",
            "precipitation",
            "surface_pressure",
        ]
    )


def _weather_frame(n_hours: int = 48, start: str = "2025-01-01 00:00") -> pd.DataFrame:
    """Frame khí tượng bề mặt: chỉ timestamp + các biến khí tượng, không có PM."""
    return _frame(n_hours, start).drop(columns=["station_id", "pm25", "pm10"])


class TestModuleImports(unittest.TestCase):
    """Regression: `src.data_quality` phải import được, không rơi về None."""

    def test_audit_functions_are_not_none(self):
        # Bản gốc dùng `from data_quality import ...` -> luôn ModuleNotFoundError
        # -> try/except đặt cả hai biến về None -> audit chết âm thầm.
        self.assertIsNotNone(
            cp.audit_dataframe,
            "audit_dataframe phải import được từ src.data_quality",
        )
        self.assertIsNotNone(cp.audit_six_dimensions)

    def test_run_preprocessing_audit_actually_runs(self):
        # Bản gốc ném ImportError với mọi input.
        report = cp.run_preprocessing_audit(_frame(12), dataset_name="unit_test")
        self.assertIn("summary_table", report)
        self.assertIn("six_dimensions", report)
        self.assertFalse(report["summary_table"].empty)

    def test_freeze_dataset_with_audit_default_path_works(self):
        # run_audit=True là mặc định -> trước đây luôn ném ImportError.
        info, audit = cp.freeze_dataset_with_audit(_frame(12))
        self.assertEqual(info.row_count, 12)
        self.assertIsNotNone(audit)
        self.assertIn("audit", info.additional_info)


class TestLeakageGuard(unittest.TestCase):
    """
    Kiểm chứng pipeline **thực sự** fit trên Train, không chỉ "đã fit".

    Feature dùng `pm10` chứ không phải `pm25`: `build_preprocessing_pipeline()`
    nay raise nếu target lọt vào danh sách feature (xem
    `tests/test_cleaning_pipeline_guards.py::B5TargetIsNeverADefaultFeature`).
    """

    def setUp(self):
        # Hai tập có phân phối khác nhau rõ rệt để phép so sánh có sức phân biệt.
        rng = np.random.default_rng(42)
        self.X_train = pd.DataFrame({"pm10": rng.normal(20.0, 5.0, 400)})
        self.X_test = pd.DataFrame({"pm10": rng.normal(90.0, 5.0, 200)})

    def _pipeline(self):
        return cp.build_preprocessing_pipeline(
            numeric_features=["pm10"], cyclical_features=[]
        )

    def test_guard_rejects_a_pipeline_fitted_on_test(self):
        pipeline = self._pipeline()
        pipeline.fit(self.X_test)  # SAI: fit trên Test
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(pipeline, X_train=self.X_train, X_test=self.X_test)
        self.assertIn("leakage", str(ctx.exception).lower())

    def test_guard_accepts_a_pipeline_fitted_on_train(self):
        pipeline = self._pipeline()
        pipeline.fit(self.X_train)  # ĐÚNG
        cp.validate_no_leakage(pipeline, X_train=self.X_train, X_test=self.X_test)

    def test_guard_rejects_untrained_pipeline(self):
        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(
                self._pipeline(), X_train=self.X_train, X_test=self.X_test
            )

    def test_guard_refuses_to_certify_an_indistinguishable_split(self):
        """Train và Test cùng phân phối thì không thể chứng minh gì."""
        same = self.X_train.copy()
        pipeline = self._pipeline()
        pipeline.fit(self.X_train)
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(pipeline, X_train=self.X_train, X_test=same)
        self.assertIn("phân biệt", str(ctx.exception))

    def test_guard_compares_only_the_columns_the_pipeline_learned(self):
        """
        Regression: imputer học trên TẬP CỘT đã chọn, nên phải so sánh trên đúng
        tập cột đó. Nếu so sánh với toàn bộ X_train sẽ lệch số phần tử và ném
        ValueError thay vì kết luận đúng.
        """
        rng = np.random.default_rng(42)
        wide_train = self.X_train.assign(
            temperature=rng.normal(22.0, 2.0, len(self.X_train)),
            wind_speed=rng.normal(3.0, 1.0, len(self.X_train)),
            precipitation=rng.normal(0.5, 0.3, len(self.X_train)),
        )
        wide_test = self.X_test.assign(
            temperature=rng.normal(30.0, 2.0, len(self.X_test)),
            wind_speed=rng.normal(9.0, 1.0, len(self.X_test)),
            precipitation=rng.normal(0.1, 0.1, len(self.X_test)),
        )
        pipeline = self._pipeline()
        pipeline.fit(wide_train)
        # Không ném lỗi, và không ném ValueError sai lệch kích thước.
        cp.validate_no_leakage(pipeline, X_train=wide_train, X_test=wide_test)

    def test_guard_reports_a_missing_column_clearly(self):
        pipeline = self._pipeline()
        pipeline.fit(self.X_train)
        without_column = self.X_test.drop(columns=["pm10"])
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(
                pipeline, X_train=self.X_train, X_test=without_column
            )
        self.assertIn("pm10", str(ctx.exception))

    def test_guard_requires_keyword_arguments(self):
        """Truyền X_train/X_test theo vị trí là lỗi ghi nhầm biến — phải ném TypeError."""
        pipeline = self._pipeline()
        pipeline.fit(self.X_train)
        with self.assertRaises(TypeError):
            cp.validate_no_leakage(pipeline, self.X_train, self.X_test)


class TestChronologicalSplit(unittest.TestCase):
    def setUp(self):
        self.df = _frame(48)

    def test_split_respects_the_cut_point(self):
        cut = pd.Timestamp("2025-01-02 00:00", tz=TZ)
        train, test = cp.chronological_split(self.df, cut)
        self.assertTrue((train["timestamp"] < cut).all())
        self.assertTrue((test["timestamp"] >= cut).all())
        self.assertEqual(len(train) + len(test), len(self.df))

    def test_split_has_no_temporal_overlap(self):
        cut = pd.Timestamp("2025-01-02 00:00", tz=TZ)
        train, test = cp.chronological_split(self.df, cut)
        self.assertLess(train["timestamp"].max(), test["timestamp"].min())
        self.assertEqual(len(set(train["timestamp"]) & set(test["timestamp"])), 0)

    def test_split_is_reproducible_not_random(self):
        cut = pd.Timestamp("2025-01-02 00:00", tz=TZ)
        a_train, a_test = cp.chronological_split(self.df, cut)
        b_train, b_test = cp.chronological_split(self.df, cut)
        pd.testing.assert_frame_equal(a_train, b_train)
        pd.testing.assert_frame_equal(a_test, b_test)

    def test_split_rejects_a_cut_point_outside_the_data(self):
        for bad in (
            pd.Timestamp("2020-01-01", tz=TZ),
            pd.Timestamp("2030-01-01", tz=TZ),
        ):
            with self.assertRaises(ValueError):
                cp.chronological_split(self.df, bad)

    def test_split_rejects_unsorted_input_instead_of_hiding_it(self):
        """
        Bản gốc chấp nhận dữ liệu đảo thứ tự rồi trả về `train` không tăng dần —
        assert "không rò rỉ" vẫn xanh vì split theo mốc chờ chứ không theo vị trí.
        Test cũ từng **ghim** hành vi sai này. Nay hàm từ chối, và người gọi muốn
        thì sort tường minh bằng `sort_by_time()`.
        """
        shuffled = self.df.iloc[::-1].reset_index(drop=True)
        cut = pd.Timestamp("2025-01-02 00:00", tz=TZ)
        with self.assertRaises(AssertionError) as ctx:
            cp.chronological_split(shuffled, cut)
        self.assertIn("tăng dần", str(ctx.exception))
        # Lối thoát tường minh vẫn cho ra kết quả đúng thứ tự.
        ordered = cp.sort_by_time(shuffled)
        train, _ = cp.chronological_split(ordered, cut)
        self.assertTrue(train["timestamp"].is_monotonic_increasing)


class TestPipelineIsFittedOnTrainOnly(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.X_train = pd.DataFrame(
            {
                "pm10": rng.normal(20.0, 5.0, 300),
                "temperature": rng.normal(22.0, 3.0, 300),
            }
        )
        # Test cố tình lệch phân phối mạnh + có NaN để lộ ra hành vi imputer.
        self.X_test = pd.DataFrame(
            {
                "pm10": np.concatenate([rng.normal(80.0, 5.0, 150), [np.nan] * 50]),
                "temperature": rng.normal(30.0, 3.0, 200),
            }
        )

    def test_imputer_median_comes_from_train_not_test(self):
        pipeline = cp.build_preprocessing_pipeline(
            numeric_features=["pm10", "temperature"], cyclical_features=[]
        )
        pipeline.fit(self.X_train)
        imputer = (
            pipeline.named_steps["preprocessor"]
            .named_transformers_["num"]
            .named_steps["imputer"]
        )
        self.assertAlmostEqual(
            float(imputer.statistics_[0]),
            float(np.median(self.X_train["pm10"])),
            places=9,
        )

    def test_transform_test_does_not_change_fitted_parameters(self):
        pipeline = cp.build_preprocessing_pipeline(
            numeric_features=["pm10", "temperature"], cyclical_features=[]
        )
        pipeline.fit(self.X_train)
        scaler = (
            pipeline.named_steps["preprocessor"]
            .named_transformers_["num"]
            .named_steps["scaler"]
        )
        before_center = scaler.center_.copy()
        before_scale = scaler.scale_.copy()
        pipeline.transform(self.X_test)
        np.testing.assert_array_equal(scaler.center_, before_center)
        np.testing.assert_array_equal(scaler.scale_, before_scale)

    def test_pipeline_drops_columns_it_was_not_asked_for(self):
        X = self.X_train.assign(target=99.0, station_id="STATION_A")
        pipeline = cp.build_preprocessing_pipeline(
            numeric_features=["pm10", "temperature"], cyclical_features=[]
        )
        pipeline.fit(X)
        out = pipeline.transform(self.X_test.assign(target=1.0))
        self.assertEqual(out.shape[1], 2)  # không chứa target / station_id

    def test_pipeline_output_is_finite_despite_nan_in_test(self):
        pipeline = cp.build_preprocessing_pipeline(
            numeric_features=["pm10", "temperature"], cyclical_features=[]
        )
        pipeline.fit(self.X_train)
        out = pipeline.transform(self.X_test)
        self.assertTrue(np.isfinite(out).all())


class TestCyclicalFeatures(unittest.TestCase):
    def test_features_stay_within_unit_circle(self):
        feats = cp.add_cyclical_time_features(_frame(24))
        for column in cp.CYCLICAL_FEATURES:
            self.assertTrue(feats[column].between(-1.0, 1.0).all(), column)

    def test_midnight_is_the_sine_origin(self):
        df = pd.DataFrame(
            {"timestamp": [pd.Timestamp("2025-01-01 00:00", tz=TZ)]}
        )
        feats = cp.add_cyclical_time_features(df)
        self.assertAlmostEqual(float(feats["hour_sin"].iloc[0]), 0.0, places=12)
        self.assertAlmostEqual(float(feats["hour_cos"].iloc[0]), 1.0, places=12)

    def test_sin_cos_are_quadrature(self):
        feats = cp.add_cyclical_time_features(_frame(24))
        for prefix in ("hour", "month"):
            total = feats[f"{prefix}_sin"] ** 2 + feats[f"{prefix}_cos"] ** 2
            np.testing.assert_allclose(total.to_numpy(), 1.0, atol=1e-12)

    def test_input_frame_is_not_mutated(self):
        df = _frame(6)
        before = df.copy()
        cp.add_cyclical_time_features(df)
        pd.testing.assert_frame_equal(df, before)


class TestMergeAirWeather(unittest.TestCase):
    def setUp(self):
        # Air mang PM + cờ chẩn đoán, weather mang biến khí tượng — không trùng
        # tên ngoài khóa `timestamp`, đúng Canonical Schema thật.
        self.air = _air_frame(24)
        self.weather = _weather_frame(24)

    def test_merge_on_timestamp_keeps_air_row_count(self):
        merged = cp.merge_air_weather(self.air, self.weather)
        self.assertEqual(len(merged), len(self.air))

    def test_merge_rejects_duplicate_keys(self):
        dup_weather = pd.concat([self.weather, self.weather], ignore_index=True)
        with self.assertRaises(ValueError):
            cp.merge_air_weather(self.air, dup_weather)

    def test_merge_rejects_a_second_weather_row_for_the_same_hour(self):
        """
        Một giờ có 2 bản ghi khí tượng là row explosion — phải bị chặn ngay ở
        kiểm tra khóa unique, không được chờ đến assert row count (assert đó
        không bao giờ bắt được gì khi `validate="1:1"` còn giữ nguyên).
        """
        exploding = pd.concat([self.weather, self.weather.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError) as ctx:
            cp.merge_air_weather(self.air, exploding)
        self.assertIn("không unique", str(ctx.exception))

    def test_row_count_assertions_are_present_in_the_source(self):
        """
        Issue #7 §Yêu cầu kỹ thuật chỉ định `assert len(df_merged) <= len(df_air)`
        và AC yêu cầu phép đó "được thiết lập và kiểm chứng". Phải có mặt trong mã —
        nhưng `<=` một mình là tautology, nên phải có thêm phép `==` mới thật sự bắt.

        Test này kiểm mã nguồn chứ không chạy merge: không tồn tại đầu vào nào làm
        `<=` fail khi `how="left"` + khoá unique + `validate="1:1"`, nên một test
        hành vi chỉ chứng minh "không bao giờ sai" chứ không chứng minh "có kiểm soát".
        """
        import inspect

        src = inspect.getsource(cp.merge_air_weather)
        self.assertIn("assert len(df_merged) <= len(df_air)", src)
        self.assertIn("assert len(df_merged) == len(df_air)", src)


class TestExportAndFreeze(unittest.TestCase):
    def test_export_round_trips_rows_columns_and_dtypes(self):
        df = _frame(12).assign(pm25_was_missing=False, is_high_humidity_fog=True)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "air_pollution_final.parquet"
            cp.export_to_parquet(df, out)
            back = pd.read_parquet(out)
        self.assertEqual(len(back), len(df))
        self.assertEqual(list(back.columns), list(df.columns))
        for column in df.columns:
            self.assertEqual(
                str(back[column].dtype), str(df[column].dtype), f"dtype lệch ở {column}"
            )

    def test_freeze_records_real_span_not_hardcoded_numbers(self):
        df = _frame(36)
        info = cp.freeze_dataset(df)
        self.assertEqual(info.row_count, 36)
        self.assertEqual(info.timestamp_min, df["timestamp"].min())
        self.assertEqual(info.timestamp_max, df["timestamp"].max())
        # Fixture chỉ có 1 trạm nên assert này tự tham chiếu. Gắn nó vào con
        # số đo được thay vì con số viết tay:
        self.assertEqual(info.station_count, df["station_id"].nunique())
        self.assertNotIn("timestamp", info.feature_columns)
        self.assertNotIn("station_id", info.feature_columns)
        self.assertNotIn("pm25", info.feature_columns)


class TestIntegrationWithIssueSixOutput(unittest.TestCase):
    """
    Issue #6 sinh ra hai cờ chẩn đoán đúng để Issue #7 không điền mù chúng.
    Không có test nào ở Issue #7 bảo vệ hợp đồng này — đây là chỗ để kiểm.
    """

    def setUp(self):
        # mkdtemp không tự dọn — dùng addCleanup để thư mục tạm không tích tụ.
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        air = _air_frame(48)
        weather = _weather_frame(48)
        # Cố tình tạo khối khuyết dài > 6 giờ và một lần nghịch đảo khí động học.
        air.loc[10:25, "pm25"] = np.nan
        air.loc[10:25, "pm10"] = np.nan
        air.loc[30, "pm25"] = 99.0
        air.loc[30, "pm10"] = 12.0
        # Giữ lại frame TRƯỚC khi làm sạch: `assert_no_imputation` chỉ có ý nghĩa
        # khi hai vế là hai trạng thái khác nhau. Truyền `self.cleaned` cho cả
        # hai vế (bản gốc) là tautology — hàm luôn trả về, test luôn xanh.
        self.air_raw = air.copy()
        self.cleaned, self.air_report = clean_air_quality(air, weather)
        self.cleaned_weather, _ = clean_weather(weather)

    def test_raw_humidity_column_never_leaks_into_the_air_artifact(self):
        """Cột độ ẩm thô phải rời khỏi artifact ô nhiễm — tích hợp khí tượng là việc của #7."""
        self.assertNotIn("relative_humidity", self.cleaned.columns)

    def test_air_frame_carrying_humidity_is_rejected_with_a_clear_message(self):
        """Regression: merge sẽ đổi tên thành _x/_y rồi `pop` ném KeyError mù."""
        polluted = _frame(48)
        with self.assertRaises(ValueError) as ctx:
            clean_air_quality(polluted, _weather_frame(48))
        self.assertIn("relative_humidity", str(ctx.exception))

    def test_issue6_output_carries_both_diagnostic_flags(self):
        for flag in ("pm25_was_missing", "is_high_humidity_fog"):
            self.assertIn(flag, self.cleaned.columns)
            self.assertIn(str(self.cleaned[flag].dtype), ("bool", "int64"))

    def test_prolonged_gap_is_flagged_not_imputed(self):
        flagged = self.cleaned["pm25_was_missing"].astype(bool)
        # Khối khuyết 16 giờ (10:00 → 01:00) vượt ngưỡng > 6 giờ nên phải được gắn cờ.
        self.assertEqual(int(flagged.sum()), 16)
        # Cờ báo hiệu khuyết, không phải đã được điền.
        self.assertTrue(
            self.cleaned.loc[flagged, "pm25"].isna().all(),
            "pm25_was_missing=1 mà pm25 lại có giá trị",
        )
        # Và mọi ô `NaN` KHÔNG được gắn cờ đều là khối khuyết đơn lẻ (1 giờ) —
        # cờ `pm25_was_missing` theo định nghĩa chỉ dành cho khối > 6 giờ.
        isolated = self.cleaned.loc[self.cleaned["pm25"].isna() & ~flagged]
        self.assertLessEqual(len(isolated), 2, "khối khuyết không gắn cờ quá dài")

    def test_issue6_output_does_not_impute_the_flagged_gap(self):
        """
        `assert_no_imputation` là chốt chặn cuối: không giá trị nào được bịa ra.

        Phải so frame TRƯỚC và SAU làm sạch. Bản gốc truyền `self.cleaned` cho
        cả hai vế — cùng một frame thì hàm luôn trả về và test luôn xanh, tức
        test không bảo vệ gì cả.
        """
        # Bảo đảm hai vế thực sự khác nhau — nếu không test là tautology.
        self.assertNotIn(
            "pm25_was_missing", self.air_raw.columns,
            "frame 'trước' phải là frame thô, chưa qua clean_air_quality()",
        )
        self.assertIn("pm25_was_missing", self.cleaned.columns)
        assert_no_imputation(self.air_raw, self.cleaned, ["pm25", "pm10"])

    def test_issue6_output_still_satisfies_issue7_pipeline(self):
        merged = cp.merge_air_weather(self.cleaned, self.cleaned_weather)
        self.assertEqual(len(merged), len(self.cleaned))
        validation = validate_cleaned_dataset(self.cleaned)
        self.assertTrue(validation["all_passed"])
        assert_no_imputation(self.air_raw, self.cleaned, ["pm25", "pm10"])

    def test_target_is_excluded_and_the_target_derived_flag_is_not_a_feature(self):
        """
        Hợp đồng feature của #7:

          - `pm25` là target nên không vào feature.
          - `pm25_was_missing` = `pm25.isna()` cũng không vào feature: `SimpleImputer`
            điền median cho đúng những hàng đó, nên mô hình học được quy tắc
            `flag == 1 => pm25 == median` và đúng 100%. Đây là rò rỉ target theo
            cấu trúc — không guard nào trong #7 bắt được, phải loại ở danh sách.
          - `is_high_humidity_fog` là điều kiện khí quyển nên vẫn hợp lệ.
        """
        features = cp.freeze_dataset(self.cleaned).feature_columns
        self.assertNotIn("pm25", features)
        for flag in cp.TARGET_DERIVED_FLAGS:
            self.assertNotIn(flag, features)
        self.assertIn("is_high_humidity_fog", features)


class TestLog1PDiagnostic(unittest.TestCase):
    def test_log1p_reduces_skew_on_a_right_tailed_series(self):
        rng = np.random.default_rng(42)
        y = pd.Series(rng.lognormal(mean=2.0, sigma=1.0, size=2000))
        result = cp.evaluate_log1p_transform(y)
        self.assertLess(result["log1p_skew"], result["original_skew"])
        self.assertEqual(len(result["log1p_values"]), len(y))

    def test_log1p_drops_na_before_computing(self):
        y = pd.Series([1.0, np.nan, 3.0, 4.0])
        result = cp.evaluate_log1p_transform(y)
        self.assertEqual(len(result["log1p_values"]), 3)


if __name__ == "__main__":
    warnings.simplefilter("error", FutureWarning)
    unittest.main(verbosity=2)
