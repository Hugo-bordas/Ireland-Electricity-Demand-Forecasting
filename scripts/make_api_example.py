"""Print a valid API request using real OPSD measurements; never invent values."""

import argparse
from datetime import timedelta
import json

import pandas as pd

from scripts.explore_data import CSV_PATH, LOAD_COLUMN, load_data


def example_request(origin="2020-02-03T02:00:00Z"):
    origin = pd.Timestamp(origin)
    if str(origin.tz) != "UTC" or origin != origin.floor("h"):
        raise ValueError("Choose a whole-hour UTC origin.")
    load = load_data(CSV_PATH)[LOAD_COLUMN]
    history = load.reindex(pd.date_range(origin - timedelta(hours=168), origin, freq="h"))
    if history.isna().any():
        raise ValueError("The source does not contain 169 complete observations for this origin.")
    return {"origin_utc": origin.isoformat(), "history": [
        {"timestamp_utc": timestamp.isoformat(), "demand_mw": float(value)}
        for timestamp, value in history.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="2020-02-03T02:00:00Z")
    args = parser.parse_args()
    print(json.dumps(example_request(args.origin), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
