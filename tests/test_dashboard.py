"""Dashboard checks use saved artifacts; they never train or evaluate a model."""

import importlib.util
from io import StringIO
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.explore_data import CSV_PATH

from dashboard.data import (MODEL, ROOT, forecast_table, load_results, representative_origin,
                            select_forecast, validate_predictions)


@unittest.skipUnless(CSV_PATH.is_file() and (ROOT / 'data/processed/phase3/test_predictions.csv').is_file(),
                     "Install the reference model Release asset to run inference integration tests; see README.md")
class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_results()
        cls.predictions = cls.data["predictions"]
        cls.origin = cls.predictions.origin_utc.min()

    def test_loads_saved_metrics_without_rounding(self):
        for period in ("validation", "test"):
            source = pd.read_csv(ROOT / f"reports/ml/{period}_metrics.csv")
            pd.testing.assert_frame_equal(self.data[f"{period}_metrics"], source)
        self.assertEqual(self.predictions.origin_utc.nunique(), self.data["completion"]["n_origins"])

    def test_selected_forecast_dates_align_with_all_24_horizons(self):
        forecast = select_forecast(self.predictions, self.origin)
        self.assertEqual(forecast.horizon.tolist(), list(range(1, 25)))
        self.assertTrue((forecast.origin_utc == self.origin).all())
        expected = self.origin + pd.to_timedelta(forecast.horizon, unit="h")
        self.assertTrue(forecast.target_utc.equals(expected))

    def test_display_errors_equal_saved_prediction_minus_observation(self):
        forecast = select_forecast(self.predictions, self.origin)
        errors = forecast[MODEL].to_numpy() - forecast.observed_mw.to_numpy()
        np.testing.assert_array_equal(forecast.error_mw, errors)
        self.assertAlmostEqual(forecast.absolute_error_mw.mean(), np.abs(errors).mean())
        self.assertNotIn("error_mw", self.predictions.columns)

    def test_invalid_or_naive_origin_is_rejected(self):
        for origin in ("2021-01-01T00:00:00Z", "2020-01-01", "2020-06-17T20:00:00Z"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                select_forecast(self.predictions, origin)

    def test_missing_artifacts_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(FileNotFoundError, "test_predictions.csv"):
                load_results(folder)

    def test_corrupt_or_incomplete_forecast_is_rejected(self):
        complete = self.predictions.loc[self.predictions.origin_utc == self.origin].copy()
        wrong_date = complete.copy()
        wrong_date.loc[wrong_date.index[0], "target_utc"] += pd.offsets.Hour(1)
        missing_value = complete.copy()
        missing_value.loc[missing_value.index[0], MODEL] = np.nan
        for frame in (complete.iloc[:-1], pd.concat([complete, complete.iloc[:1]]), wrong_date, missing_value):
            with self.subTest(rows=len(frame)), self.assertRaises(ValueError):
                validate_predictions(frame)

    def test_no_model_loading_training_or_final_evaluation(self):
        with patch("joblib.load", side_effect=AssertionError("Model load forbidden")), \
             patch("sklearn.ensemble.RandomForestRegressor.fit", side_effect=AssertionError("Fit forbidden")), \
             patch("scripts.evaluate_test.main", side_effect=AssertionError("Final test forbidden")):
            results = load_results()
            forecast = select_forecast(results["predictions"], self.origin)
        self.assertEqual(len(forecast), 24)

    def test_default_origin_is_deterministic_and_closest_to_median_mae(self):
        errors = (self.predictions[MODEL] - self.predictions.observed_mw).abs()
        per_origin = errors.groupby(self.predictions.origin_utc).mean().sort_index()
        selected = representative_origin(self.predictions)
        self.assertEqual(abs(per_origin.loc[selected] - per_origin.median()),
                         (per_origin - per_origin.median()).abs().min())
        self.assertEqual(selected, representative_origin(self.predictions.sample(frac=1, random_state=42)))
        self.assertEqual(self.predictions.origin_utc.nunique(), 4149)

    def test_high_error_example_remains_available_and_matches_raw_observations(self):
        origin = pd.Timestamp("2020-01-02T02:00:00Z")
        forecast = select_forecast(self.predictions, origin)
        raw = pd.read_csv(CSV_PATH,
                          usecols=["utc_timestamp", "IE_load_actual_entsoe_transparency"])
        raw.index = pd.to_datetime(raw.utc_timestamp, utc=True)
        np.testing.assert_array_equal(forecast.observed_mw,
            raw.loc[forecast.target_utc, "IE_load_actual_entsoe_transparency"])
        self.assertAlmostEqual(forecast.absolute_error_mw.mean(), 350.72970699495437)
        worst = forecast.loc[forecast.absolute_error_mw.idxmax()]
        self.assertEqual(worst.target_utc, pd.Timestamp("2020-01-02T10:00:00Z"))
        self.assertEqual(worst.horizon, 8)
        self.assertAlmostEqual(worst.absolute_error_mw, 826.302380635092)

    def test_csv_round_trip_preserves_display_table_values_and_order(self):
        forecast = select_forecast(self.predictions, "2020-01-02T02:00:00Z")
        table = forecast_table(forecast)
        restored = pd.read_csv(StringIO(table.to_csv(index=False)), float_precision="round_trip")
        pd.testing.assert_frame_equal(restored, table, check_exact=True)
        self.assertEqual(restored["Origin (UTC)"].unique().tolist(), ["2020-01-02 02:00 UTC"])


HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


@unittest.skipUnless((ROOT / "data/processed/phase3/test_predictions.csv").is_file(),
                     "Reference historical predictions are missing; see README.md")
@unittest.skipUnless(HAS_STREAMLIT, "Install requirements-dashboard.txt to run Streamlit interaction tests")
class DashboardAppTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30)

    def test_startup_refreshes_an_outdated_data_module_without_training(self):
        import dashboard.data as data_module
        from streamlit.testing.v1 import AppTest
        for name in ("forecast_table", "representative_origin"):
            with self.subTest(missing_export=name):
                original = getattr(data_module, name)
                delattr(data_module, name)
                try:
                    with patch("sklearn.ensemble.RandomForestRegressor.fit", side_effect=AssertionError("Fit forbidden")), \
                         patch("joblib.load", side_effect=AssertionError("Model load forbidden")), \
                         patch("scripts.evaluate_test.main", side_effect=AssertionError("Final test forbidden")):
                        app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
                        self.assertEqual(len(app.exception), 0)
                        self.assertEqual(len(app.error), 0)
                        app.radio(key="navigation").set_value("Forecast Explorer").run()
                        self.assertEqual(len(app.exception), 0)
                        self.assertEqual(len(app.dataframe[0].value), 24)
                    self.assertTrue(callable(getattr(data_module, name)))
                finally:
                    if not hasattr(data_module, name):
                        setattr(data_module, name, original)

    def test_overview_and_all_sections_render_without_training(self):
        with patch("sklearn.ensemble.RandomForestRegressor.fit", side_effect=AssertionError("Fit forbidden")), \
             patch("joblib.load", side_effect=AssertionError("Model load forbidden")), \
             patch("scripts.evaluate_test.main", side_effect=AssertionError("Final test forbidden")):
            self.app.run()
            self.assertEqual(len(self.app.exception), 0)
            self.assertEqual(len(self.app.error), 0)
            self.assertEqual(self.app.metric[0].value, f"{load_results()['test_metrics'].set_index('model').loc[MODEL, 'mae_mw']:.2f} MW")
            for section in ["Forecast Explorer", "Model Performance", "Methodology"]:
                self.app.radio(key="navigation").set_value(section).run()
                self.assertEqual(len(self.app.exception), 0)
                self.assertEqual(len(self.app.error), 0)

    def test_date_and_hour_selection_changes_the_saved_forecast(self):
        self.app.run()
        self.app.radio(key="navigation").set_value("Forecast Explorer").run()
        self.app.selectbox(key="origin_date").select_index(5).run()
        self.app.selectbox(key="origin_hour").select_index(3).run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.error), 0)
        day = self.app.selectbox(key="origin_date").value
        hour = self.app.selectbox(key="origin_hour").value
        origin = pd.Timestamp(day, tz="UTC") + pd.offsets.Hour(hour)
        forecast = select_forecast(load_results()["predictions"], origin)
        self.assertEqual(self.app.metric[0].value, f"{forecast.absolute_error_mw.mean():.2f} MW")
        self.app.checkbox[0].check().run()
        self.assertEqual(len(self.app.exception), 0)

    def test_performance_switches_period_without_mixing_scores(self):
        self.app.run()
        self.app.radio(key="navigation").set_value("Model Performance").run()
        self.assertEqual(len(self.app.dataframe[0].value), 3)
        self.app.radio(key="evaluation_period").set_value("Validation · 2019").run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(len(self.app.dataframe[0].value), 5)

    def test_missing_file_is_reported_in_the_interface(self):
        with patch("dashboard.data.pd.read_csv", side_effect=FileNotFoundError("Missing test_predictions.csv")):
            # Clear the cache to exercise a fresh startup failure.
            import streamlit as st
            st.cache_data.clear()
            self.app.run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertGreater(len(self.app.error), 0)
        self.assertIn("Missing test_predictions.csv", self.app.error[0].value)

    def test_export_payload_equals_displayed_rows_for_high_error_origin(self):
        import streamlit as st
        self.app.run()
        with patch("streamlit.download_button", wraps=st.download_button) as download:
            self.app.radio(key="navigation").set_value("Forecast Explorer").run()
            origin = pd.Timestamp("2020-01-02T02:00:00Z")
            self.app.selectbox(key="origin_date").set_value(origin.date()).run()
            self.app.selectbox(key="origin_hour").set_value(origin.hour).run()
            payload = download.call_args.args[1]
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.metric[0].label, "MAE · selected 24 hours")
        self.assertEqual(self.app.metric[0].value, "350.73 MW")
        self.assertEqual(self.app.metric[1].value, "826.30 MW")
        exported = pd.read_csv(StringIO(payload.decode("utf-8")), float_precision="round_trip")
        pd.testing.assert_frame_equal(exported, self.app.dataframe[0].value, check_exact=True)

    def test_initial_forecast_uses_the_documented_median_rule(self):
        self.app.run()
        self.app.radio(key="navigation").set_value("Forecast Explorer").run()
        day = self.app.selectbox(key="origin_date").value
        hour = self.app.selectbox(key="origin_hour").value
        selected = pd.Timestamp(day, tz="UTC") + pd.offsets.Hour(hour)
        self.assertEqual(selected, representative_origin(load_results()["predictions"]))

    def test_changing_only_date_updates_origin_and_forecast(self):
        self.app.run()
        self.app.radio(key="navigation").set_value("Forecast Explorer").run()
        origin = pd.Timestamp("2020-01-02T02:00:00Z")
        self.app.selectbox(key="origin_date").set_value(origin.date()).run()
        self.assertEqual(len(self.app.exception), 0)
        self.assertEqual(self.app.selectbox(key="origin_hour").value, origin.hour)
        self.assertEqual(self.app.metric[0].value, "350.73 MW")
        self.assertEqual(self.app.dataframe[0].value["Origin (UTC)"].unique().tolist(),
                         ["2020-01-02 02:00 UTC"])

    def test_forecast_chart_uses_original_values_and_distinct_lines(self):
        import streamlit as st
        self.app.run()
        with patch("streamlit.altair_chart", wraps=st.altair_chart) as draw:
            self.app.radio(key="navigation").set_value("Forecast Explorer").run()
            self.app.checkbox[0].check().run()
            chart = draw.call_args.args[0].to_dict()
        day = self.app.selectbox(key="origin_date").value
        hour = self.app.selectbox(key="origin_hour").value
        origin = pd.Timestamp(day, tz="UTC") + pd.offsets.Hour(hour)
        saved = select_forecast(load_results()["predictions"], origin)
        records = next(records for records in chart["datasets"].values()
                       if records and "Series" in records[0])
        plotted = pd.DataFrame(records)
        for label, column in [("Observed", "observed_mw"), ("Random Forest", MODEL),
                              ("Previous day", "DailyBaseline")]:
            points = plotted[plotted.Series == label].sort_values("horizon")
            np.testing.assert_array_equal(points["Demand (MW)"], saved[column])
            self.assertEqual(pd.to_datetime(points.target_utc, utc=True).tolist(), saved.target_utc.tolist())
        encoding = chart["layer"][0]["encoding"]
        self.assertEqual(encoding["x"]["scale"]["type"], "utc")
        self.assertNotEqual(*encoding["strokeDash"]["scale"]["range"][:2])
        self.assertEqual(len(self.app.metric), 4)

    def test_comparison_chart_uses_only_selected_period_results(self):
        import streamlit as st
        self.app.run()
        with patch("streamlit.altair_chart", wraps=st.altair_chart) as draw:
            self.app.radio(key="navigation").set_value("Model Performance").run()
            for label, period in [("Test · Jan–Jun 2020", "test"), ("Validation · 2019", "validation")]:
                self.app.radio(key="evaluation_period").set_value(label).run()
                comparison, horizons = [call.args[0].to_dict() for call in draw.call_args_list[-2:]]
                rows = next(iter(comparison["datasets"].values()))
                actual = pd.DataFrame(rows).set_index("model").sort_index()
                expected = load_results()[f"{period}_metrics"].set_index("model").sort_index()
                np.testing.assert_array_equal(actual.mae_mw, expected.mae_mw)
                np.testing.assert_array_equal(actual.rmse_mw, expected.rmse_mw)
                horizon_rows = pd.DataFrame(next(iter(horizons["datasets"].values())))
                self.assertEqual(set(horizon_rows.model), set(expected.index))


if __name__ == "__main__":
    unittest.main()
