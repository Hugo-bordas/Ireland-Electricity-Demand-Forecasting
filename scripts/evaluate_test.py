"""Ouvrir le test final une seule fois, après sélection : python -m scripts.evaluate_test."""

import hashlib
import json
from datetime import datetime, timezone

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts.explore_data import CSV_PATH, LOAD_COLUMN, ROOT, load_data
from scripts.forecast_data import baseline_predictions, build_features, build_targets, split_examples
from scripts.forecast_evaluation import evaluate_predictions, prediction_table
from scripts.forecast_models import predict_direct
from scripts.train_forecast import (PREDICTION_DIR, REPORT_DIR, SELECTION_PATH, TEST_MARKER,
                                    split_summary, write_json)


def main():
    if TEST_MARKER.exists():
        raise SystemExit("Test déjà ouvert. Réutiliser les métriques et prédictions enregistrées.")
    if not SELECTION_PATH.exists():
        raise SystemExit("Entraîner et figer la sélection avant d'ouvrir le test.")
    selection = json.loads(SELECTION_PATH.read_text())
    model_path = ROOT / selection["model_path"]
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != selection["model_sha256"]:
        raise SystemExit("Le modèle a changé depuis sa sélection.")
    if hashlib.sha256(CSV_PATH.read_bytes()).hexdigest() != selection["data_sha256"]:
        raise SystemExit("Les données ont changé depuis la sélection.")
    if hashlib.sha256((ROOT / "reports/phase3_protocol.md").read_bytes()).hexdigest() != selection["protocol_sha256"]:
        raise SystemExit("Le protocole a changé depuis sa fixation.")
    # Le marqueur est créé avant toute évaluation, sans possibilité d'écrasement.
    with TEST_MARKER.open("x", encoding="utf-8") as output:
        json.dump({"opened_utc": datetime.now(timezone.utc).isoformat(),
                   "selected_model": selection["selected_model"],
                   "model_sha256": selection["model_sha256"]}, output, indent=2)
    load = load_data(CSV_PATH)[LOAD_COLUMN].loc[:"2020-06-30 23:00"]
    features, targets = build_features(load), build_targets(load)
    origins, audit = split_examples(load, features, targets, "test")
    audit.to_csv(PREDICTION_DIR / "test_exclusions.csv")
    splits = pd.read_csv(REPORT_DIR / "split_counts.csv")
    pd.concat([splits, pd.DataFrame([split_summary("test", origins, audit)])],
              ignore_index=True).to_csv(REPORT_DIR / "split_counts.csv", index=False)
    bundle = joblib.load(model_path)
    with threadpool_limits(limits=2):
        predictions = {selection["selected_model"]: predict_direct(bundle["models"], features, origins)}
    predictions["DailyBaseline"] = baseline_predictions(features, origins, "previous_day")
    predictions["WeeklyBaseline"] = baseline_predictions(features, origins, "previous_week")
    actual = targets.loc[origins].to_numpy()
    metrics, horizon_metrics = [], []
    for name, values in predictions.items():
        overall, per_horizon = evaluate_predictions(actual, values)
        metrics.append({"model": name, **overall})
        horizon_metrics.append(per_horizon.assign(model=name))
    # Conserver les sorties pour les graphiques, sans nouvelles prédictions de test.
    prediction_table(origins, actual, predictions).to_csv(
        PREDICTION_DIR / "test_predictions.csv", index=False)
    pd.DataFrame(metrics).to_csv(REPORT_DIR / "test_metrics.csv", index=False)
    pd.concat(horizon_metrics, ignore_index=True).to_csv(REPORT_DIR / "test_by_horizon.csv", index=False)
    write_json(REPORT_DIR / "test_completion.json", {
        "completed_utc": datetime.now(timezone.utc).isoformat(),
        "n_origins": len(origins), "metrics": metrics,
        "selected_model": selection["selected_model"], "model_sha256": selection["model_sha256"],
    })
    print(pd.DataFrame(metrics).to_string(index=False))


if __name__ == "__main__":
    main()
