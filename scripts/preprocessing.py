"""Variables temporelles pour une demande cible à l'heure t, indexée en UTC."""

from numbers import Integral

import pandas as pd


def validate_hourly_index(frame):
    """Refuser les index ambigus : une ligne doit correspondre à une heure UTC."""
    index = frame.index
    if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != "UTC":
        raise ValueError("L'index doit être un DatetimeIndex en UTC.")
    if frame.empty or index.hasnans or not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("L'index doit être non vide, trié, unique et sans date manquante.")
    expected = pd.date_range(index.min(), periods=len(index), freq="h")
    if not index.equals(expected) or not (index == index.floor("h")).all():
        raise ValueError("L'index doit suivre une grille horaire complète, aux heures rondes.")


def positive_integer(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError("Les décalages, fenêtres et horizons doivent être des entiers positifs.")


def add_calendar_features(frame):
    """Ajouter le calendrier de l'heure cible ; lundi=0, dimanche=6."""
    validate_hourly_index(frame)
    result = frame.copy()
    result["hour"] = result.index.hour
    result["day_of_week"] = result.index.dayofweek
    result["month"] = result.index.month
    result["is_weekend"] = result.index.dayofweek >= 5
    return result


def add_lag_features(frame, target="demand_mw", lags=(1, 24, 168), horizon=1):
    """À la ligne t, lag_k = demande(t-k), avec k >= horizon de prévision."""
    validate_hourly_index(frame)
    positive_integer(horizon)
    result = frame.copy()
    for lag in lags:
        positive_integer(lag)
        if lag < horizon:
            raise ValueError("Un lag doit être au moins égal à l'horizon de prévision.")
        result[f"lag_{lag}h"] = frame[target].shift(lag)
    return result


def add_rolling_features(frame, target="demand_mw", windows=(24, 168), horizon=1):
    """Moyenne des w heures se terminant à t-horizon, avec w mesures requises."""
    validate_hourly_index(frame)
    positive_integer(horizon)
    result = frame.copy()
    past = frame[target].shift(horizon)
    for window in windows:
        positive_integer(window)
        result[f"rolling_mean_{window}h"] = past.rolling(
            window=window, min_periods=window
        ).mean()
    return result


def prepare_features(frame, target="demand_mw", lags=(1, 24, 168),
                     windows=(24, 168), horizon=1):
    """Conserver toutes les lignes et les NaN ; ne pas imputer ni normaliser."""
    result = add_calendar_features(frame)
    result = add_lag_features(result, target, lags, horizon)
    return add_rolling_features(result, target, windows, horizon)
