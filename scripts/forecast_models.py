"""Un régresseur indépendant par horizon, sans récursion des prédictions."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from scripts.forecast_data import CALENDAR_COLUMNS, NUMERIC_COLUMNS, HORIZONS


MODEL_NAMES = ("Ridge", "RandomForest", "HistGradientBoosting")
# Fixés avant toute évaluation ; pas de recherche d'hyperparamètres en phase 3.
MODEL_PARAMETERS = {
    "Ridge": {"alpha": 10.0},
    "RandomForest": {"n_estimators": 80, "max_depth": 14, "min_samples_leaf": 5,
                     "random_state": 42, "n_jobs": 2},
    "HistGradientBoosting": {"max_iter": 150, "max_leaf_nodes": 15, "learning_rate": 0.1,
                             "l2_regularization": 1.0, "early_stopping": False,
                             "random_state": 42},
}


def make_model(name):
    if name == "Ridge":
        # Ajustement du scaler sur l'entraînement uniquement, dans la pipeline.
        transform = ColumnTransformer([
            ("calendar", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CALENDAR_COLUMNS),
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
        ])
        return make_pipeline(transform, Ridge(**MODEL_PARAMETERS[name]))
    if name == "RandomForest":
        return RandomForestRegressor(**MODEL_PARAMETERS[name])
    if name == "HistGradientBoosting":
        return HistGradientBoostingRegressor(**MODEL_PARAMETERS[name])
    raise ValueError(f"Modèle inconnu : {name}")


def fit_direct_models(name, features, targets, origins):
    models = {}
    for horizon in HORIZONS:
        model = make_model(name)
        model.fit(features[horizon].loc[origins], targets.loc[origins, horizon])
        models[horizon] = model
        if horizon % 6 == 0:
            print(f"{name} : {horizon}/24 horizons entraînés", flush=True)
    return models


def predict_direct(models, features, origins):
    if set(models) != set(HORIZONS):
        raise ValueError("Il faut exactement un modèle pour chacun des 24 horizons.")
    return np.column_stack([models[h].predict(features[h].loc[origins]) for h in HORIZONS])
