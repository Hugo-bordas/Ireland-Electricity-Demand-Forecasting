# Reproduce and verify the experiment

Use Python 3.13. The reference dependencies are pinned in `requirements.txt`;
`requirements-all.txt` also installs the dashboard, API and test dependencies.
The historical quick demonstration requires only `dashboard/requirements.txt`.
No GPU, API key or training server is needed.

## A. Inspect the historical demonstration

Follow the [README quick start](../README.md#quick-start). The dashboard reads
the eight committed files listed in [deployment documentation](STREAMLIT_DEPLOYMENT.md#required-files).
It does not need a model binary, raw multi-country CSV or private local files.

With the full environment installed, check the saved reference outputs:

```bash
python -m scripts.download_artifacts --profile historical --check
python -m scripts.verify_results
python -W error::DeprecationWarning -m unittest discover -s tests -v
```

The result checker validates all 99,576 forecast rows and recomputes MAE/RMSE
for the selected model and both baselines, globally and at each horizon. It
checks the saved schema and periods against the implementation. This does not
retrain a model or rerun final-test inference.

Without the optional model, 15 API integration tests skip explicitly. For all
API tests, install the trusted v1.0.0 model with the README downloader commands,
then run the same suite. The [verification record](PORTFOLIO_VERIFICATION.md)
distinguishes local full-model checks from Linux CI.

## B. Train an independent experiment

From a clone's root, create and activate a Python 3.13 environment, then:

```bash
python -m pip install -r requirements-all.txt
PROJECT_ROOT="$PWD"
python -m scripts.create_reproduction .reproductions/run-01
cd .reproductions/run-01
python -m scripts.download_data
python -m scripts.explore_data
python -m scripts.analyze_patterns
python -m scripts.prepare_data
python -m scripts.train_forecast
python -m scripts.evaluate_test
python -m scripts.plot_forecast_results
python -m scripts.report_forecast_results
python -m scripts.verify_results --compare-to "$PROJECT_ROOT"
python -W error::DeprecationWarning -m unittest discover -s tests -v
```

Keep the original virtual environment active after changing directories; its
installed packages remain available. `run-01` must be a new direct child of
`.reproductions/`. The helper copies implementation, configuration and the frozen
protocol, but leaves source data, trained models and prior experiment outputs
out. This protects the published reference selection and test markers.

### Source acquisition and directory layout

Read [provenance](../data/SOURCES.md) and [data terms](DATA_TERMS.md) before
acquiring or reusing the data. The downloader requests the versioned
[OPSD package](https://data.open-power-system-data.org/time_series/2020-10-06/):

```text
data/raw/datapackage.json
data/raw/README.md
data/raw/time_series_60min_singleindex.csv
```

It verifies the CSV against the SHA-256 in OPSD's metadata. An existing CSV is
verified and reused. The upstream file is about 130 MB and contains multiple
countries; it stays local and ignored by Git. Parsing selects only
`utc_timestamp` and `IE_load_actual_entsoe_transparency`. Do not redistribute the
full source CSV under the project's Irish-data permission.

The published repository uses a permitted two-column Irish extract when present.
An empty reproduction workspace reads the original downloaded CSV. Those files
have different byte hashes even though the Irish field values agree.

### What the commands do

| Command | Output or responsibility |
| --- | --- |
| `explore_data` | Source coverage, missing values and first-week figure |
| `analyze_patterns` | Missing runs and calendar-pattern analysis |
| `prepare_data` | Exploratory **one-hour** feature table, `data/processed/irish_demand_features.csv` |
| `train_forecast` | Independently rebuilds the **24-horizon** inputs from the hourly observations; fits three families and freezes validation selection |
| `evaluate_test` | Loads the selected model, checks hashes and evaluates the held-out test with both baselines |
| `plot_forecast_results`, `report_forecast_results` | Figures and English summary from saved outputs |
| `verify_results --compare-to` | Recomputes saved test errors and compares validation/test scores, horizon scores and all split counts/dates with the reference |

The exploratory table is not an input to `train_forecast`. Its initial one-hour
lag convention differs from the final direct forecasting design. In the final
design y(T) is known, the 169-hour history ends at T, and targets are T+1…T+24.

### Expected artifacts

- `reports/ml/`: configuration, selection, validation/test scores, per-horizon
  scores, split counts and test opening/completion markers.
- `models/phase3/`: one bundle per model family, each with 24 regressors and
  metadata. The selected reference model is approximately 161 MiB.
- `data/processed/phase3/`: validation/test prediction rows and exclusion logs.
- `reports/figures/`: plots from the saved outputs.

Training stops if selection or test-opening markers already exist. Evaluation
stops if its test-opening marker exists. Reuse saved outputs or create another
independent workspace; do not delete the published markers to rerun a reference
test or tune against its results. Reproduction verifies a fixed experiment and
does not turn the observed test into fresh evidence for model selection.

## Inspect the reproduced application

From the experiment workspace, with the full environment active:

```bash
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

In a second terminal, activate the same environment and enter that workspace:

```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The reproduced model, selection and historical forecasts belong together. Do
not use the reference artifact downloader to overwrite a reproduced run: it pins
the reference metadata and deliberately rejects a mismatching experiment.
See the [API guide](API.md) for requests and responses.

## Reproducibility scope

The isolated reproduction on 17 November 2026 matched all saved validation/test
MAE and RMSE values and per-horizon scores within 1e-8 MW, with identical split
counts and dates. See the [verification record](PORTFOLIO_VERIFICATION.md).
Random Forest and HistGradientBoosting use seed 42; numerical thread pools are
limited to two threads. Fit times, creation timestamps and model binary hashes
can differ between runs. Other dependency versions or platforms may also change
floating-point arithmetic; numerical agreement is checked rather than assuming
byte-identical model files. Linux CI checks the frozen predictions and tests;
it does not retrain the experiment.
