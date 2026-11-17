"""Contrôles temporels sur séries artificielles réservées aux tests."""

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
from sklearn.dummy import DummyRegressor

from scripts.forecast_data import (FEATURE_COLUMNS, HORIZONS, PERIODS, baseline_predictions,
                                   build_features, build_targets, split_examples)
from scripts.forecast_evaluation import evaluate_predictions
from scripts.forecast_models import make_model, predict_direct
from scripts.predict_forecast import forecast_next_24


def controlled(start="2018-10-01", periods=800):
    return pd.Series(np.arange(periods, dtype=float),
                     index=pd.date_range(start, periods=periods, freq="h", tz="UTC"),
                     name="demand_mw")


class ForecastingTests(unittest.TestCase):
    def test_24_horizons_and_target_alignment(self):
        load = controlled()
        targets = build_targets(load)
        self.assertEqual(list(targets.columns), list(range(1, 25)))
        self.assertEqual(targets.shape, (len(load), 24))
        for h in HORIZONS:
            self.assertEqual(targets.iloc[200][h], 200 + h)
            self.assertTrue(targets[h].iloc[-h:].isna().all())

    def test_origin_features_and_baseline_availability(self):
        load = controlled()
        features = build_features(load)
        for h in HORIZONS:
            row = features[h].iloc[200]
            target = load.index[200] + timedelta(hours=h)
            self.assertEqual(row["target_hour"], target.hour)
            self.assertEqual(row["target_day_of_week"], target.dayofweek)
            self.assertEqual(row["target_month"], target.month)
            self.assertEqual(row["target_weekend"], int(target.dayofweek >= 5))
            self.assertEqual(row["demand_at_origin"], 200)
            self.assertEqual(row["demand_origin_minus_24h"], 176)
            self.assertEqual(row["demand_origin_minus_168h"], 32)
            self.assertEqual(row["mean_last_24h"], np.mean(range(177, 201)))
            self.assertEqual(row["mean_last_168h"], np.mean(range(33, 201)))
            self.assertEqual(row["previous_day"], 200 + h - 24)
            self.assertEqual(row["previous_week"], 200 + h - 168)
            self.assertLessEqual(200 + h - 24, 200)
        origins = load.index[[200, 201]]
        daily = baseline_predictions(features, origins, "previous_day")
        self.assertEqual(daily.shape, (2, 24))
        self.assertEqual(daily[0, 0], 177)
        self.assertEqual(daily[0, 23], 200)

    def test_calendar_crosses_year_and_weekend(self):
        load = controlled("2020-12-20", 400)
        origin = pd.Timestamp("2020-12-31 23:00", tz="UTC")
        row = build_features(load)[1].loc[origin]
        self.assertEqual((row.target_hour, row.target_month, row.target_day_of_week), (0, 1, 4))

    def test_future_changes_do_not_change_features_at_or_before_origin(self):
        load = controlled()
        changed = load.copy()
        changed.iloc[251:] = 999999
        original_features, changed_features = build_features(load), build_features(changed)
        for h in HORIZONS:
            assert_frame_equal(original_features[h].iloc[:251], changed_features[h].iloc[:251])
        self.assertNotEqual(build_targets(load).iloc[250, 0], build_targets(changed).iloc[250, 0])

    def test_truncating_all_future_observations_preserves_features(self):
        load = controlled()
        full, truncated = build_features(load), build_features(load.iloc[:251])
        for h in HORIZONS:
            assert_frame_equal(full[h].iloc[:251], truncated[h])

    def test_missing_feature_and_missing_target_are_distinguished(self):
        load = controlled()
        load.iloc[252] = np.nan
        features, targets = build_features(load), build_targets(load)
        kept, audit = split_examples(load, features, targets, "train")
        before_gap = load.index[250]
        self.assertFalse(audit.loc[before_gap, "unavailable_features"])
        self.assertEqual(audit.loc[before_gap, "reason"], "missing_targets")
        self.assertEqual(audit.loc[load.index[252], "reason"], "missing_features")
        self.assertNotIn(before_gap, kept)
        self.assertTrue(pd.isna(features[24].loc[load.index[252], "previous_day"]))

    def test_purge_separates_train_validation_and_validation_test(self):
        for start, first, second in [("2018-12-15", "train", "validation"),
                                     ("2019-12-15", "validation", "test")]:
            with self.subTest(first=first, second=second):
                load = controlled(start, 800)
                features, targets = build_features(load), build_targets(load)
                a, audit = split_examples(load, features, targets, first)
                b, _ = split_examples(load, features, targets, second)
                end = pd.Timestamp(PERIODS[first][1], tz="UTC")
                self.assertEqual((audit.reason == "boundary_24h").sum(), 24)
                self.assertEqual(a.max(), end - timedelta(hours=25))
                self.assertLess(a.max() + timedelta(hours=24), b.min())
                self.assertTrue(targets.loc[a].notna().all().all())

    def test_test_targets_stay_in_january_to_june(self):
        load = controlled("2020-06-15", 600)
        features, targets = build_features(load), build_targets(load)
        kept, audit = split_examples(load, features, targets, "test")
        self.assertEqual(kept.max(), pd.Timestamp("2020-06-29 23:00", tz="UTC"))
        self.assertEqual((audit.reason == "boundary_24h").sum(), 24)
        self.assertLess(kept.max() + timedelta(hours=24), pd.Timestamp("2020-07-01", tz="UTC"))

    def test_exclusions_are_additive_and_no_rows_imputed(self):
        load = controlled("2015-01-01")
        load.iloc[400] = np.nan
        features, targets = build_features(load), build_targets(load)
        kept, audit = split_examples(load, features, targets, "train")
        self.assertEqual((audit.reason == "insufficient_history").sum(), 168)
        self.assertEqual(audit.reason.value_counts().sum(), len(audit))
        self.assertTrue(targets.loc[kept].notna().all().all())
        for h in HORIZONS:
            self.assertTrue(features[h].loc[kept].notna().all().all())
        self.assertTrue(pd.isna(load.iloc[400]))

    def test_metrics_use_global_squared_errors(self):
        actual = np.zeros((2, 24))
        predicted = np.vstack([np.ones(24), np.full(24, 3)])
        overall, by_horizon = evaluate_predictions(actual, predicted)
        self.assertEqual(overall["mae_mw"], 2)
        self.assertAlmostEqual(overall["rmse_mw"], np.sqrt(5))
        self.assertTrue((by_horizon.mae_mw == 2).all())
        with self.assertRaises(ValueError):
            evaluate_predictions(actual, np.zeros((2, 23)))
        with self.assertRaises(ValueError):
            evaluate_predictions(actual, np.full((2, 24), np.nan))

    def test_ridge_scaler_fits_only_training_values(self):
        load = controlled()
        x = build_features(load)[1]
        train = x.iloc[168:200]
        model = make_model("Ridge")
        model.fit(train, build_targets(load).iloc[168:200, 0])
        scaler = model[0].named_transformers_["numeric"]
        self.assertAlmostEqual(scaler.mean_[0], np.mean(range(168, 200)))
        self.assertNotEqual(scaler.mean_[0], x.demand_at_origin.mean())

    def test_saved_models_predict_24_values_from_past_only(self):
        load = controlled()
        features = build_features(load)
        models = {h: DummyRegressor(strategy="constant", constant=h).fit(
            features[h].iloc[168:200], np.arange(32)) for h in HORIZONS}
        bundle = {"name": "controlled_test", "models": models,
                  "metadata": {"features": FEATURE_COLUMNS}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "controlled.joblib"
            joblib.dump(bundle, path)
            restored = joblib.load(path)
            result = forecast_next_24(restored, load.iloc[:251])
        self.assertEqual(result.shape, (24, 4))
        self.assertEqual(result.predicted_mw.tolist(), list(range(1, 25)))
        self.assertEqual(result.target_utc.iloc[-1], load.index[250] + timedelta(hours=24))
        self.assertEqual(str(result.target_utc.dt.tz), "UTC")
        self.assertEqual(predict_direct(models, features, load.index[200:202]).shape, (2, 24))
        with self.assertRaises(ValueError):
            forecast_next_24(bundle, load.iloc[:100])


if __name__ == "__main__":
    unittest.main()
