# Prepared publication scope

Prepared on 17 November 2026. Nothing has been published. The owner's separate
confirmation is required before GitHub repository creation, push or Release.

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

## Planned Release

`v1.0.0` is a proposed tag, not a published Release. Its reviewed local assets are
`RandomForest.joblib`, `test_predictions.csv`, `example_request.json` and
`DATA_TERMS.md` and `SHA256SUMS`. Sizes and SHA-256 digests of the three installable assets are in
[the manifest](../artifacts/manifest.json). The model is about 161 MiB and remains
outside Git. It has not been uploaded. The terms accompany the assets.

The manifest's legal review is recorded as cleared within the supplied permission's
scope. Owner distribution authorization remains false and repository remains
unset until publication is approved. Network downloads therefore remain disabled.
The downloader does not load models or train them.

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
