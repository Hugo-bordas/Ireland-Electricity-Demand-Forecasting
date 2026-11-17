# Portfolio verification

Checks for the recruiter-facing update, 17 November 2026. The original
[experiment verification](verification.json) remains unchanged as a historical
record; its old repository name predates the current GitHub name.

## Completed checks

- Cloned the public repository into a separate working directory. The coursework
  repository and original local experiment were not edited.
- Installed `requirements-dashboard.txt` from the package index in a new Python
  3.13.16 virtual environment on macOS Apple Silicon. Installed the smaller
  `dashboard/requirements.txt` in a second new environment using the downloaded
  package cache. Its four direct dependencies render all four dashboard sections
  with Streamlit AppTest, without scikit-learn or a model binary.
- Recomputed MAE and RMSE for Random Forest and both seasonal baselines from all
  99,576 saved prediction rows (4,149 origins × 24 horizons). Each matches the
  saved test table within 1e-10 MW. Random Forest's test MAE reduction against
  the previous-week baseline is 35.134161%, displayed as 35.1% in the README.
- Verified the nine reference metadata hashes in `artifacts/manifest.json`.
  Protocol, selection, splits, metrics and reference ML requirements are unchanged.
- Retrieved all five existing v1.0.0 Release assets from the canonical repository.
  Checked the three installable assets against the manifest's exact byte counts
  and SHA-256 digests, and checked every entry in the Release's `SHA256SUMS`.
  The Release terms match `docs/DATA_TERMS.md` byte for byte.
- Updated current Release links and the downloader's repository pointer to
  `Hugo-bordas/Ireland-Electricity-Demand-Forecasting`. The v1.0.0 tag and asset
  hashes remain unchanged. Corrected a CLI help reference to a missing document.
- Checked relative links and images in the README and documentation.

## Test suite

The clean clone without the model ran 80 tests in the existing reference Python
environment: 65 passed and 15 model-dependent API tests were explicitly skipped.
After installing `requirements-all.txt` from the package index in the new
environment and verifying the Release model before use, all 80 tests passed
with zero skips, failures or errors (6.891 seconds).

The test suite uses controlled fixtures for model fitting. No reference experiment
was retrained, no test selection was repeated, and no saved prediction or metric
was overwritten.

## Hosting limits

The fresh installs above ran on macOS. Streamlit Community Cloud, Linux builds,
public browser access and host resource usage have not been tested. The
[deployment assessment](STREAMLIT_DEPLOYMENT.md) records the proposed configuration,
the existing loopback binding and the hosting-permission question. No hosted URL
is claimed and no new dataset or Release asset was published.
