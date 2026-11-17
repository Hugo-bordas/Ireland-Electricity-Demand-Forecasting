"""Réutiliser un modèle enregistré, sans disposer de ses futures cibles."""

import argparse
import json
from datetime import timedelta

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from scripts.explore_data import CSV_PATH, LOAD_COLUMN, ROOT, load_data
from scripts.forecast_data import FEATURE_COLUMNS, HORIZONS, build_features
from scripts.forecast_models import predict_direct


def forecast_next_24(bundle, history, origin=None):
    """Le passé peut s'arrêter à T : seules des données <= T sont lues comme variables."""
    if list(bundle["metadata"]["features"]) != FEATURE_COLUMNS:
        raise ValueError("Le schéma sauvegardé ne correspond pas au code courant.")
    origin = history.index.max() if origin is None else pd.Timestamp(origin)
    if origin.tzinfo is None or str(origin.tz) != "UTC" or origin not in history.index:
        raise ValueError("L'origine doit être une heure UTC présente dans l'historique.")
    past = history.loc[:origin]
    features = build_features(past)
    if any(not np.isfinite(features[h].loc[origin]).all() for h in HORIZONS):
        raise ValueError("Historique incomplet : les 24 prévisions ne peuvent pas être produites.")
    with threadpool_limits(limits=2):
        predicted = predict_direct(bundle["models"], features, pd.DatetimeIndex([origin]))[0]
    return pd.DataFrame({"origin_utc": origin, "horizon": HORIZONS,
                         "target_utc": [origin + timedelta(hours=h) for h in HORIZONS],
                         "predicted_mw": predicted})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True, help="Heure UTC, par exemple 2020-01-01T23:00:00Z")
    args = parser.parse_args()
    selection = json.loads((ROOT / "reports/ml/selection.json").read_text())
    bundle = joblib.load(ROOT / selection["model_path"])
    history = load_data(CSV_PATH)[LOAD_COLUMN]
    print(forecast_next_24(bundle, history, args.origin).to_string(index=False))


if __name__ == "__main__":
    main()
