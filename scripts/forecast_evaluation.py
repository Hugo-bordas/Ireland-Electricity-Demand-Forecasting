"""Métriques et exports sur des paires (origine, horizon) de poids égal."""

import numpy as np
import pandas as pd

from scripts.forecast_data import HORIZONS


def evaluate_predictions(actual, predicted):
    actual, predicted = np.asarray(actual), np.asarray(predicted)
    if actual.shape != predicted.shape or actual.ndim != 2 or actual.shape[1] != 24:
        raise ValueError("Les cibles et prédictions doivent avoir la forme (n_origines, 24).")
    if len(actual) == 0 or not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("L'évaluation exige des valeurs finies et au moins une origine.")
    errors = predicted - actual
    overall = {"mae_mw": float(np.abs(errors).mean()),
               "rmse_mw": float(np.sqrt(np.square(errors).mean()))}
    per_horizon = pd.DataFrame({
        "horizon": HORIZONS,
        "mae_mw": np.abs(errors).mean(axis=0),
        "rmse_mw": np.sqrt(np.square(errors).mean(axis=0)),
    })
    return overall, per_horizon


def prediction_table(origins, actual, predictions):
    """Exporter toutes les prévisions, sans choisir une belle période après examen."""
    frame = pd.DataFrame({"origin_utc": np.repeat(origins, 24),
                          "horizon": np.tile(HORIZONS, len(origins)),
                          "observed_mw": np.asarray(actual).ravel()})
    frame["target_utc"] = pd.to_datetime(frame["origin_utc"], utc=True) + pd.to_timedelta(
        frame["horizon"], unit="h")
    for name, values in predictions.items():
        frame[name] = np.asarray(values).ravel()
    return frame
