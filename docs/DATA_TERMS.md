# Irish data and trained-model terms

The project owner supplied a written response attributed to EirGrid's Data
Licensing Team. It permits use, reproduction, modification and public
redistribution of the Irish electricity data covered by the owner's request for
this non-commercial, open-source academic project. It expressly includes public
GitHub datasets, derived charts and dashboard screenshots, model training, and
public sharing of the resulting trained models and forecasts.

This preparation relies on that owner-supplied permission. The original
correspondence is kept privately by the owner. It is not an independently issued
license from this repository or a blanket commercial reuse grant.

## Attribution

Supported by EirGrid Group Data.

Original Irish electricity data source: EirGrid. Publication source: ENTSO-E
Transparency Platform. Data package: Open Power System Data (2020), *Data Package
Time series*, version 2020-10-06,
[DOI: 10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06).
No endorsement by EirGrid, ENTSO-E or OPSD is implied.

## Scope and transformations

`data/irish/irish_demand_hourly.csv` contains only `utc_timestamp` and
`IE_load_actual_entsoe_transparency`, selected from the OPSD hourly CSV with no
imputation or change to the field values. It contains 50,401 hourly rows. The
multi-country OPSD CSV is not redistributed.

The saved test export contains observations for the Irish series, forecasts and
seasonal baselines. The example request contains 169 Irish measurements. Charts
and screenshots display this experiment. The selected Random Forest model uses
past demand and the target calendar to forecast 24 hours. These transformations
must not be described as original measurements supplied by EirGrid.

## Separate licenses

The MIT license covers original project code and documentation. It does not
relicense the measurements, their representations or trained-model assets.
The supplied permission is limited to the stated non-commercial academic project
and requires appropriate credit to EirGrid and compliance with applicable license
conditions. Do not infer unrestricted commercial reuse or a right to license
unrelated European data. Obtain the applicable permission for a different use.

Reference links:

- [EirGrid Group Open Data Licence](https://www.smartgriddashboard.com/all/open-data-license/)
- [ENTSO-E terms and reuse lists](https://transparencyplatform.zendesk.com/hc/en-us/articles/40921911218961-Legal-Terms-and-Conditions)
- [OPSD package documentation](https://data.open-power-system-data.org/time_series/2020-10-06/README.md)

The project owner approved public GitHub publication and the v1.0.0 model Release
on 17 November 2026. That approval does not expand the data permission beyond the
stated non-commercial academic project.
