# Source and transformations

Supported by EirGrid Group Data.

Original source: EirGrid; published through ENTSO-E Transparency. Retrieved for
the reference experiment from Open Power System Data (2020), *Data Package Time
series*, version 2020-10-06,
[DOI: 10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06).
No endorsement is implied.

The committed `irish/irish_demand_hourly.csv` is a two-column Irish extract, with
50,401 rows and the same field strings and missing values as the upstream hourly
CSV. `utc_timestamp` marks interval starts in UTC and
`IE_load_actual_entsoe_transparency` is actual demand in MW. The SEM market-area
series and all non-Irish series are omitted.

The owner supplied written permission expressly covering public datasets, charts,
screenshots, trained models and forecasts for this non-commercial, open-source
academic project. See [the scope and conditions](../docs/DATA_TERMS.md).
The MIT license does not grant rights over the source measurements.

The code uses the committed Irish extract when present; in independent
reproduction workspaces without that extract, it can read the original locally
downloaded OPSD CSV. That multi-country file remains ignored by Git.
