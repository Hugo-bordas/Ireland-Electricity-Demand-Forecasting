# Prediction API

The FastAPI application serves a saved historical Random Forest and the saved
January–June 2020 forecasts. It does not download current demand, retrain models
or run a new evaluation on startup.

## Install and start

From the project root, activate a Python 3.13 environment and run:

```bash
python -m pip install -r requirements-all.txt
python -m scripts.download_artifacts --profile full --download
python -m scripts.download_artifacts --profile full --check
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The downloader checks exact sizes, SHA-256 digests and pinned experiment metadata.
The API verifies the selected model's hash and feature schema before loading it
once at startup. Use only the trusted project-owner Release: joblib can execute
code during deserialization. An independently reproduced model can also be used
from its own workspace, with that run's selection and saved predictions.

Open [Swagger UI](http://127.0.0.1:8000/docs) or
[OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

## Endpoints

| Method / path | Parameters | Success response | Error responses |
| --- | --- | --- | --- |
| `GET /health` | None | Object containing `status` and `artifacts` | 503 when either the model or historical predictions could not load |
| `GET /model-info` | None | Object with model, features, horizons, required history, versions, parameters, periods, hash and limitations | 503 when the verified model is unavailable |
| `GET /historical-forecast` | Required `origin_utc` query string in ISO 8601 UTC on a whole hour | Array of 24 points with `observed_mw` | 422 for invalid UTC input; 404 for an unavailable complete origin; 503 for missing predictions |
| `POST /predict` | JSON `origin_utc` and `history` | Array of 24 points, without `observed_mw` | 422 for invalid input; 503 for unavailable model or failed inference |

All successful forecast points contain `origin_utc`, integer `horizon` (1–24),
`target_utc`, numeric `predicted_mw` and `model`. Timestamps use UTC and demand
uses MW. Historical points additionally include numeric `observed_mw`.

## Verified requests and responses

Readiness with the model and forecasts installed:

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status":"ok","artifacts":{"random_forest":true,"historical_forecasts":true}}
```

Read a saved historical forecast:

```bash
curl --get http://127.0.0.1:8000/historical-forecast \
  --data-urlencode 'origin_utc=2020-02-03T02:00:00Z'
```

Generate predictions using the complete
[example request](../data/processed/phase3/example_request.json):

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H 'Content-Type: application/json' \
  --data-binary @data/processed/phase3/example_request.json
```

The example contains measurements from 27 January 2020 at 02:00 UTC through
3 February at 02:00 UTC. The response is a 24-element array. Its first element,
verified against the running API with the v1.0.0 model, is:

```json
{
  "origin_utc": "2020-02-03T02:00:00Z",
  "horizon": 1,
  "target_utc": "2020-02-03T03:00:00Z",
  "predicted_mw": 2720.116210539463,
  "model": "RandomForest"
}
```

The corresponding historical endpoint includes `"observed_mw": 2640.0` in
that point. Inference matches all 24 saved predictions for this origin within
1e-8 MW. This is a consistency check, not a new out-of-sample benchmark.

## Input validation and operational limits

The request must contain exactly 169 observations, ordered hourly from T−168
through T, with the last timestamp equal to `origin_utc`. Use explicit `Z` or
`+00:00` offsets and whole hours. Demands must be finite, nonnegative JSON
numbers. Missing observations, duplicates, gaps, reversed history, extra fields,
booleans and numeric strings are rejected. Inputs must fit the supported pandas
timestamp range (years 1678–2261).

For example, an empty `history` returns 422 with a `detail` array of
`location` and `message` objects. An unavailable saved origin such as
`2024-01-01T00:00:00Z` returns 404:

```json
{"detail":"No complete saved forecast exists for this UTC origin."}
```

Missing or inconsistent artifacts yield generic 503 errors. Request validation
does not echo the submitted history or internal file paths. Detailed failures go
to server logs.

The API has no authentication, rate limiting or live data connection and is
intended for local inspection. It assumes the measurement at T has already been
received. Publication delays, revisions and current-data accuracy are not
modelled. The public Streamlit demonstration reads saved results and does not
expose this API.
