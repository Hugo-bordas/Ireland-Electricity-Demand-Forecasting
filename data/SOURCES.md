# Data provenance and rights

The local reference experiment used Open Power System Data (2020), *Data Package
Time series*, version 2020-10-06,
[DOI: 10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06).
Primary measurements were published on ENTSO-E Transparency.

The code selects `utc_timestamp` and `IE_load_actual_entsoe_transparency` from the
[hourly package](https://data.open-power-system-data.org/time_series/2020-10-06).
The latter represents actual total load for Ireland, in MW. It is distinct from
`IE_sem_load_actual_entsoe_transparency`. Timestamps mark interval starts in UTC.

This source edition contains no measurements. The original package metadata
contains no `licenses` field, and its README supplies attribution without a blanket
open license for all measurements. See [OPSD legal context](https://open-power-system-data.org/legal/)
and [ENTSO-E terms and reuse lists](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions).

The reviewed ENTSO-E list covers specified categories and does not establish a
general redistribution permission for the actual-load series used here. Review
source permissions before downloading, reusing or redistributing data. The original
code license does not relicense third-party measurements. No endorsement is implied.

Local transformations include selecting the Irish hourly series, excluding
incomplete examples, constructing past-only features, fitting direct models and
computing aggregate errors. Only aggregate evaluation statistics and experiment
configuration accompany the public code. Predictions per origin, observations,
trained models, figures and screenshots are omitted.
