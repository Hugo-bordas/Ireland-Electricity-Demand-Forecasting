"""Exemples directs : une ligne par origine T, une cible par horizon T+h."""

from datetime import timedelta

import numpy as np
import pandas as pd

from scripts.preprocessing import validate_hourly_index


HORIZONS = tuple(range(1, 25))
CALENDAR_COLUMNS = ["target_hour", "target_day_of_week", "target_month", "target_weekend"]
NUMERIC_COLUMNS = ["demand_at_origin", "demand_origin_minus_24h", "demand_origin_minus_168h",
                   "mean_last_24h", "mean_last_168h", "previous_day", "previous_week"]
FEATURE_COLUMNS = CALENDAR_COLUMNS + NUMERIC_COLUMNS
PERIODS = {
    "train": ("2015-01-01", "2019-01-01"),
    "validation": ("2019-01-01", "2020-01-01"),
    "test": ("2020-01-01", "2020-07-01"),
}


def build_features(load):
    """Calculer les variables sans cible future. Toutes les demandes sont datées <= T."""
    validate_hourly_index(load.to_frame())
    history = pd.DataFrame(index=load.index)
    history["demand_at_origin"] = load
    history["demand_origin_minus_24h"] = load.shift(24)
    history["demand_origin_minus_168h"] = load.shift(168)
    # Ici T est connu : fenêtres [T-23, T] et [T-167, T].
    history["mean_last_24h"] = load.rolling(24, min_periods=24).mean()
    history["mean_last_168h"] = load.rolling(168, min_periods=168).mean()
    features = {}
    for horizon in HORIZONS:
        target_time = load.index + timedelta(hours=horizon)
        frame = history.copy()
        frame["target_hour"] = target_time.hour
        frame["target_day_of_week"] = target_time.dayofweek
        frame["target_month"] = target_time.month
        frame["target_weekend"] = (target_time.dayofweek >= 5).astype(int)
        # T+h-24 <= T et T+h-168 <= T pour les horizons de 1 à 24.
        frame["previous_day"] = load.shift(24 - horizon)
        frame["previous_week"] = load.shift(168 - horizon)
        features[horizon] = frame[FEATURE_COLUMNS]
    return features


def build_targets(load):
    """À la ligne T, la colonne h contient y(T+h). Ne jamais utiliser comme variable."""
    validate_hourly_index(load.to_frame())
    return pd.DataFrame({h: load.shift(-h) for h in HORIZONS}, index=load.index)


def split_examples(load, features, targets, period):
    """Masque commun aux 24 horizons ; journaliser une raison exclusive par origine."""
    start, end = (pd.Timestamp(value, tz="UTC") for value in PERIODS[period])
    origins = load.index[(load.index >= start) & (load.index < end)]
    audit = pd.DataFrame(index=origins)
    audit.index.name = "origin_utc"
    audit["target_crosses_period_end"] = origins + timedelta(hours=24) >= end
    audit["insufficient_history"] = origins - timedelta(hours=168) < load.index.min()
    missing_features = pd.Series(False, index=origins)
    for horizon in HORIZONS:
        missing_features |= ~np.isfinite(features[horizon].loc[origins]).all(axis=1)
    audit["unavailable_features"] = missing_features
    audit["unavailable_targets"] = ~np.isfinite(targets.loc[origins]).all(axis=1)
    # Priorité explicite : les drapeaux détaillés peuvent se recouper.
    audit["reason"] = np.select(
        [audit["target_crosses_period_end"], audit["insufficient_history"],
         audit["unavailable_features"], audit["unavailable_targets"]],
        ["boundary_24h", "insufficient_history", "missing_features", "missing_targets"],
        default="kept",
    )
    kept = audit.index[audit["reason"] == "kept"]
    if kept.empty:
        raise ValueError(f"Aucun exemple complet dans la période {period}.")
    if not ((kept + timedelta(hours=24)) < end).all():
        raise ValueError("Une cible franchit la frontière de période.")
    return kept, audit


def baseline_predictions(features, origins, column):
    """Prédire les mêmes origines et horizons que le ML, sans remplir les lacunes."""
    if column not in ("previous_day", "previous_week"):
        raise ValueError("Baseline inconnue.")
    return np.column_stack([features[h].loc[origins, column].to_numpy() for h in HORIZONS])
