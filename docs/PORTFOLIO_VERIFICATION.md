# Portfolio audit and verification

Final audit: 17 November 2026. The original [experiment receipt](verification.json)
and all scientific reference files remain unchanged. Work used a fresh clone of
`main`; unrelated local repositories and existing working-directory changes were
left intact.

## Findings and priorities

| Priority | Finding | Resolution |
| --- | --- | --- |
| Critical before public hosting | Dashboard errors echoed raw exception text, potentially including local paths | Generic visitor error; detailed server logging; regression test |
| Important | No automated GitHub verification | Read-only Linux CI verifies artifact hashes, recomputes saved errors and runs the suite; action versions pinned to official commit hashes |
| Important | Full reproduction had not been demonstrated during the first portfolio pass | Completed an isolated run from the original OPSD CSV and compared all scores, horizon scores and split records |
| Important | Exploratory one-hour features could be confused with final 24-horizon inputs | Explicit separation in the README and reproduction guide |
| Important | Generated experiment report contained outdated environment and pre-dashboard statements | English summary now derives its numbers from saved files and describes the current interfaces accurately |
| Important | Recruiters needed local setup to access the dashboard | Created the Community Cloud deployment and documented its public URL and runtime files |
| Important | Required EirGrid attribution was not present in the dashboard sidebar | Added the attribution and source/non-endorsement note |
| Optional | Dense README and scattered technical detail | Prominent results and screenshot; compact navigation; separate API and reproduction guides |

No methodological correction or change to published metrics was required.

## Tests and dependency installation

- Fresh Python 3.13.16 macOS environments were installed during the initial
  portfolio pass from the package index. A second environment uses only the
  dashboard's four direct requirements; all four sections render there without
  scikit-learn or a model binary.
- The expanded local suite with the verified v1.0.0 model ran **83 tests, all
  passed**, with no skips. It includes feature invariance under future-data
  changes, split boundaries, global RMSE calculation, artifact validation, API
  input errors, real-model inference, dashboard interactions and saved-score drift.
- The isolated reproduced experiment also ran **83 tests, all passed**, with no
  skips. Its scientific outputs remain local in the ignored workspace.
- [Linux CI](https://github.com/Hugo-bordas/Ireland-Electricity-Demand-Forecasting/actions/runs/44009144664)
  installed the full requirements and passed: **83 tests, 68 passed and 15
  model-dependent API tests explicitly skipped**. Artifact hashes and the result
  verifier passed too. CI does not download a model or retrain the experiment.

Commands:

```bash
python -m scripts.download_artifacts --profile full --check
python -m scripts.verify_results
python -W error::DeprecationWarning -m unittest discover -s tests -v
```

## Scientific verification and full reproduction

The saved selection, implementation and original frozen protocol agree on
Random Forest, horizons T+1…T+24, 11 inputs, train 2015–2018, validation 2019 and
test January–June 2020. Feature code uses demand at or before T and the known UTC
target calendar. Ridge preprocessing is fitted on training only. Period-end
purges keep all targets in their split. Selection does not read 2020 observations.

The result verifier recomputed all three methods' global and per-horizon test
MAE/RMSE from all 99,576 prediction rows (4,149 origins). Scores match within
1e-8 MW. Random Forest test MAE is 78.4396423739622 MW and RMSE is
117.15723636284176 MW. MAE reduction against the previous-week baseline is
35.13416108536187%, displayed as 35.13%.

An independent workspace was created using `scripts.create_reproduction`.
The existing original 130,339,665-byte OPSD CSV was copied locally after hash
verification; the downloader fetched fresh metadata and documentation and
rechecked the CSV hash against that metadata. The entire CSV was not downloaded
again. The documented exploration, pattern analysis, one-hour preparation,
three-family training, selected-model test evaluation, plotting and English
report commands ran successfully. No parameter was tuned after comparison.

```bash
python -m scripts.create_reproduction .reproductions/run-01
# From that new workspace, after the source/reproduction commands:
python -m scripts.verify_results --compare-to /path/to/reference/clone
```

The independent run matched all validation/test MAE and RMSE values, all
per-horizon score tables (absolute tolerance 1e-8 MW), and every split count/date.
Model file hashes, creation timestamps and fit times are not expected to be
identical. The published data, predictions, scientific metadata, protocol and
manifest were compared byte-for-byte with the pre-audit commit and preserved.

## API verification

Started Uvicorn on loopback and sent actual HTTP requests:

- `/health`: 200 and both artifacts available.
- `/model-info`: 200, 24 horizons and 11 features.
- `/historical-forecast`: 200 with 24 saved points; unavailable origin: 404.
- `/predict`: 200 with 24 forecasts; incomplete history: 422.
- `/docs`: 200.

For the included 3 February 2020 example, all 24 inferred predictions match the
saved values within 1e-8 MW. The [API guide](API.md) shows a response obtained from
the running service. The existing tests also exercise missing/corrupt artifacts,
UTC rules, malformed inputs and generic failure responses. The API contract and
model behavior were not changed.

## Dashboard and public deployment

Deployed the existing `dashboard/app.py` on Community Cloud with Python 3.13,
its minimal requirements, no secrets and no model download:

**[Public historical dashboard](https://ireland-electricity-demand-forecasting.streamlit.app/)**

The public Overview was read in Chrome without a Streamlit owner session, showing
78.44 MW, 117.16 MW, 24 hours and 4,149 origins. Later automated browser attempts
encountered blank pages and a CONNECTING state, so a complete automated public
navigation/date/export check was not established. The owner independently
confirmed that the public URL, Forecast Explorer and Model Performance work.
Local AppTest covers all sections, date/hour changes, baseline visibility, chart
values and CSV/display equality, including a high-error forecast. Missing-file
errors now avoid exposing diagnostic paths.

The existing three authentic application screenshots were reviewed against the
interface and saved values. Each is 1440 × 1400 pixels and under 102 KB. Image
files were preserved; no fabricated image or replacement screenshot was added.
They predate the additional sidebar attribution. Public-host uptime, cold starts,
concurrent load and long-running availability have not been measured.

## Release, rights and repository hygiene

The existing [v1.0.0 Release](https://github.com/Hugo-bordas/Ireland-Electricity-Demand-Forecasting/releases/tag/v1.0.0)
contains the same five assets. Its three installable artifacts were checked
against exact manifest sizes and SHA-256 digests; every `SHA256SUMS` entry was
checked, and Release terms match the repository terms. The tag and Release were
not edited. Current code changes preserve the selected model schema and hashes.

Source documentation and the [EirGrid licence](https://www.smartgriddashboard.com/all/open-data-license/)
were consulted. Public assets continue to rely on the specific owner-supplied
Irish-data permission documented in [DATA_TERMS.md](DATA_TERMS.md); private
correspondence was not published or independently authenticated. The MIT code
license was not changed and does not relicense data, models or dependencies.

Tracked files were checked for credentials/private-key patterns, absolute user
paths, caches, environments and unexpected large binaries. No matching exposed
secret or private file was found; this is a focused audit, not a full security
certification. The existing prediction export and source extract remain the
reviewed scientific artifacts. Training outputs, original multi-country data,
model binaries, caches and permission evidence remain ignored. Relative links,
README image paths and the final GitHub rendering are checked before delivery.
