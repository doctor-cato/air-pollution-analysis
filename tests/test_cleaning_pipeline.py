"""
Unit tests cho src/cleaning_pipeline.py (Issue #7).

Kiểm thử độc lập, không phụ thuộc #5/#6.
"""

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from src.cleaning_pipeline import (
    add_cyclical_time_features,
    chronological_split,
    build_preprocessing_pipeline,
    evaluate_log1p_transform,
    export_to_parquet,
    freeze_dataset,
    merge_air_weather,
    validate_no_leakage,
    NUMERIC_FEATURES,
    CYCLICAL_FEATURES,
    TARGET_CANDIDATE,
)


class TestCyclicalTimeFeatures(unittest.TestCase):
    """Test cho add_cyclical_time_features()."""

    def setUp(self):
        self.df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=24, freq="h"),
        })

    def test_adds_four_columns(self):
        result = add_cyclical_time_features(self.df)
        for col in CYCLICAL_FEATURES:
            self.assertIn(col, result.columns)

    def test_hour_sin_correct(self):
        result = add_cyclical_time_features(self.df)
        hour_0 = result.iloc[0]
        self.assertAlmostEqual(hour_0["hour_sin"], 0.0, places=5)
        self.assertAlmostEqual(hour_0["hour_cos"], 1.0, places=5)

    def test_hour_sin_at_6am(self):
        result = add_cyclical_time_features(self.df)
        hour_6 = result.iloc[6]
        self.assertAlmostEqual(hour_6["hour_sin"], 1.0, places=5)
        self.assertAlmostEqual(hour_6["hour_cos"], 0.0, places=5)

    def test_month_sin_correct(self):
        result = add_cyclical_time_features(self.df)
        month_1 = result.iloc[0]
        # Tháng 1: sin(2π * 1 / 12) = sin(π/6) = 0.5
        self.assertAlmostEqual(month_1["month_sin"], 0.5, places=5)
        # Tháng 1: cos(2π * 1 / 12) = cos(π/6) ≈ 0.866
        self.assertAlmostEqual(month_1["month_cos"], np.sqrt(3)/2, places=5)

    def test_does_not_modify_original(self):
        original_cols = list(self.df.columns)
        add_cyclical_time_features(self.df)
        self.assertEqual(list(self.df.columns), original_cols)


class TestChronologicalSplit(unittest.TestCase):
    """Test cho chronological_split()."""

    def setUp(self):
        self.df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
            "value": range(100),
        })

    def test_split_correct(self):
        split_ts = pd.Timestamp("2024-01-03 00:00:00")
        train, test = chronological_split(self.df, split_ts)
        self.assertEqual(len(train), 48)
        self.assertEqual(len(test), 52)

    def test_no_temporal_leakage(self):
        split_ts = pd.Timestamp("2024-01-03 00:00:00")
        train, test = chronological_split(self.df, split_ts)
        self.assertLess(train["timestamp"].max(), test["timestamp"].min())

    def test_split_timestamp_out_of_range(self):
        with self.assertRaises(ValueError):
            chronological_split(self.df, pd.Timestamp("2023-01-01"))

    def test_split_timestamp_beyond_max(self):
        with self.assertRaises(ValueError):
            chronological_split(self.df, pd.Timestamp("2024-01-06 00:00:00"))


class TestBuildPreprocessingPipeline(unittest.TestCase):
    """Test cho build_preprocessing_pipeline()."""

    def test_returns_pipeline(self):
        from sklearn.pipeline import Pipeline
        pipeline = build_preprocessing_pipeline()
        self.assertIsInstance(pipeline, Pipeline)

    def test_numeric_features_exclude_target(self):
        self.assertNotIn(TARGET_CANDIDATE, NUMERIC_FEATURES)

    def test_cyclical_features_correct(self):
        self.assertEqual(len(CYCLICAL_FEATURES), 4)


class TestMergeAirWeather(unittest.TestCase):
    """Test cho merge_air_weather()."""

    def setUp(self):
        self.df_air = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "station_id": "ST01",
            "pm25": range(10),
        })
        self.df_weather = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "station_id": "ST01",
            "temperature": range(10, 20),
        })

    def test_merge_correct(self):
        merged = merge_air_weather(self.df_air, self.df_weather)
        self.assertEqual(len(merged), len(self.df_air))
        self.assertIn("temperature", merged.columns)

    def test_row_explosion_detected(self):
        df_weather_dup = pd.concat([self.df_weather, self.df_weather])
        with self.assertRaises(ValueError):
            merge_air_weather(self.df_air, df_weather_dup)

    def test_merge_without_station_id(self):
        df_air = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
            "pm25": range(5),
        })
        df_weather = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
            "temperature": range(5, 10),
        })
        merged = merge_air_weather(df_air, df_weather)
        self.assertEqual(len(merged), 5)


class TestExportToParquet(unittest.TestCase):
    """Test cho export_to_parquet()."""

    def test_export_and_readback(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "value": range(10),
        })
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            tmp_path = f.name
        try:
            export_to_parquet(df, tmp_path)
            df_readback = pd.read_parquet(tmp_path)
            self.assertEqual(len(df_readback), len(df))
            self.assertEqual(list(df_readback.columns), list(df.columns))
        finally:
            Path(tmp_path).unlink()


class TestFreezeDataset(unittest.TestCase):
    """Test cho freeze_dataset()."""

    def test_freeze_correct(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=10, freq="h"),
            "station_id": "ST01",
            "pm25": range(10),
        })
        info = freeze_dataset(df)
        self.assertEqual(info.row_count, 10)
        self.assertEqual(info.station_count, 1)
        self.assertEqual(info.timestamp_min, df["timestamp"].min())
        self.assertEqual(info.timestamp_max, df["timestamp"].max())


class TestValidateNoLeakage(unittest.TestCase):
    """Test cho validate_no_leakage()."""

    def test_pass_when_fit_on_train(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
            "feature": np.random.randn(100),
        })
        split_ts = pd.Timestamp("2024-01-03 00:00:00")
        train, test = chronological_split(df, split_ts)
        X_train = train[["feature"]]
        X_test = test[["feature"]]
        pipeline = build_preprocessing_pipeline(
            numeric_features=["feature"],
            cyclical_features=[],
        )
        pipeline.fit(X_train)
        validate_no_leakage(pipeline, X_train, X_test)

    def test_fail_when_fit_on_test(self):
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
            "feature": np.random.randn(100),
        })
        split_ts = pd.Timestamp("2024-01-03 00:00:00")
        train, test = chronological_split(df, split_ts)
        X_train = train[["feature"]]
        X_test = test[["feature"]]
        pipeline = build_preprocessing_pipeline(
            numeric_features=["feature"],
            cyclical_features=[],
        )
        pipeline.fit(X_test)  # Fit trên Test
        with self.assertRaises(AssertionError):
            validate_no_leakage(pipeline, X_train, X_test)


class TestEvaluateLog1pTransform(unittest.TestCase):
    """Test cho evaluate_log1p_transform()."""

    def test_returns_dict(self):
        y = pd.Series(np.random.lognormal(3, 1, 100))
        result = evaluate_log1p_transform(y)
        self.assertIn("original_skew", result)
        self.assertIn("log1p_skew", result)
        self.assertIn("original_kurtosis", result)
        self.assertIn("log1p_kurtosis", result)

    def test_log1p_reduces_skew(self):
        y = pd.Series(np.random.lognormal(3, 1, 1000))
        result = evaluate_log1p_transform(y)
        self.assertLess(abs(result["log1p_skew"]), abs(result["original_skew"]))


if __name__ == "__main__":
    unittest.main()
