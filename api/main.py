"""Run locally with: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000."""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Annotated

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, AfterValidator, BeforeValidator, model_validator

from dashboard.data import MODEL, ROOT, select_forecast, validate_predictions
from scripts.forecast_data import FEATURE_COLUMNS, HORIZONS
from scripts.predict_forecast import forecast_next_24

LIMITATION = ("Historical research model, not a real-time electricity service. OPSD timestamps "
              "mark interval starts; the measurement at T must already have been received. "
              "Publication delays and revisions are not simulated. Recent-data accuracy is unknown.")
logger = logging.getLogger(__name__)


def require_timestamp_string(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("Use an ISO 8601 UTC timestamp string, with Z or +00:00.")
    return value


def validate_utc_hour(value):
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Timestamp must explicitly use UTC (Z or +00:00).")
    if value.minute or value.second or value.microsecond:
        raise ValueError("Timestamp must be on a whole hour.")
    # The existing pandas feature pipeline uses nanosecond timestamps.
    if not 1678 <= value.year <= 2261:
        raise ValueError("Timestamp is outside the supported pandas date range.")
    return value.astimezone(timezone.utc)


UTCHour = Annotated[datetime, BeforeValidator(require_timestamp_string), AfterValidator(validate_utc_hour)]
Demand = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp_utc: UTCHour
    demand_mw: Demand


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin_utc: UTCHour
    history: list[Observation] = Field(min_length=169, max_length=169)

    @model_validator(mode="after")
    def check_history(self):
        times = [row.timestamp_utc for row in self.history]
        if any(right - left != timedelta(hours=1) for left, right in zip(times, times[1:])):
            raise ValueError("History must be chronologically ordered, unique and spaced exactly one hour apart.")
        if times[-1] != self.origin_utc:
            raise ValueError("Origin must equal the last history timestamp; future measurements are forbidden.")
        return self


class ForecastPoint(BaseModel):
    origin_utc: datetime
    horizon: int
    target_utc: datetime
    predicted_mw: float = Field(allow_inf_nan=False)
    model: str
    observed_mw: float | None = None


def load_verified_model(root):
    """Only load the local selected artifact after verifying its recorded hash/schema."""
    selection = json.loads((root / "reports/ml/selection.json").read_text())
    path = root / "models/phase3/RandomForest.joblib"
    if (selection["selected_model"] != MODEL or selection["features"] != FEATURE_COLUMNS
            or selection["horizons"] != list(HORIZONS)
            or hashlib.sha256(path.read_bytes()).hexdigest() != selection["model_sha256"]):
        raise ValueError("Inconsistent model artifacts.")
    bundle = joblib.load(path)
    if (bundle["name"] != MODEL or bundle["metadata"]["features"] != FEATURE_COLUMNS
            or set(bundle["models"]) != set(HORIZONS)):
        raise ValueError("Inconsistent model schema.")
    for model in bundle["models"].values():
        if list(model.feature_names_in_) != FEATURE_COLUMNS or model.n_features_in_ != 11:
            raise ValueError("Inconsistent regressor feature order.")
    return selection, bundle


def forecast_records(frame, historical=False):
    return [{"origin_utc": row.origin_utc.to_pydatetime(), "horizon": int(row.horizon),
             "target_utc": row.target_utc.to_pydatetime(),
             "predicted_mw": float(getattr(row, MODEL) if historical else row.predicted_mw),
             "model": MODEL, **({"observed_mw": float(row.observed_mw)} if historical else {})}
            for row in frame.itertuples(index=False)]


def create_app(root=ROOT):
    """A separate app instance lets tests exercise missing artifacts without touching real files."""
    root = Path(root)

    @asynccontextmanager
    async def lifespan(app):
        app.state.bundle = app.state.selection = app.state.predictions = None
        app.state.predict_lock = Lock()
        try:
            app.state.selection, app.state.bundle = load_verified_model(root)
        except Exception:
            logger.exception("Selected model could not be loaded")
        try:
            app.state.predictions = validate_predictions(pd.read_csv(
                root / "data/processed/phase3/test_predictions.csv"))
        except Exception:
            logger.exception("Historical forecasts could not be loaded")
        yield
        app.state.bundle = app.state.predictions = None

    app = FastAPI(title="Irish Energy Forecast AI", version="1.0.0",
                  description=LIMITATION, lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Do not echo the request body, exception context or internal file paths.
        return JSONResponse(status_code=422, content={"detail": [
            {"location": list(item["loc"]), "message": item["msg"]}
            for item in error.errors()]})

    @app.get("/health")
    def health():
        """Readiness reflects successfully loaded artifacts, not merely existing files."""
        available = {"random_forest": app.state.bundle is not None,
                     "historical_forecasts": app.state.predictions is not None}
        ready = all(available.values())
        return JSONResponse(status_code=200 if ready else 503,
                            content={"status": "ok" if ready else "degraded", "artifacts": available})

    @app.get("/model-info")
    def model_info():
        """Training metadata checked against the loaded regressors; no new evaluation."""
        if app.state.bundle is None:
            raise HTTPException(503, "Verified Random Forest artifacts are unavailable. Restore them and restart the service.")
        metadata = app.state.bundle["metadata"]
        return {"model": MODEL, "horizons": list(HORIZONS), "features": FEATURE_COLUMNS,
                "required_history_hours": 169, "timezone": "UTC", "demand_unit": "MW",
                "training_period_end_exclusive": metadata["periods_end_exclusive"]["train"],
                "validation_period_end_exclusive": metadata["periods_end_exclusive"]["validation"],
                "strategy": metadata["strategy"], "selection_rule": metadata["selection_rule"],
                "parameters": metadata["model_parameters"][MODEL], "versions": metadata["versions"],
                "model_sha256": app.state.selection["model_sha256"], "limitations": LIMITATION}

    @app.get("/historical-forecast", response_model=list[ForecastPoint], response_model_exclude_none=True)
    def historical_forecast(origin_utc: Annotated[UTCHour, Query(description="Saved test origin, e.g. 2020-02-03T02:00:00Z")]):
        """Read a saved 24-hour forecast, including its observations. No model inference."""
        if app.state.predictions is None:
            raise HTTPException(503, "Historical forecasts are unavailable. Restore them and restart the service.")
        try:
            frame = select_forecast(app.state.predictions, pd.Timestamp(origin_utc))
        except ValueError:
            raise HTTPException(404, "No complete saved forecast exists for this UTC origin.") from None
        return forecast_records(frame, historical=True)

    @app.post("/predict", response_model=list[ForecastPoint], response_model_exclude_none=True)
    def predict(payload: PredictionRequest):
        """Predict T+1 through T+24 using exactly 169 complete measurements, T−168 through T."""
        if app.state.bundle is None:
            raise HTTPException(503, "Verified Random Forest artifacts are unavailable. Restore them and restart the service.")
        history = pd.Series([row.demand_mw for row in payload.history],
                            index=pd.DatetimeIndex([row.timestamp_utc for row in payload.history]), name="demand_mw")
        try:
            # The reused function temporarily sets process-wide numerical thread limits.
            with app.state.predict_lock:
                frame = forecast_next_24(app.state.bundle, history, payload.origin_utc)
            if not np.isfinite(frame.predicted_mw).all():
                raise ValueError("Non-finite model output")
            return forecast_records(frame)
        except Exception:
            logger.exception("Inference failed")
            raise HTTPException(503, "Prediction could not be produced with the loaded model.") from None

    return app


app = create_app()
