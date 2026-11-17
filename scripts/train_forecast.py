"""Entraîner sur 2015-2018 et sélectionner sur 2019 : python -m scripts.train_forecast."""

import hashlib
import importlib.metadata
import json
from datetime import datetime, timezone
from pathlib import Path
import time

import joblib
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts.explore_data import CSV_PATH, LOAD_COLUMN, ROOT, load_data
from scripts.forecast_data import (FEATURE_COLUMNS, HORIZONS, PERIODS, baseline_predictions,
                                   build_features, build_targets, split_examples)
from scripts.forecast_evaluation import evaluate_predictions, prediction_table
from scripts.forecast_models import MODEL_NAMES, MODEL_PARAMETERS, fit_direct_models, predict_direct


MODEL_DIR = ROOT / "models" / "phase3"
REPORT_DIR = ROOT / "reports" / "ml"
PREDICTION_DIR = ROOT / "data" / "processed" / "phase3"
SELECTION_PATH = REPORT_DIR / "selection.json"
TEST_MARKER = REPORT_DIR / "test_evaluation_started.json"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def split_summary(period, origins, audit):
    row = {"period": period, "candidates": len(audit), "kept": len(origins)}
    for reason in ("boundary_24h", "insufficient_history", "missing_features", "missing_targets"):
        row[reason] = int((audit["reason"] == reason).sum())
    row.update(first_origin=str(origins.min()), last_origin=str(origins.max()),
               first_target=str(origins.min() + pd.offsets.Hour(1)),
               last_target=str(origins.max() + pd.offsets.Hour(24)))
    return row


def main():
    if SELECTION_PATH.exists() or TEST_MARKER.exists():
        raise SystemExit("Expérience déjà sélectionnée ou test déjà ouvert. Consulter les résultats existants.")
    for path in (MODEL_DIR, REPORT_DIR, PREDICTION_DIR):
        path.mkdir(parents=True, exist_ok=True)
    # Aucun exemple d'entraînement/validation ne peut utiliser une mesure de 2020.
    load = load_data(CSV_PATH)[LOAD_COLUMN].loc[:"2019-12-31 23:00"]
    features, targets = build_features(load), build_targets(load)
    splits, summaries = {}, []
    for period in ("train", "validation"):
        origins, audit = split_examples(load, features, targets, period)
        splits[period] = origins
        audit.to_csv(PREDICTION_DIR / f"{period}_exclusions.csv")
        summaries.append(split_summary(period, origins, audit))
    pd.DataFrame(summaries).to_csv(REPORT_DIR / "split_counts.csv", index=False)
    train, validation = splits["train"], splits["validation"]
    actual = targets.loc[validation].to_numpy()
    print(pd.DataFrame(summaries).to_string(index=False), flush=True)
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "strategy": "24 independent direct regressors; hourly forecast origins; no refit",
        "selection_rule": "lowest validation MAE among ML; then RMSE, then name",
        "periods_end_exclusive": PERIODS,
        "features": FEATURE_COLUMNS, "horizons": list(HORIZONS),
        "model_parameters": MODEL_PARAMETERS,
        "data_sha256": hashlib.sha256(CSV_PATH.read_bytes()).hexdigest(),
        "protocol_sha256": hashlib.sha256((ROOT / "reports/phase3_protocol.md").read_bytes()).hexdigest(),
        "versions": {name: importlib.metadata.version(name)
                     for name in ("scikit-learn", "pandas", "numpy", "scipy", "joblib")},
    }
    write_json(REPORT_DIR / "training_config.json", metadata)
    predictions = {
        "DailyBaseline": baseline_predictions(features, validation, "previous_day"),
        "WeeklyBaseline": baseline_predictions(features, validation, "previous_week"),
    }
    scores, horizon_scores = [], []
    for name in predictions:
        score, per_horizon = evaluate_predictions(actual, predictions[name])
        scores.append({"model": name, **score, "fit_seconds": 0.0})
        horizon_scores.append(per_horizon.assign(model=name))
    with threadpool_limits(limits=2):
        for name in MODEL_NAMES:
            started = time.perf_counter()
            models = fit_direct_models(name, features, targets, train)
            elapsed = time.perf_counter() - started
            predictions[name] = predict_direct(models, features, validation)
            score, per_horizon = evaluate_predictions(actual, predictions[name])
            scores.append({"model": name, **score, "fit_seconds": elapsed})
            horizon_scores.append(per_horizon.assign(model=name))
            bundle = {"name": name, "models": models, "metadata": metadata}
            joblib.dump(bundle, MODEL_DIR / f"{name}.joblib", compress=3)
            print(f"Validation {name} : {score}", flush=True)
            del models, bundle
    metrics = pd.DataFrame(scores)
    metrics.to_csv(REPORT_DIR / "validation_metrics.csv", index=False)
    pd.concat(horizon_scores, ignore_index=True).to_csv(
        REPORT_DIR / "validation_by_horizon.csv", index=False)
    prediction_table(validation, actual, predictions).to_csv(
        PREDICTION_DIR / "validation_predictions.csv", index=False)
    chosen = metrics[metrics.model.isin(MODEL_NAMES)].sort_values(["mae_mw", "rmse_mw", "model"]).iloc[0]
    model_path = MODEL_DIR / f"{chosen['model']}.joblib"
    selection = {
        **metadata, "selected_model": chosen["model"],
        "validation_mae_mw": float(chosen["mae_mw"]),
        "validation_rmse_mw": float(chosen["rmse_mw"]),
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "test_evaluated": False,
    }
    write_json(SELECTION_PATH, selection)
    print(f"\nSélection figée avant test : {chosen['model']}", flush=True)


if __name__ == "__main__":
    main()
