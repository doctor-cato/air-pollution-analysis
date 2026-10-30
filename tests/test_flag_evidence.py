"""
Unit test cho `src/flag_evidence.py` (Issue #38).

VÌ SAO FILE NÀY TỒN TẠI
-----------------------
Trước Issue #38, `F = 16,78` / `p = 7,4·10⁻¹¹` chỉ nằm trong comment và chuỗi
hằng ở 6 chỗ; test duy nhất "bảo vệ" nó lại là `assertIn("F = 16,78", source)` —
xoá hẳn dòng số liệu và thay bằng câu mơ hồ thì test vẫn xanh.

Bộ test này thay thế bằng kiểm **hành vi**:

  * phép tính cho ra F / p / bậc tự do hợp lệ từ dữ liệu tổng hợp CÓ KIỂM SOÁT;
  * kết quả khớp con số tài liệu KHI dữ liệu thật có sẵn (bỏ qua nếu thiếu — repo
    không commit `data/`);
  * test phát hiện được khi công thức bị đổi sai (mô hình không tương tác, mùa
    gộp sai, đảo cờ, lọc NaN sai);
  * thiếu cột / thiếu nhóm / không đủ quan sát → lỗi tường minh, không trả 0;
  * `verify_claims.py` và `build_progress_report.py` thực sự GỌI hàm này chứ
    không chứa bản sao số liệu.

Toàn bộ test chạy offline và tất định.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

# Cho phép chạy `python -m unittest discover tests` từ thư mục gốc repo.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src import flag_evidence as fe  # noqa: E402

TZ = "Asia/Ho_Chi_Minh"


def _load_script(name: str):
    """Nạp một script trong `scripts/` như module (chúng không phải package)."""
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Khung dữ liệu tổng hợp CÓ THAM SỐ ĐIỀU KHIỂN
# ---------------------------------------------------------------------------


def _synthetic_frame(
    n_per_cell: int = 400,
    fog_effect: dict | None = None,
    noise: float = 1.0,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Dựng frame có hiệu ứng tương tác **đã biết trước** để kiểm chứng công thức.

    `fog_effect` ánh xạ mùa → chênh lệch PM2.5 giữa nhóm có cờ và không cờ. Với
    bộ dữ liệu này, hệ số tương tác và F-test đều phải ra con số lớn, và dấu của
    chênh lệch phải khớp đúng mùa — nếu công thức bị đảo hay gộp nhầm mùa thì
    test đỏ.

    Mỗi mùa chiếm đúng `2 × n_per_cell` giờ liên tiếp tính từ ĐẦU mùa, nên với
    `n_per_cell ≤ 800` khối không tràn sang mùa kế tiếp (3 tháng ≈ 2.200 giờ).
    """
    effects = {"Dong": 3.0, "Xuan": -9.0, "He": 0.3, "Thu": -3.0}
    effects.update(fog_effect or {})

    # Mỗi mùa bắt đầu ở tháng đầu của mùa để `add_season()` gán đúng.
    months = {"Dong": 1, "Xuan": 3, "He": 6, "Thu": 9}
    rng = np.random.default_rng(seed)

    rows = []
    for season, month in months.items():
        start = pd.Timestamp(f"2025-{month:02d}-01 00:00", tz=TZ)
        hours = pd.date_range(start=start, periods=n_per_cell * 2, freq="h")
        for i, ts in enumerate(hours):
            fog = i % 2
            rows.append({
                "timestamp": ts,
                "pm25": 40.0 + effects[season] * fog + rng.normal(0, noise),
                "relative_humidity": 70.0 + 25.0 * fog + rng.normal(0, 1.0),
                "is_high_humidity_fog": fog,
            })
    return pd.DataFrame(rows)


class TestAddSeason(unittest.TestCase):
    def test_month_maps_to_the_documented_vietnamese_seasons(self):
        frame = pd.DataFrame({
            "timestamp": pd.to_datetime(
                [f"2025-{m:02d}-15 12:00" for m in range(1, 13)], utc=True
            ).tz_convert(TZ),
            "pm25": [40.0] * 12,
            "relative_humidity": [70.0] * 12,
            "is_high_humidity_fog": [0] * 12,
        })
        out = fe.add_season(frame)
        self.assertEqual(
            list(out["season"]),
            ["Dong", "Dong"] + ["Xuan"] * 3 + ["He"] * 3 + ["Thu"] * 3 + ["Dong"],
            "Đông = 12–2, Xuân = 3–5, Hè = 6–8, Thu = 9–11",
        )
        self.assertEqual(list(out["fog"]), [0] * 12)

    def test_missing_timestamp_column_fails_loudly(self):
        frame = pd.DataFrame({"pm25": [1.0]})
        with self.assertRaises(KeyError):
            fe.add_season(frame)

    def test_unparseable_timestamp_fails_loudly(self):
        frame = pd.DataFrame({
            "timestamp": [pd.Timestamp("2025-01-01 00:00", tz=TZ), pd.NaT],
            "pm25": [1.0, 2.0],
            "relative_humidity": [70.0, 70.0],
            "is_high_humidity_fog": [0, 0],
        })
        with self.assertRaises(ValueError):
            fe.add_season(frame)


class TestSelectAnalysisSample(unittest.TestCase):
    def test_missing_required_column_raises_key_error_naming_it(self):
        frame = _synthetic_frame(n_per_cell=10).drop(columns=["relative_humidity"])
        with self.assertRaises(KeyError) as ctx:
            fe.select_analysis_sample(frame)
        self.assertIn("relative_humidity", str(ctx.exception))

    def test_missing_flag_column_raises_key_error(self):
        frame = _synthetic_frame(n_per_cell=10).drop(columns=["is_high_humidity_fog"])
        with self.assertRaises(KeyError) as ctx:
            fe.select_analysis_sample(frame)
        self.assertIn("is_high_humidity_fog", str(ctx.exception))

    def test_rows_with_nan_are_dropped_not_imputed(self):
        frame = _synthetic_frame(n_per_cell=20)
        frame.loc[frame.index[:10], "pm25"] = np.nan
        frame.loc[frame.index[10:20], "relative_humidity"] = np.nan
        sample = fe.select_analysis_sample(frame)
        self.assertEqual(len(sample), len(frame) - 20)
        self.assertFalse(sample.isna().any().any())

    def test_empty_sample_raises_instead_of_returning_nan(self):
        frame = _synthetic_frame(n_per_cell=5)
        frame["pm25"] = np.nan
        with self.assertRaises(ValueError):
            fe.select_analysis_sample(frame)

    def test_thin_cell_raises_instead_of_being_silently_dropped(self):
        """Một ô fog × mùa quá mỏng thì mô hình không ước lượng được."""
        frame = _synthetic_frame(n_per_cell=3)
        drop = frame[(frame["timestamp"].dt.month == 6)
                     & (frame["is_high_humidity_fog"] == 1)].index[1:]
        frame = frame.drop(index=drop)
        with self.assertRaises(ValueError) as ctx:
            fe.select_analysis_sample(frame)
        self.assertIn("fog × mùa", str(ctx.exception))


def _drop_cell(frame: pd.DataFrame, season: str, fog: int) -> pd.DataFrame:
    """Xoá TRỌN một ô `season × fog` (không còn quan sát nào, khác với ô mỏng)."""
    labelled = fe.add_season(frame)
    return frame[~((labelled[fe.SEASON_COLUMN] == season)
                   & (labelled[fe.FOG_ALIAS] == fog))]


class TestMissingFogSeasonCells(unittest.TestCase):
    """
    Một ô `fog × mùa` bị THIẾU HOÀN TOÀN phải làm hỏng phép tính, không được
    lặng lẽ cho ra một F-test khác.

    Đây không phải lo xa. Trước khi có guard, xoá trọn ô `Đông × fog=1` (ô của
    mức tham chiếu) khiến ma trận thiết kế hạng thấp: statsmodels vẫn trả
    F = 3,73 và p = 0,054 — tức **kết luận ngược hẳn** so với F = 16,78 —
    kèm một `ValueWarning` trôi qua mà không ai đọc. `format_evidence_sentence()`
    sẽ in ra con số đó và `build_progress_report.py` sẽ xuất nó vào báo cáo.
    """

    def test_missing_non_reference_cell_raises(self):
        frame = _drop_cell(_synthetic_frame(), "He", 1)
        with self.assertRaises(ValueError) as ctx:
            fe.fog_flag_evidence(frame)
        message = str(ctx.exception)
        self.assertIn("Hè", message)
        self.assertIn("fog=1", message)

    def test_missing_reference_cell_raises(self):
        """Ô của mức tham chiếu mất thì phải báo lỗi, không trả F khác."""
        frame = _drop_cell(_synthetic_frame(), "Dong", 1)
        with self.assertRaises(ValueError) as ctx:
            fe.fog_flag_evidence(frame)
        self.assertIn("Đông", str(ctx.exception))

    def test_missing_whole_season_raises(self):
        frame = _synthetic_frame()
        labelled = fe.add_season(frame)
        frame = frame[labelled[fe.SEASON_COLUMN] != "He"]
        with self.assertRaises(ValueError) as ctx:
            fe.fog_flag_evidence(frame)
        self.assertIn("Hè", str(ctx.exception))

    def test_missing_cell_is_named_in_select_analysis_sample(self):
        frame = _drop_cell(_synthetic_frame(), "Thu", 0)
        with self.assertRaises(ValueError) as ctx:
            fe.select_analysis_sample(frame)
        self.assertIn("Thu", str(ctx.exception))

    def test_every_declared_cell_is_present_in_the_shipped_evidence(self):
        """Bằng chứng trả về phải phủ đủ 8 ô — không âm thầm thiếu ô nào."""
        evidence = fe.fog_flag_evidence(_synthetic_frame())
        expected = {
            f"{fe.SEASON_LABELS_VI[s]} × fog={f}"
            for s in fe.SEASON_DISPLAY_ORDER
            for f in (0, 1)
        }
        self.assertEqual(set(evidence["cell_counts"]), expected)
        self.assertTrue(all(n > 0 for n in evidence["cell_counts"].values()))


class TestModelIsWellFormed(unittest.TestCase):
    """F chỉ có nghĩa khi ma trận thiết kế đủ hạng và đủ 3 hệ số tương tác."""

    def test_design_matrix_has_full_rank(self):
        sample = fe.select_analysis_sample(_synthetic_frame())
        import statsmodels.formula.api as smf
        fit = smf.ols(fe.INTERACTION_FORMULA, data=sample).fit()
        exog = np.asarray(fit.model.exog)
        self.assertEqual(np.linalg.matrix_rank(exog), exog.shape[1])

    def test_all_three_interaction_coefficients_are_estimated(self):
        seasonal = fe.fog_flag_evidence(_synthetic_frame())["seasonal"]
        self.assertEqual(len(seasonal["interaction_terms"]), 3)
        self.assertEqual(seasonal["f_df_num"], 3)
        for name in seasonal["interaction_terms"]:
            self.assertIn("C(fog)[T.1]:C(season)[T.", name)

    def test_all_four_seasons_appear_in_the_result(self):
        evidence = fe.fog_flag_evidence(_synthetic_frame())
        self.assertEqual(set(evidence["season_counts"]),
                         {"Đông", "Xuân", "Hè", "Thu"})
        self.assertEqual(set(evidence["seasonal"]["raw_mean_difference"]),
                         {"Đông", "Xuân", "Hè", "Thu"})


class TestFogFlagEvidence(unittest.TestCase):
    """Kiểm chứng công thức trên dữ liệu tổng hợp có tham số điều khiển."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.frame = _synthetic_frame()
        cls.evidence = fe.fog_flag_evidence(cls.frame)

    def test_returns_a_well_formed_result(self):
        for key in ("n_rows_used", "marginal", "seasonal"):
            self.assertIn(key, self.evidence)
        for key in ("f_statistic", "f_p_value", "f_df_num", "f_df_denom",
                    "raw_mean_difference", "model_contrast", "welch",
                    "double_difference_dong_vs_xuan_he"):
            self.assertIn(key, self.evidence["seasonal"])

    def test_season_differences_match_the_planted_effects(self):
        """Chênh lệch theo mùa phải bám đúng tham số đã cấy vào dữ liệu."""
        raw = self.evidence["seasonal"]["raw_mean_difference"]
        planted = {"Đông": 3.0, "Xuân": -9.0, "Hè": 0.3, "Thu": -3.0}
        for season, expected in planted.items():
            self.assertAlmostEqual(
                raw[season], expected, delta=0.2,
                msg=f"{season}: điểm ước lượng lệch quá nhiễu so với tham số",
            )

    def test_double_difference_equals_dong_minus_pooled_xuan_he(self):
        seasonal = self.evidence["seasonal"]
        pooled = seasonal["pooled_xuan_he_difference"]
        expected = seasonal["raw_mean_difference"]["Đông"] - pooled
        self.assertAlmostEqual(
            seasonal["double_difference_dong_vs_xuan_he"], expected, places=10,
        )

    def test_f_statistic_is_positive_and_significant_for_a_planted_interaction(self):
        seasonal = self.evidence["seasonal"]
        self.assertGreater(seasonal["f_statistic"], 10.0)
        self.assertLess(seasonal["f_p_value"], 1e-6)

    def test_degrees_of_freedom_come_from_the_fitted_model(self):
        seasonal = self.evidence["seasonal"]
        self.assertEqual(seasonal["f_df_num"], 3,
                         "4 mùa → 3 hệ số tương tác được kiểm định đồng thời")
        self.assertEqual(seasonal["f_df_denom"], seasonal["n_obs"] - 8)
        self.assertEqual(seasonal["n_obs"], self.evidence["n_rows_used"])

    def test_interaction_terms_are_the_three_fog_by_season_coefficients(self):
        terms = self.evidence["seasonal"]["interaction_terms"]
        self.assertEqual(len(terms), 3)
        self.assertTrue(all("C(fog)[T.1]:C(season)[T." in t for t in terms))

    def test_reference_season_is_dong_so_main_effect_is_its_difference(self):
        seasonal = self.evidence["seasonal"]
        self.assertEqual(seasonal["reference_season"], "Đông")
        self.assertAlmostEqual(
            seasonal["model_contrast"]["Đông"]["estimate"],
            seasonal["raw_mean_difference"]["Đông"], places=6,
        )

    def test_marginal_corr_and_group_means_are_computed_not_hard_coded(self):
        marginal = self.evidence["marginal"]
        self.assertTrue(np.isfinite(marginal["corr_pm25_rh"]))
        # Nhóm có cờ phải thấp hơn nhóm không cờ ở mức marginal (hiệu ứng âm
        # trung bình vì Xuân/Thu âm mạnh hơn Đông dương).
        self.assertLess(marginal["mean_pm25_by_flag"][1],
                        marginal["mean_pm25_by_flag"][0])
        self.assertEqual(
            sum(marginal["n_pm25_by_flag"].values()),
            self.evidence["n_rows_used"],
        )

        # Nếu `corr` bị hard-code, đổi dữ liệu sẽ không làm nó đổi.
        uniform = fe.fog_flag_evidence(_synthetic_frame(
            fog_effect={"Dong": 30.0, "Xuan": 30.0, "He": 30.0, "Thu": 30.0}
        ))
        self.assertNotEqual(
            marginal["corr_pm25_rh"], uniform["marginal"]["corr_pm25_rh"],
        )

    def test_mutual_information_is_flagged_as_unverified(self):
        """MI KHÔNG được báo là đã xác minh, và phải in ra nhiều phương án."""
        marginal = self.evidence["marginal"]
        self.assertFalse(marginal["mutual_information_verified"])
        variants = marginal["mutual_information_variants"]
        self.assertGreaterEqual(len(variants), 4,
                                "phải in nhiều phương án ước lượng, không tự chọn")
        self.assertTrue(all(isinstance(v, float) for v in variants.values()))


class TestFormulaRegressions(unittest.TestCase):
    """Các lỗi công thức mà test phải BẮT ĐƯỢC (bằng chứng test có tác dụng)."""

    def test_no_interaction_model_gives_a_different_f_statistic(self):
        """Nếu ai đó đổi sang mô hình KHÔNG có tương tác, kết quả phải đổi."""
        correct = fe.fog_flag_evidence(_synthetic_frame())
        import statsmodels.formula.api as smf

        sample = fe.select_analysis_sample(_synthetic_frame())
        reduced = smf.ols("pm25 ~ C(fog) + C(season)", data=sample).fit()
        reduced_f = float(np.ravel(
            reduced.f_test([n for n in reduced.params.index if n != "Intercept"]).fvalue
        )[0])
        self.assertNotAlmostEqual(
            reduced_f, correct["seasonal"]["f_statistic"], places=3,
            msg="mô hình không tương tác phải cho F khác hẳn — nếu bằng nhau thì "
                "phép kiểm định đang không làm đúng việc",
        )

    def test_collapsing_the_seasons_is_rejected_not_silently_narrowed(self):
        """
        Còn hai mùa thay vì bốn thì F-test sẽ chỉ kiểm định 1 hệ số tương tác
        thay vì 3 — tức là **một phép kiểm định khác hẳn** vẫn mang tên
        `F(., .)`.

        Trước đây hàm âm thầm trả về `f_df_num = 1` và test "chứng minh" điều đó
        là hành vi. Nay phải ném lỗi: số hằng 16,78 / 7,4·10⁻¹¹ trong tài liệu
        được định nghĩa trên đúng bốn mùa, nên thiếu mùa là dữ liệu hỏng chứ
        không phải một phép tính khác.
        """
        two_seasons = _synthetic_frame()
        two_seasons = two_seasons[
            two_seasons["timestamp"].dt.month.isin([1, 2, 3, 4])
        ]
        with self.assertRaises(ValueError) as ctx:
            fe.fog_flag_evidence(two_seasons)
        message = str(ctx.exception)
        self.assertIn("Hè", message)
        self.assertIn("Thu", message)

    def test_all_four_seasons_still_yield_three_interaction_terms(self):
        seasonal = fe.fog_flag_evidence(_synthetic_frame())["seasonal"]
        self.assertEqual(seasonal["f_df_num"], 3)

    def test_inverting_the_flag_flips_the_sign_of_every_difference(self):
        """Đảo nghĩa cờ thì mọi chênh lệch theo mùa phải đổi dấu."""
        frame = _synthetic_frame()
        baseline = fe.fog_flag_evidence(frame)
        flipped = frame.assign(
            is_high_humidity_fog=1 - frame["is_high_humidity_fog"]
        )
        other = fe.fog_flag_evidence(flipped)
        for season, value in baseline["seasonal"]["raw_mean_difference"].items():
            self.assertAlmostEqual(
                other["seasonal"]["raw_mean_difference"][season], -value, places=6
            )

    def test_dropping_the_humidity_filter_changes_the_sample_size(self):
        """Lọc theo RH là một phần của định nghĩa — bỏ đi thì mẫu phải khác."""
        frame = _synthetic_frame(n_per_cell=50)
        frame.loc[frame.index[:25], "relative_humidity"] = np.nan
        evidence = fe.fog_flag_evidence(frame)
        self.assertEqual(evidence["n_rows_used"], len(frame) - 25)


class TestFormatting(unittest.TestCase):
    def test_sentence_numbers_come_from_the_evidence_not_the_source(self):
        evidence = fe.fog_flag_evidence(_synthetic_frame(n_per_cell=200))
        sentence = fe.format_evidence_sentence(evidence)
        f_value = evidence["seasonal"]["f_statistic"]
        self.assertIn(fe.format_number_vi(round(f_value, 2)), sentence)
        self.assertIn(fe.format_signed_vi(
            evidence["seasonal"]["raw_mean_difference"]["Xuân"]
        ), sentence)

    def test_sentence_changes_when_the_data_changes(self):
        """Nếu số liệu bị hard-code, đổi tham số dữ liệu sẽ không đổi câu này."""
        a = fe.format_evidence_sentence(
            fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -9.0}))
        )
        b = fe.format_evidence_sentence(
            fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -1.0}))
        )
        self.assertNotEqual(a, b)

    def test_vietnamese_number_helpers(self):
        self.assertEqual(fe.format_number_vi(-0.0364569, 4), "−0,0365")
        self.assertEqual(fe.format_int_vi(7495), "7.495")
        self.assertEqual(fe.format_signed_vi(2.7948), "+2,79")
        self.assertEqual(fe.format_signed_vi(-8.9095), "−8,91")
        self.assertEqual(fe.format_scientific_vi(7.38e-11), "7,4·10⁻¹¹")
        # Chuẩn hoá exponent: bỏ zero thừa và dấu trừ unicode (10⁻⁰⁸ → 10⁻⁸).
        self.assertEqual(fe.format_scientific_vi(1e-8), "1,0·10⁻⁸")
        self.assertEqual(fe.format_scientific_vi(2.5e-100, 2), "2,50·10⁻¹⁰⁰")
        self.assertEqual(fe.format_scientific_vi(1.5e8), "1,5·10⁸")


class TestDocumentedReproduction(unittest.TestCase):
    """
    Chạy trên dữ liệu THẬT của dự án nếu `data/interim/*.parquet` có sẵn.

    Repo KHÔNG commit `data/` (.gitignore), nên trên máy CI sạch các test này
    `skip`. Chúng tồn tại để người có dữ liệu chạy lại được đúng con số tài liệu,
    và để `verify_claims.py` không phải là nơi duy nhất tái lập được.
    """

    AIR = REPO_ROOT / "data" / "interim" / "air_quality_canonical.parquet"
    WEATHER = REPO_ROOT / "data" / "interim" / "weather_canonical.parquet"

    @classmethod
    def setUpClass(cls) -> None:
        if not (cls.AIR.exists() and cls.WEATHER.exists()):
            raise unittest.SkipTest(
                "Thiếu data/interim/*.parquet — chạy `python scripts/fetch_dataset.py`."
            )
        cls.evidence = fe.fog_flag_evidence(fe.build_analysis_frame(cls.AIR, cls.WEATHER))

    def test_sample_size(self):
        self.assertEqual(self.evidence["n_rows_used"], 7495)

    def test_marginal_numbers(self):
        marginal = self.evidence["marginal"]
        self.assertAlmostEqual(marginal["corr_pm25_rh"], -0.0365, places=4)
        self.assertAlmostEqual(marginal["mean_pm25_by_flag"][1], 41.65, places=2)
        self.assertAlmostEqual(marginal["mean_pm25_by_flag"][0], 44.75, places=2)
        self.assertEqual(marginal["n_pm25_by_flag"], {0: 5111, 1: 2384})

    def test_season_differences(self):
        raw = self.evidence["seasonal"]["raw_mean_difference"]
        for season, expected in (("Đông", 2.79), ("Xuân", -8.91),
                                 ("Hè", 0.28), ("Thu", -2.72)):
            self.assertAlmostEqual(raw[season], expected, places=2, msg=season)

    def test_f_test(self):
        seasonal = self.evidence["seasonal"]
        self.assertAlmostEqual(seasonal["f_statistic"], 16.78, places=2)
        self.assertAlmostEqual(seasonal["f_p_value"], 7.4e-11, delta=7.4e-12)
        self.assertEqual(seasonal["f_df_num"], 3)
        self.assertEqual(int(seasonal["f_df_denom"]), 7487)
        self.assertAlmostEqual(
            seasonal["double_difference_dong_vs_xuan_he"], 7.77, places=2
        )


class TestScriptsUseTheComputation(unittest.TestCase):
    """
    Hai script phải GỌI hàm tính, không chứa bản sao số liệu.

    Đây là điều kiện tiên quyết để Issue #38 không tái diễn: nếu ai đó xoá
    `report_flag_evidence` khỏi `verify_claims.py` hoặc thay lời gọi trong
    `build_progress_report.py` bằng một chuỗi hằng, các test này đỏ.
    """

    def test_verify_claims_registers_the_flag_claim_group(self):
        source = (REPO_ROOT / "scripts" / "verify_claims.py").read_text("utf-8")
        self.assertIn("flag_evidence", source)
        self.assertIn("def report_flag_evidence", source)
        self.assertIn("fog_claims(evidence)", source)

    def test_verify_claims_marks_mutual_information_unverifiable(self):
        source = (REPO_ROOT / "scripts" / "verify_claims.py").read_text("utf-8")
        self.assertIn("fog_mutual_information", source)
        self.assertIn("UNVERIFIABLE_CLAIMS", source)

    def test_verify_claims_reads_the_values_out_of_the_evidence(self):
        """Claim của `verify_claims.py` phải lấy giá trị từ `evidence`, không từ hằng.

        Nếu `compute` trả về hằng, đổi tham số dữ liệu sẽ không làm kết quả đổi và
        mọi MISMATCH sẽ bị bỏ sót.
        """
        vc = _load_script("verify_claims")
        strong = fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -9.0}))
        weak = fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -1.0}))
        strong_claim = {c.key: c for c in vc.fog_claims(strong)}["fog_interaction_f"]
        weak_claim = {c.key: c for c in vc.fog_claims(weak)}["fog_interaction_f"]

        self.assertNotEqual(
            strong_claim.compute(None), weak_claim.compute(None),
            "giá trị tái lập phải đến từ evidence",
        )

    def test_verify_claims_reports_mismatch_when_the_data_no_longer_matches(self):
        """`verify_claims.py` phải THẤT BẠI khi kết quả không còn khớp tài liệu."""
        vc = _load_script("verify_claims")
        real = fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -9.0}))
        tampered = fe.fog_flag_evidence(_synthetic_frame(fog_effect={"Xuan": -1.0}))
        key = "fog_interaction_f"
        strong_claims = {c.key: c for c in vc.fog_claims(real)}
        weak_claims = {c.key: c for c in vc.fog_claims(tampered)}

        # F của dữ liệu tổng hợp khác 16,78 → MISMATCH là kết quả ĐÚNG.
        self.assertEqual(strong_claims[key].run(None).status, vc.MISMATCH)

        # Khi giá trị tài liệu trùng kết quả tính thì phải báo VERIFIED — chứng minh
        # VERIFIED không phải là kết quả "mặc định".
        measured = strong_claims[key].compute(None)
        aligned = vc.Claim(key, "src", measured, lambda d: measured)
        self.assertEqual(aligned.run(None).status, vc.VERIFIED)

        # Và giá trị tái lập phải đổi theo dữ liệu, không phải hằng.
        self.assertNotEqual(
            strong_claims[key].compute(None), weak_claims[key].compute(None)
        )

    def test_relative_tolerance_does_not_accept_a_wrong_p_value(self):
        """p-value phải so TƯƠNG ĐỐI — dung sai tuyệt đối sẽ nuốt mọi p < 5e-4."""
        vc = _load_script("verify_claims")
        exact = vc.Claim("p", "src", 7.4e-11, lambda d: 7.38e-11, rtol=0.05)
        wrong = vc.Claim("p", "src", 7.4e-11, lambda d: 7.4e-15, rtol=0.05)
        self.assertEqual(exact.run(None).status, vc.VERIFIED)
        self.assertEqual(wrong.run(None).status, vc.MISMATCH)

    def test_progress_report_builds_the_bullet_from_the_evidence(self):
        module = _load_script("build_progress_report")
        self.assertTrue(callable(module.fog_flag_evidence_bullet))

    @unittest.skipUnless(
        (REPO_ROOT / "data" / "interim" / "air_quality_canonical.parquet").exists(),
        "Thiếu data/interim — bỏ qua kiểm tra câu sinh ra.",
    )
    def test_progress_report_bullet_carries_the_computed_f_statistic(self):
        module = _load_script("build_progress_report")
        evidence = fe.fog_flag_evidence(fe.build_analysis_frame())
        bullet = module.fog_flag_evidence_bullet()
        self.assertIn(
            fe.format_number_vi(round(evidence["seasonal"]["f_statistic"], 2)),
            bullet,
        )
        self.assertIn(
            fe.format_scientific_vi(evidence["seasonal"]["f_p_value"]), bullet
        )
        self.assertIn("verify_claims.py", bullet)


if __name__ == "__main__":
    unittest.main()