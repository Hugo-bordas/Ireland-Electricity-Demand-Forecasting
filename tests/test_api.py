"""Exercise HTTP validation and real saved-model inference without training."""

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from api.main import ROOT, create_app
from scripts.forecast_data import FEATURE_COLUMNS
from scripts.make_api_example import example_request


@unittest.skipUnless(all((ROOT / name).is_file() for name in ('data/raw/time_series_60min_singleindex.csv', 'data/processed/phase3/test_predictions.csv', 'models/phase3/RandomForest.joblib')),
                     "Local reference artifacts are not distributed; see README.md")
class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fit_guard = patch("sklearn.ensemble.RandomForestRegressor.fit", side_effect=AssertionError("Training forbidden"))
        cls.fit = cls.fit_guard.start()
        cls.addClassCleanup(cls.fit_guard.stop)
        cls.evaluation_guard = patch("scripts.evaluate_test.main", side_effect=AssertionError("Evaluation forbidden"))
        cls.evaluation_guard.start()
        cls.addClassCleanup(cls.evaluation_guard.stop)
        cls.client = TestClient(create_app())
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)
        cls.payload = example_request()

    def test_health_and_openapi_documentation(self):
        result = self.client.get("/health")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"status": "ok", "artifacts": {"random_forest": True, "historical_forecasts": True}})
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertEqual(set(self.client.get("/openapi.json").json()["paths"]),
                         {"/health", "/model-info", "/historical-forecast", "/predict"})

    def test_metadata_matches_saved_model_and_feature_order(self):
        result = self.client.get("/model-info")
        self.assertEqual(result.status_code, 200)
        info = result.json()
        self.assertEqual(info["features"], FEATURE_COLUMNS)
        self.assertEqual(len(info["features"]), 11)
        self.assertEqual(info["horizons"], list(range(1, 25)))
        self.assertEqual(info["training_period_end_exclusive"], ["2015-01-01", "2019-01-01"])
        self.assertEqual(info["model"], "RandomForest")
        self.assertIn("interval starts", info["limitations"])

    def test_historical_forecast_reads_saved_values_without_inference(self):
        with patch("api.main.forecast_next_24", side_effect=AssertionError("Inference forbidden")):
            result = self.client.get("/historical-forecast", params={"origin_utc": self.payload["origin_utc"]})
        self.assertEqual(result.status_code, 200)
        saved = pd.read_csv(ROOT / "data/processed/phase3/test_predictions.csv")
        saved = saved[pd.to_datetime(saved.origin_utc, utc=True) == pd.Timestamp(self.payload["origin_utc"])]
        np.testing.assert_array_equal([r["predicted_mw"] for r in result.json()], saved.RandomForest)
        np.testing.assert_array_equal([r["observed_mw"] for r in result.json()], saved.observed_mw)

    def test_unknown_origin_returns_404(self):
        result = self.client.get("/historical-forecast", params={"origin_utc": "2024-01-01T00:00:00Z"})
        self.assertEqual(result.status_code, 404)

    def test_prediction_matches_saved_values_for_verified_origin(self):
        result = self.client.post("/predict", json=self.payload)
        self.assertEqual(result.status_code, 200, result.text)
        historical = self.client.get("/historical-forecast", params={"origin_utc": self.payload["origin_utc"]}).json()
        rows = result.json()
        self.assertEqual(len(rows), 24)
        self.assertEqual([r["horizon"] for r in rows], list(range(1, 25)))
        # CSV float serialization and rolling arithmetic can introduce tiny rounding differences.
        np.testing.assert_allclose([r["predicted_mw"] for r in rows],
                                   [r["predicted_mw"] for r in historical], rtol=0, atol=1e-8)
        for row in rows:
            self.assertEqual(pd.Timestamp(row["target_utc"]), pd.Timestamp(self.payload["origin_utc"]) + timedelta(hours=row["horizon"]))
            self.assertEqual(pd.Timestamp(row["origin_utc"]), pd.Timestamp(self.payload["origin_utc"]))
            self.assertEqual(row["model"], "RandomForest")
            self.assertNotIn("observed_mw", row)
        self.fit.assert_not_called()

    def test_incomplete_or_oversized_history_is_rejected(self):
        for history in (self.payload["history"][:-1], [], self.payload["history"] * 2):
            with self.subTest(length=len(history)):
                payload = {**self.payload, "history": history}
                self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)

    def test_invalid_numeric_demands_are_rejected(self):
        for value in (None, "3000", True, -1, "NaN"):
            with self.subTest(value=value):
                payload = deepcopy(self.payload)
                payload["history"][0]["demand_mw"] = value
                self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)
        for token in ("NaN", "Infinity", "-Infinity"):
            payload = deepcopy(self.payload)
            payload["history"][0]["demand_mw"] = 987654321
            raw = json.dumps(payload).replace('987654321', token)
            self.assertEqual(self.client.post("/predict", content=raw, headers={"content-type": "application/json"}).status_code, 422)

    def test_irregular_duplicate_or_reversed_history_is_rejected(self):
        for variant in ("duplicate", "gap", "reversed"):
            with self.subTest(variant=variant):
                payload = deepcopy(self.payload)
                if variant == "duplicate":
                    payload["history"][1]["timestamp_utc"] = payload["history"][0]["timestamp_utc"]
                elif variant == "gap":
                    first = pd.Timestamp(payload["history"][0]["timestamp_utc"])
                    payload["history"][0]["timestamp_utc"] = (first - timedelta(hours=1)).isoformat()
                else:
                    payload["history"].reverse()
                self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)

    def test_origin_must_be_last_history_hour(self):
        for origin in ("2020-02-03T01:00:00Z", "2020-02-03T03:00:00Z"):
            payload = {**self.payload, "origin_utc": origin}
            self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)

    def test_timestamps_require_explicit_utc_whole_hours(self):
        for value in ("2020-02-03T02:00:00", "2020-02-03T03:00:00+01:00", "2020-02-03T02:01:00Z", 1580695200, "not-a-date", "9999-01-01T00:00:00Z"):
            with self.subTest(value=value):
                payload = {**self.payload, "origin_utc": value}
                self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)
                self.assertEqual(self.client.get("/historical-forecast", params={"origin_utc": value}).status_code, 422)

    def test_missing_fields_extra_fields_and_invalid_json(self):
        for payload in ({}, {**self.payload, "future_demand": 3000},
                        {**self.payload, "history": [{"timestamp_utc": "2020-01-01T00:00:00Z"}] * 169}):
            self.assertEqual(self.client.post("/predict", json=payload).status_code, 422)
        self.assertEqual(self.client.post("/predict", content="{", headers={"content-type": "application/json"}).status_code, 422)

    def test_missing_artifacts_are_503_without_exposing_paths(self):
        with tempfile.TemporaryDirectory() as folder, patch("api.main.logger.exception"), TestClient(create_app(folder)) as client:
            for endpoint in ("/health", "/model-info", "/historical-forecast?origin_utc=2020-02-03T02:00:00Z"):
                result = client.get(endpoint)
                self.assertEqual(result.status_code, 503)
                self.assertNotIn(folder, result.text)
            result = client.post("/predict", json=self.payload)
            self.assertEqual(result.status_code, 503)
            self.assertNotIn(folder, result.text)

    def test_corrupt_model_is_rejected_before_deserialization(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "reports/ml").mkdir(parents=True)
            (root / "models/phase3").mkdir(parents=True)
            (root / "reports/ml/selection.json").write_bytes((ROOT / "reports/ml/selection.json").read_bytes())
            (root / "models/phase3/RandomForest.joblib").write_bytes(b"corrupt")
            with patch("api.main.joblib.load", side_effect=AssertionError("Unsafe load")), patch("api.main.logger.exception"), TestClient(create_app(root)) as client:
                self.assertEqual(client.get("/health").status_code, 503)

    def test_inference_failure_has_a_generic_public_error(self):
        with patch("api.main.forecast_next_24", side_effect=ValueError("/private/internal/path")), patch("api.main.logger.exception"):
            result = self.client.post("/predict", json=self.payload)
        self.assertEqual(result.status_code, 503)
        self.assertNotIn("/private", result.text)

    def test_requests_reuse_loaded_model_without_deserialization(self):
        with patch("api.main.joblib.load", side_effect=AssertionError("Repeated model load forbidden")):
            self.assertEqual(self.client.get("/model-info").status_code, 200)
            self.assertEqual(self.client.post("/predict", json=self.payload).status_code, 200)
        self.fit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
