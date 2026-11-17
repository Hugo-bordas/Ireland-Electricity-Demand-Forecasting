"""Check saved test scores without training or loading a model.

Run from the project root: python -m scripts.verify_results
Compare an independent run: python -m scripts.verify_results --compare-to /path/to/reference
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dashboard.data import MODEL, ROOT, load_results, validate_predictions
from scripts.forecast_data import FEATURE_COLUMNS, HORIZONS, PERIODS


TOLERANCE_MW = 1e-8


def verify_tables(predictions, metrics, horizons):
    """Recompute global and per-horizon errors from every saved forecast row."""
    frame = validate_predictions(predictions)
    if set(metrics.model) != {MODEL, "DailyBaseline", "WeeklyBaseline"}:
        raise ValueError("Expected the selected model and both test baselines.")
    for row in metrics.itertuples(index=False):
        errors = frame[row.model].to_numpy() - frame.observed_mw.to_numpy()
        values = [np.abs(errors).mean(), np.sqrt(np.square(errors).mean())]
        if not np.allclose(values, [row.mae_mw, row.rmse_mw], rtol=0, atol=TOLERANCE_MW):
            raise ValueError(f"Saved global test metrics disagree with predictions: {row.model}")
        saved = horizons.loc[horizons.model == row.model].sort_values("horizon")
        if saved.horizon.tolist() != list(HORIZONS):
            raise ValueError(f"Expected all 24 horizon scores: {row.model}")
        for item in saved.itertuples(index=False):
            subset = errors[frame.horizon.to_numpy() == item.horizon]
            expected = [np.abs(subset).mean(), np.sqrt(np.square(subset).mean())]
            if not np.allclose(expected, [item.mae_mw, item.rmse_mw], rtol=0, atol=TOLERANCE_MW):
                raise ValueError(f"Saved horizon metrics disagree with predictions: {row.model}, {item.horizon}")
    score = metrics.set_index("model").mae_mw
    return {"test_origins": int(frame.origin_utc.nunique()), "test_rows": len(frame),
            "horizons": len(HORIZONS), "selected_model": MODEL,
            "test_mae_mw": float(score[MODEL]),
            "weekly_baseline_mae_reduction_percent": float(100 * (1 - score[MODEL] / score.WeeklyBaseline))}


def compare_reference(root, reference):
    """Compare scientific outputs, excluding timestamps, fit duration and binary hashes."""
    for filename, keys, columns in (
        ("validation_metrics.csv", ["model"], ["mae_mw", "rmse_mw"]),
        ("test_metrics.csv", ["model"], ["mae_mw", "rmse_mw"]),
        ("validation_by_horizon.csv", ["model", "horizon"], ["mae_mw", "rmse_mw"]),
        ("test_by_horizon.csv", ["model", "horizon"], ["mae_mw", "rmse_mw"]),
    ):
        actual = pd.read_csv(Path(root) / "reports/ml" / filename).set_index(keys).sort_index()
        expected = pd.read_csv(Path(reference) / "reports/ml" / filename).set_index(keys).sort_index()
        if (not actual.index.equals(expected.index)
                or not np.allclose(actual[columns], expected[columns], rtol=0, atol=TOLERANCE_MW)):
            raise ValueError(f"Reproduced results differ from the reference: {filename}")
    actual = pd.read_csv(Path(root) / "reports/ml/split_counts.csv")
    expected = pd.read_csv(Path(reference) / "reports/ml/split_counts.csv")
    if not actual.equals(expected):
        raise ValueError("Reproduced split counts or dates differ from the reference.")


def verify_results(root=ROOT, compare_to=None):
    results = load_results(root)
    selection = results["selection"]
    periods = {name: list(bounds) for name, bounds in PERIODS.items()}
    if (selection["horizons"] != list(HORIZONS) or selection["features"] != FEATURE_COLUMNS
            or selection["periods_end_exclusive"] != periods):
        raise ValueError("Saved feature schema, horizons or periods disagree with the implementation.")
    summary = verify_tables(results["predictions"], results["test_metrics"], results["test_horizons"])
    if compare_to is not None:
        compare_reference(root, compare_to)
        summary["reference_metrics_and_splits_match"] = True
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-to", type=Path, help="Reference project root for an independent run")
    args = parser.parse_args()
    try:
        summary = verify_results(compare_to=args.compare_to)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Result verification failed: {error}\n")
    print(json.dumps(summary, indent=2))
    print("Saved results verified. No model loaded, trained or evaluated.")


if __name__ == "__main__":
    main()
