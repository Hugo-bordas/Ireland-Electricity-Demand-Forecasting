# Streamlit demonstration deployment assessment

Assessed on 17 November 2026. The historical dashboard is a suitable candidate
for Streamlit Community Cloud: it reads committed results and needs neither the
161 MiB model nor training, an API service, credentials or an upstream data download.
No hosted deployment or public demo URL has been verified.

## Proposed configuration

| Setting | Value |
| --- | --- |
| Repository | `Hugo-bordas/Ireland-Electricity-Demand-Forecasting` |
| Branch | `main` |
| Entrypoint | `dashboard/app.py` |
| Python | Select 3.13 in Advanced settings |
| Dashboard dependencies | `dashboard/requirements.txt` |
| Configuration | `.streamlit/config.toml` at repository root |
| Data | Existing Irish extract, saved forecasts and `reports/ml/` metadata |
| Model download / training | None |
| Secrets | None required by the app |

The new dependency file sits beside the entrypoint, following Streamlit's
[documented subdirectory layout](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/file-organization).
It includes only NumPy, pandas, Streamlit and Altair as direct dependencies, at
the reference versions. The root `requirements.txt` is for the ML environment;
it does not include Streamlit. Keep the dashboard-specific file when deploying.
See [dependency configuration](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/app-dependencies)
and [deployment settings](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/deploy).

## Checks before publishing a hosted demo

1. Establish that the project's data permission also covers serving these
   observations, visuals and downloadable CSV rows through the chosen host.
   The [recorded terms](DATA_TERMS.md) describe public GitHub publication and
   project outputs; the private correspondence has not been reinterpreted as
   an explicit hosting grant. Do not add other data or upload private evidence.
2. Review the server binding for the hosting platform. The current config fixes
   `server.address` to `127.0.0.1` for local use. A host must be able to route
   requests to the process; adjust that setting in the deployment configuration
   if required, then verify the hosted health endpoint. This assessment leaves
   the local binding unchanged.
3. Build on Community Cloud with Python 3.13 and confirm the dependency file in
   the build log. A fresh macOS installation and all four sections were checked
   locally; Linux builds, host memory and cold starts still need observation.
4. Check Overview, Forecast Explorer, Model Performance and Methodology in the
   hosted browser. Change forecast date/hour, switch validation/test, download
   a CSV and verify its 24 rows against the displayed forecast. Confirm that
   metrics still show test MAE 78.44 MW and RMSE 117.16 MW.
5. Check that EirGrid attribution and historical-use limitations remain visible.
   Add the public URL to the README only after these checks pass.

## Why keep inference separate?

The demo already exposes the completed experiment without deserializing a model.
FastAPI inference additionally needs the trusted reference model and its recorded
ML dependency versions. The API has no authentication and is documented for local
use. A public inference service needs a separate deployment review.

No Release asset, source dataset, scientific result or model parameter was changed
for this assessment. See [portfolio verification](PORTFOLIO_VERIFICATION.md) for
completed checks and [publication scope](PUBLICATION_SCOPE.md) for existing assets.
