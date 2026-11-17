# Publication scope

The owner approved public GitHub publication and the v1.0.0 Release on
17 November 2026. This approval covers the repository and assets listed below.

## Git repository

Original code, tests, pinned requirements, the frozen protocol, reference metrics
and configuration; one Irish two-column historical dataset; saved Irish test
forecasts and an example request; three real dashboard screenshots and eight
experiment figures. All third-party data and resulting model assets are subject
to [the separate data terms](DATA_TERMS.md), including the non-commercial academic
scope and attribution. The code remains MIT.

The owner-supplied EirGrid response explicitly covers the stated Irish dataset,
derived visuals, model training and public sharing of trained models and forecasts.
The private permission image is not included in this repository.

## Reference Release

The [v1.0.0 Release](https://github.com/Hugo-bordas/Ireland-Electricity-Demand-Forecasting/releases/tag/v1.0.0)
contains the reviewed assets
`RandomForest.joblib`, `test_predictions.csv`, `example_request.json`,
`DATA_TERMS.md` and `SHA256SUMS`. Sizes and SHA-256 digests of the three installable
assets are in
[the manifest](../artifacts/manifest.json). The model is about 161 MiB and remains
outside Git. The terms accompany the assets.

The manifest's legal review is recorded as cleared within the supplied permission's
scope. The repository was published under `Hugo-bordas/irish-energy-forecast-ai`
and is now named `Hugo-bordas/Ireland-Electricity-Demand-Forecasting`.
The pinned tag remains `v1.0.0`. The downloader verifies the reference assets and metadata;
it does not load models or train them.

## Excluded

The complete multi-country source CSV, non-Irish observations, private email
correspondence, credentials, environments, caches and the original project's Git
history. New unrelated data or models are not automatically approved by this scope.
The complete original local project is preserved separately.

## Verification

See [verification.json](verification.json) for checks actually completed.
The full local suite runs with the staged reference model. A clone without that
large model skips inference integration tests explicitly; the historical dashboard
can use the committed forecast export without downloading a model.

Reference selection and completion records preserve their respective experiment
stages. `test_evaluated: false` in selection is its pre-test state. Independent
experiments use `.reproductions/` rather than overwriting these records.
