"""Read phase 3 artifacts without loading, training or evaluating a model."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODEL = "RandomForest"
LABELS = {"RandomForest": "Random Forest", "HistGradientBoosting": "HistGradientBoosting",
          "Ridge": "Ridge", "DailyBaseline": "Previous day", "WeeklyBaseline": "Previous week"}
ARTIFACTS = {
    "selection": "reports/ml/selection.json",
    "completion": "reports/ml/test_completion.json",
    "validation_metrics": "reports/ml/validation_metrics.csv",
    "test_metrics": "reports/ml/test_metrics.csv",
    "validation_horizons": "reports/ml/validation_by_horizon.csv",
    "test_horizons": "reports/ml/test_by_horizon.csv",
    "splits": "reports/ml/split_counts.csv",
    "predictions": "data/processed/phase3/test_predictions.csv",
}


def load_results(root=ROOT):
    """Validate the stored evaluation before displaying historical performance."""
    root = Path(root)
    missing = [name for name in ARTIFACTS.values() if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError("Missing phase 3 artifacts: " + ", ".join(missing)
                                + ". Restore the saved files; the dashboard does not train models.")
    result = {}
    for name, relative in ARTIFACTS.items():
        path = root / relative
        result[name] = json.loads(path.read_text()) if path.suffix == ".json" else pd.read_csv(path)
    if result["selection"]["selected_model"] != MODEL or result["completion"]["selected_model"] != MODEL:
        raise ValueError("The saved evaluation must reference the selected Random Forest model.")
    if result["selection"]["model_sha256"] != result["completion"]["model_sha256"]:
        raise ValueError("The selection and final test refer to different model artifacts.")
    for period in ("validation", "test"):
        metrics = result[f"{period}_metrics"]
        required = {"model", "mae_mw", "rmse_mw"}
        if not required.issubset(metrics.columns) or metrics.model.duplicated().any():
            raise ValueError(f"Invalid {period} metrics table.")
        if MODEL not in metrics.model.values or not np.isfinite(metrics[["mae_mw", "rmse_mw"]]).all().all():
            raise ValueError(f"Missing or non-finite {period} model metrics.")
        if (metrics[["mae_mw", "rmse_mw"]] < 0).any().any():
            raise ValueError(f"Negative error metric in {period} results.")
        horizons = result[f"{period}_horizons"]
        for name, group in horizons.groupby("model"):
            if sorted(group.horizon.tolist()) != list(range(1, 25)):
                raise ValueError(f"Invalid {period} horizons for {name}.")
        if set(horizons.model) != set(metrics.model) or not np.isfinite(horizons[["mae_mw", "rmse_mw"]]).all().all():
            raise ValueError(f"Invalid {period} horizon metrics.")
    predictions = validate_predictions(result["predictions"])
    count = predictions.origin_utc.nunique()
    test_count = int(result["splits"].set_index("period").loc["test", "kept"])
    if count != test_count or count != result["completion"]["n_origins"]:
        raise ValueError("The saved test origin counts do not match the forecast file.")
    result["predictions"] = predictions
    return result


def validate_predictions(frame):
    required = {"origin_utc", "target_utc", "horizon", "observed_mw", MODEL,
                "DailyBaseline", "WeeklyBaseline"}
    if not required.issubset(frame.columns) or frame.empty:
        raise ValueError("The saved test forecast table is empty or missing required columns.")
    frame = frame.copy()
    for column in ("origin_utc", "target_utc"):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="raise")
        if frame[column].isna().any():
            raise ValueError("The forecast file contains missing timestamps.")
    numeric = ["horizon", "observed_mw", MODEL, "DailyBaseline", "WeeklyBaseline"]
    if not np.isfinite(frame[numeric]).all().all():
        raise ValueError("The saved forecasts contain missing or non-finite values.")
    if frame.duplicated(["origin_utc", "horizon"]).any():
        raise ValueError("Duplicate forecast horizons were found.")
    groups = frame.groupby("origin_utc").horizon
    if not ((groups.size() == 24) & (groups.min() == 1) & (groups.max() == 24)).all():
        raise ValueError("Each origin must have all 24 horizons.")
    if not frame.horizon.isin(range(1, 25)).all():
        raise ValueError("Forecast horizons must be integers from 1 to 24.")
    expected = frame.origin_utc + pd.to_timedelta(frame.horizon, unit="h")
    if not frame.target_utc.equals(expected):
        raise ValueError("Forecast targets do not align with origin + horizon.")
    if (frame.origin_utc < pd.Timestamp("2020-01-01", tz="UTC")).any() or (
        frame.target_utc >= pd.Timestamp("2020-07-01", tz="UTC")).any():
        raise ValueError("The explorer only accepts the saved January–June 2020 test forecasts.")
    return frame.sort_values(["origin_utc", "horizon"]).reset_index(drop=True)


def select_forecast(predictions, origin):
    """Return exactly one stored forecast and its display errors, never a new evaluation."""
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None or str(origin.tz) != "UTC":
        raise ValueError("Select an available forecast origin with an explicit UTC timezone.")
    selected = predictions.loc[predictions.origin_utc == origin].sort_values("horizon").copy()
    if selected.horizon.tolist() != list(range(1, 25)):
        raise ValueError("This origin does not have a complete saved 24-hour forecast.")
    selected["error_mw"] = selected[MODEL] - selected.observed_mw
    selected["absolute_error_mw"] = selected.error_mw.abs()
    return selected


def representative_origin(predictions):
    """Closest to median per-origin 24-hour MAE; chronological order breaks ties."""
    errors = (predictions[MODEL] - predictions.observed_mw).abs()
    per_origin = errors.groupby(predictions.origin_utc).mean().sort_index()
    if per_origin.empty:
        raise ValueError("No saved forecast origins are available.")
    return (per_origin - per_origin.median()).abs().idxmin()


def forecast_table(forecast):
    """One table for the displayed rows and CSV, without rounding saved predictions."""
    table = forecast[["origin_utc", "horizon", "target_utc", "observed_mw", MODEL,
                      "error_mw", "absolute_error_mw"]].copy()
    for column in ("origin_utc", "target_utc"):
        table[column] = table[column].dt.strftime("%Y-%m-%d %H:%M UTC")
    return table.rename(columns={"origin_utc": "Origin (UTC)", "horizon": "Horizon (h)",
        "target_utc": "Target (UTC)", "observed_mw": "Observed (MW)", MODEL: "Predicted (MW)",
        "error_mw": "Error (MW)", "absolute_error_mw": "Absolute error (MW)"}).reset_index(drop=True)
