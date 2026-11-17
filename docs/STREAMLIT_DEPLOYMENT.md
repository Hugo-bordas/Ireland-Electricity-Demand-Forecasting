# Streamlit deployment and local demonstration

The existing historical dashboard is deployed on Streamlit Community Cloud:

**[Open Ireland Electricity Demand Forecasting](https://ireland-electricity-demand-forecasting.streamlit.app/)**

This application explores saved January–June 2020 forecasts. It does not train,
load a Random Forest binary, call the API or obtain current demand observations.
The public URL and Overview metrics were observed on 17 November 2026. The owner
also confirmed that the public demonstration and its navigation work. See the
[verification record](PORTFOLIO_VERIFICATION.md) for the limits of automated
public-browser checks.

## Configuration

| Setting | Deployed configuration |
| --- | --- |
| Repository | `Hugo-bordas/Ireland-Electricity-Demand-Forecasting` |
| Branch | `main` |
| Entrypoint | `dashboard/app.py` |
| Python | 3.13, selected in Advanced settings |
| Dependencies | `dashboard/requirements.txt` |
| Theme and server configuration | `.streamlit/config.toml` at repository root |
| Secrets, model download, training | None |

Community Cloud [searches for dependency files beside the entrypoint before the repository root](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/app-dependencies).
The dashboard-specific requirements pin NumPy, pandas, Streamlit and Altair.
The root ML requirements remain unchanged. The fixed loopback address was removed
from the shared server config so the hosting runtime can supply its binding.
For local use, explicitly bind to loopback:

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

## Required files

The eight files read by `dashboard.data.load_results` are:

```text
reports/ml/selection.json
reports/ml/test_completion.json
reports/ml/validation_metrics.csv
reports/ml/test_metrics.csv
reports/ml/validation_by_horizon.csv
reports/ml/test_by_horizon.csv
reports/ml/split_counts.csv
data/processed/phase3/test_predictions.csv
```

All are committed. The dashboard validates model references, horizon coverage,
finite values, target dates and forecast counts before rendering. It restricts
the explorer to saved complete origins. Missing or invalid artifacts produce a
generic public error; diagnostic details are logged server-side. No private file
or upstream multi-country CSV is needed. The included Irish source extract and
API example are not dashboard runtime requirements.

## Deployment and verification procedure

In [Community Cloud](https://share.streamlit.io/), choose **Create app → Deploy
from repo**, select this repository and `main`, and set the entrypoint and Python
version above. No secrets are required. Follow Streamlit's
[file layout](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/file-organization)
and [deployment instructions](https://docs.streamlit.io/deploy/community-cloud/deploy-your-app/deploy).

After a change:

1. Verify that Overview shows MAE 78.44 MW, RMSE 117.16 MW and 4,149 origins.
2. In Forecast Explorer, change date and hour, show the baseline and export the
   selected 24 rows. Compare the CSV with the displayed values.
3. In Model Performance, switch between validation and test: validation has five
   methods and test has three. Check the horizon plot.
4. Open Methodology and confirm the historical scope and limitations.
5. Confirm that EirGrid attribution remains visible and inspect startup logs if
   the app reports unavailable results. Check public access from a browser that
   is not signed in as the owner.

Local AppTest exercises all four sections, date/hour changes, baseline selection,
chart values, CSV consistency and missing-file errors. A clean minimal runtime
also renders the four sections without scikit-learn or the model. Linux CI checks
the full test suite with explicit model-dependent skips. These checks complement
public-browser testing; they do not measure hosting uptime, cold starts or
memory under concurrent traffic.

## Data and service scope

The deployment uses the same Irish outputs already published under the
[recorded data terms](DATA_TERMS.md) for this non-commercial academic project.
No new dataset, model asset, private correspondence or secret was uploaded.
Keep the required EirGrid attribution and applicable restrictions. Publication
does not confer rights for another project or unrestricted commercial reuse.

FastAPI remains a local inference interface, with a separate 161 MiB model and
its ML dependencies. It has no authentication and is not exposed through this
demonstration. A public inference service would need its own operational review.
