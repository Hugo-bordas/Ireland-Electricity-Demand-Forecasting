"""Write an English experiment summary from saved metrics; never fit or predict."""

import json

import pandas as pd

from scripts.train_forecast import REPORT_DIR


def metric_table(frame):
    rows = ["| Method | MAE (MW) | RMSE (MW) |", "| --- | ---: | ---: |"]
    for row in frame.itertuples():
        rows.append(f"| {row.model} | {row.mae_mw:.2f} | {row.rmse_mw:.2f} |")
    return "\n".join(rows)


def main():
    selection = json.loads((REPORT_DIR / "selection.json").read_text())
    splits = pd.read_csv(REPORT_DIR / "split_counts.csv")
    validation = pd.read_csv(REPORT_DIR / "validation_metrics.csv")
    test = pd.read_csv(REPORT_DIR / "test_metrics.csv")
    selected = selection["selected_model"]
    test_mae = test.set_index("model").loc[selected, "mae_mw"]
    split_rows = ["| Period | Candidate origins | Retained origins | Boundary | Short history | Missing features | Missing targets |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in splits.itertuples():
        split_rows.append(f"| {row.period} | {row.candidates} | {row.kept} | {row.boundary_24h} | "
                          f"{row.insufficient_history} | {row.missing_features} | {row.missing_targets} |")
    improvements = []
    for baseline in ("DailyBaseline", "WeeklyBaseline"):
        baseline_mae = test.set_index("model").loc[baseline, "mae_mw"]
        gain = 100 * (1 - test_mae / baseline_mae)
        improvements.append(f"- Test MAE reduction against {baseline}: {gain:.2f}%.")
    report = f"""# Electricity demand forecasting: saved experiment results

## Examples and temporal split

Each origin T predicts the next 24 hourly demands, T+1 through T+24. Training
uses 2015–2018, validation uses 2019 and the final test uses January–June 2020.
Incomplete inputs or targets are excluded without imputation. All methods use
the same origins. Exclusion reasons are exclusive and additive.

{chr(10).join(split_rows)}

Exact first/last origins and targets are in `split_counts.csv`. Per-origin
exclusions are in `data/processed/phase3/*_exclusions.csv`.

## Model selection

Selected model: **{selected}**, using validation MAE (then RMSE and name for ties).
There is one fixed configuration per family and 24 independent regressors per
family. No validation refit is performed. The 11 inputs use only demand at or
before T and the known UTC target calendar. Ridge preprocessing fits training
only. Exact features, parameters and versions are in `training_config.json`.

### Validation: 2019

{metric_table(validation)}

### Held-out test: January–June 2020

{metric_table(test)}

{chr(10).join(improvements)}

Only the selected model and two baselines are evaluated on the test. Selection
metadata predates the test; opening/completion markers record its evaluation.
Global MAE averages absolute errors over all origin–horizon pairs. Global RMSE
is the square root of mean squared error over those same pairs, rather than
the average of horizon-specific RMSEs. Per-horizon scores are saved separately.

## Interpretation and limitations

Forecasts are issued hourly using newly available observations. This is not a
six-month forecast issued in January. Overlapping forecast windows produce
correlated errors. Demand at T is assumed available; publication delays and
revisions are not simulated. Complete-case evaluation does not assess service
availability under missing inputs. Weather, holidays, local daylight-saving time
and prediction intervals are outside this version. A single validation year and
one configuration per family do not establish general model superiority or
accuracy on recent demand.

This summary reads saved outputs only. The dashboard displays historical
predictions; API inference uses the saved selected model and supplied history.
Neither interface retrains the model or supplies a live electricity data feed.
"""
    destination = REPORT_DIR / "results.md"
    destination.write_text(report, encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
