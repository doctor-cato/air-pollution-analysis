from __future__ import annotations

import sys
import unittest
import unittest.mock
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import cleaning_pipeline as cp

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

    def setUp(self):
        self.air = _wind_frame(400, level=0.0)
        self.wx = _wx_frame(400, level=0.0)

    def test_guard_rejects_a_random_split(self):
        from sklearn.model_selection import train_test_split

        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = train_test_split(X, test_size=0.3, random_state=42)

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

    def test_guard_refuses_to_certify_without_the_chronology_layer(self):
        from sklearn.model_selection import train_test_split

        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = train_test_split(X, test_size=0.3, random_state=42)

        pipeline = cp.build_preprocessing_pipeline(feats, [])
        pipeline.fit(X_tr)
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(pipeline, X_train=X_tr, X_test=X_te)
        message = str(ctx.exception)
        self.assertIn("BẮT BUỘC", message)
        self.assertIn("random split", message)

    def test_explicit_opt_out_still_warns_loudly(self):
        from sklearn.model_selection import train_test_split

        merged = cp.merge_air_weather(self.air, self.wx)
        feats = ["pm10", "temperature"]
        X = merged[feats]
        X_tr, X_te = train_test_split(X, test_size=0.3, random_state=42)

        pipeline = cp.build_preprocessing_pipeline(feats, [])
        pipeline.fit(X_tr)
        with self.assertLogs("src.cleaning_pipeline", level="WARNING") as logs:
            cp.validate_no_leakage(
                pipeline, X_train=X_tr, X_test=X_te, verify_chronology=False
            )
        self.assertTrue(
            any("THỨ TỜ THỜI GIAN" in m or "THỨ TỰ THỜI GIAN" in m
                for m in logs.output),
            f"phải cảnh báo lớp thứ tự thời gian đang bị tắt; thấy: {logs.output}",
        )

    def test_guard_rejects_half_passed_timestamps(self):
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
        pipeline.fit(self.X_train)
        num = pipeline.named_steps["preprocessor"].named_transformers_["num"]
        num.named_steps["scaler"].fit(self.X_test)
        with self.assertRaises(AssertionError) as ctx:
            cp.validate_no_leakage(
                pipeline, X_train=self.X_train, X_test=self.X_test,
                verify_chronology=False,
            )
        self.assertIn("scaler", str(ctx.exception).lower())

    def test_guard_rejects_a_whole_pipeline_fitted_on_test(self):
        pipeline = cp.build_preprocessing_pipeline(self.feats, [])
        pipeline.fit(self.X_test)
        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(
                pipeline, X_train=self.X_train, X_test=self.X_test,
                verify_chronology=False,
            )


class B3EveryTransformerIsChecked(unittest.TestCase):

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
        pre.named_transformers_["cyc"].fit(X_test)

        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(pipeline, X_train=X_train, X_test=X_test,
                                   verify_chronology=False)

    def test_guard_covers_a_second_branch_over_a_different_column_set(self):
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
        pre.named_transformers_["cyc"].fit(X_test)
        with self.assertRaises(AssertionError):
            cp.validate_no_leakage(pipeline, X_train=X_train, X_test=X_test,
                                   verify_chronology=False)


class B4ArgumentOrderCannotBeSwapped(unittest.TestCase):

    def test_guard_rejects_swapped_positional_arguments(self):
        X_train = pd.DataFrame({"pm10": np.linspace(1, 10, 100)})
        X_test = pd.DataFrame({"pm10": np.linspace(500, 509, 100)})
        pipeline = cp.build_preprocessing_pipeline(["pm10"], [])
        pipeline.fit(X_test)
        with self.assertRaises(TypeError):
            cp.validate_no_leakage(pipeline, X_test, X_train)


class B5TargetIsNeverADefaultFeature(unittest.TestCase):

    def test_default_numeric_features_exclude_the_target(self):
        self.assertNotIn("pm25", cp.NUMERIC_FEATURES)
        self.assertNotIn(cp.TARGET_CANDIDATE, cp.NUMERIC_FEATURES)

    def test_builder_rejects_the_target_explicitly(self):
        with self.assertRaises(ValueError) as ctx:
            cp.build_preprocessing_pipeline(numeric_features=["pm25", "pm10"],
                                           cyclical_features=[])
        self.assertIn("target", str(ctx.exception).lower())

    def test_builder_rejects_the_target_in_the_cyclical_list_too(self):
        with self.assertRaises(ValueError) as ctx:
            cp.build_preprocessing_pipeline(numeric_features=["pm10"],
                                           cyclical_features=["pm25"])
        self.assertIn("target", str(ctx.exception).lower())

    def test_builder_rejects_duplicate_numeric_columns(self):
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

    def test_merge_rejects_weather_that_does_not_overlap_at_all(self):
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(10, start="2030-01-01 00:00")
        with self.assertRaises((AssertionError, ValueError)) as ctx:
            cp.merge_air_weather(air, wx)
        self.assertIn("nan", str(ctx.exception).lower())

    def test_merge_rejects_weather_shifted_out_of_the_window(self):
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(10, start="2026-01-02 00:00")
        with self.assertRaises((AssertionError, ValueError)):
            cp.merge_air_weather(air, wx)

    def test_merge_warns_when_coverage_is_partial(self):
        air = _wind_frame(10, start="2026-01-01 00:00")
        wx = _wx_frame(6, start="2026-01-01 00:00")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            merged = cp.merge_air_weather(air, wx)
        self.assertEqual(len(merged), len(air))
        self.assertTrue(any("coverage" in str(w.message).lower() or
                            "khớp" in str(w.message) for w in caught))

    def test_merge_rejects_colliding_column_names(self):
        air = _wind_frame(6).assign(pm25_was_missing=0)
        wx = _wx_frame(6).assign(pm25_was_missing=1)
        with self.assertRaises((AssertionError, ValueError)) as ctx:
            cp.merge_air_weather(air, wx)
        self.assertIn("pm25_was_missing", str(ctx.exception))


class B7TargetDerivedFlagIsNotAFeature(unittest.TestCase):

    def test_flag_is_declared_target_derived(self):
        self.assertIn("pm25_was_missing", cp.TARGET_DERIVED_FLAGS)
        self.assertNotIn("pm25_was_missing", cp.DIAGNOSTIC_FEATURES)

    def test_allowed_diagnostic_features_exclude_only_the_target_derived_one(self):
        self.assertIn("pm25_was_stuck", cp.DIAGNOSTIC_FEATURES)
        self.assertNotIn("is_high_humidity_fog", cp.DIAGNOSTIC_FEATURES)
        self.assertIn("is_high_humidity_fog", cp.NON_PREDICTIVE_FLAGS)

    def test_the_two_flag_groups_stay_disjoint(self):
        self.assertEqual(
            set(cp.TARGET_DERIVED_FLAGS) & set(cp.NON_PREDICTIVE_FLAGS), set()
        )
        self.assertNotIn(
            "pm25_was_missing", cp.NON_PREDICTIVE_FLAGS,
            "pm25_was_missing rò rỉ target, không phải chỉ thiếu tín hiệu",
        )

    def test_the_leak_is_actually_deterministic(self):
        air = _wind_frame(300)
        air.loc[air.index[::7], "pm25"] = np.nan
        air["pm25_was_missing"] = air["pm25"].isna().astype(int)
        med = float(np.nanmedian(air["pm25"]))
        filled = air["pm25"].fillna(med)
        flag = air["pm25_was_missing"].astype(bool)
        self.assertGreater(int(flag.sum()), 0)
        self.assertEqual(int(((filled == med) & flag).sum()), int(flag.sum()))


class B8TransformNeverRefits(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(11)
        self.feats = ["pm10", "temperature"]
        self.X_train = pd.DataFrame({
            "pm10": rng.normal(30.0, 4.0, 300),
            "temperature": rng.normal(22.0, 2.0, 300),
        })
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
        expected = self.pipeline.transform(self.X_test)
        np.testing.assert_allclose(out, expected)

    def test_transform_helper_output_is_not_centred_on_test(self):
        out = cp.transform_with_pipeline(self.pipeline, self.X_test)
        self.assertGreater(np.abs(out).max(), 1.0,
                           "output bị scale lại theo Test — tức đã refit")

    def test_transform_helper_is_callable_repeatedly_without_drift(self):
        first = cp.transform_with_pipeline(self.pipeline, self.X_test)
        second = cp.transform_with_pipeline(self.pipeline, self.X_test)
        np.testing.assert_array_equal(first, second)


class B9ChronologicalSplitIsNotSilent(unittest.TestCase):

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
        df = self._frame(48).iloc[::-1].reset_index(drop=True)
        out = cp.sort_by_time(df)
        self.assertTrue(out["timestamp"].is_monotonic_increasing)
        self.assertEqual(len(out), len(df))
        self.assertFalse(df["timestamp"].is_monotonic_increasing)


class B10CyclicalFeaturesRefuseUnusableTimestamps(unittest.TestCase):

    def test_cyclical_features_reject_nat(self):
        ts = pd.date_range("2026-01-01", periods=10, freq="h", tz=TZ).to_series()
        ts.iloc[3] = pd.NaT
        df = pd.DataFrame({"timestamp": ts.to_numpy()})
        with self.assertRaises((ValueError, AssertionError)) as ctx:
            cp.add_cyclical_time_features(df)
        self.assertIn("timestamp", str(ctx.exception).lower())


class B11ExportIsAtomicAndRefusesSilentOverwrite(unittest.TestCase):

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
        self.assertEqual(len(pd.read_parquet(out)), len(self.df))

    def test_export_allows_explicit_overwrite(self):
        out = self.tmp / "air_pollution_final.parquet"
        cp.export_to_parquet(self.df, out)
        cp.export_to_parquet(self.df.head(5), out, overwrite=True)
        self.assertEqual(len(pd.read_parquet(out)), 5)

    def test_failed_validation_leaves_the_destination_untouched_and_no_temp_behind(self):
        out = self.tmp / "air_pollution_final.parquet"
        good = _wind_frame(7)
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        corrupt = good.head(3).rename(columns={"pm10": "pm10_renamed"})
        with unittest.mock.patch.object(
            cp.pd, "read_parquet", return_value=corrupt
        ):
            with self.assertRaises(AssertionError):
                cp.export_to_parquet(self.df, out, overwrite=True)

        self.assertEqual(out.read_bytes(), before, "file đích bị thay bằng bản hỏng")
        leftovers = list(self.tmp.glob("*.tmp"))
        self.assertEqual(leftovers, [], f"file tạm sót lại: {leftovers}")


    def test_readback_row_count_assert_fires_on_its_own(self):
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
        good = _wind_frame(8)
        out = self.tmp / "schema.parquet"
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        renamed = good.rename(columns={"pm10": "pm10_renamed"})
        self.assertEqual(len(renamed), len(good), "fixture phải giữ nguyên số dòng")
        with unittest.mock.patch.object(cp.pd, "read_parquet", return_value=renamed):
            with self.assertRaises(AssertionError) as ctx:
                cp.export_to_parquet(good, out, overwrite=True)
        self.assertIn("schema", str(ctx.exception).lower())
        self.assertEqual(out.read_bytes(), before)

    def test_readback_dtype_assert_fires_on_its_own(self):
        good = _wind_frame(8)
        out = self.tmp / "dtype.parquet"
        cp.export_to_parquet(good, out)
        before = out.read_bytes()

        recast = good.copy()
        recast["pm25"] = recast["pm25"].astype("float32")
        self.assertEqual(len(recast), len(good))
        self.assertEqual(list(recast.columns), list(good.columns))
        with unittest.mock.patch.object(cp.pd, "read_parquet", return_value=recast):
            with self.assertRaises(AssertionError) as ctx:
                cp.export_to_parquet(good, out, overwrite=True)
        self.assertIn("dtype", str(ctx.exception).lower())
        self.assertEqual(out.read_bytes(), before)


class B12FreezeAndLog1pAreHonest(unittest.TestCase):

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
