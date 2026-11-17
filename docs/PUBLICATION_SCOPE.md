# Public source edition

Prepared on 17 November 2026. Publication requires the project owner's confirmation.

## Included

Original Python implementation, controlled tests, optional integration tests,
pinned requirements, Streamlit configuration, the MIT license and source notices.
The reference records contain model parameters, feature names, protocol and data
hashes, period boundaries, selection/test markers, counts and aggregate MAE/RMSE.
They do not contain timestamped demand observations or individual forecasts.

The reference selection and completion records intentionally preserve different
stages of the experiment. `test_evaluated: false` in the selection is the saved
pre-test state; the completion record records the later test. New experiments use
`.reproductions/` so these records are not overwritten.

## Omitted

All raw and processed measurements, all trained models, all per-origin predictions
and request examples, every figure and screenshot, data-profile tables, generated
reports, local environments, caches, secrets and the previous Git history.
The complete local project is preserved separately. This edition has a new Git
history, so omitted content is absent from its earlier commits as well.

The disabled manifest describes local asset sizes and digests; those descriptions
are not the assets and provide no download authorization. No Release is published.
Ignore rules also exclude newly generated media, data profiles and forecast outputs.

## Verification

See `verification.json` for the measured test counts and content checks.
Tests depending on the undistributed reference artifacts are explicitly skipped.
Controlled tests use artificial inputs and do not measure forecasting performance.
No training, data acquisition or final scientific evaluation is performed as part
of preparing this source edition.

A public copy is a code portfolio and reproducibility guide. Running the full
interface requires locally acquired data and generated artifacts under the
applicable source permissions. MIT applies to original code and documentation;
source measurements and dependency licenses are separate.
