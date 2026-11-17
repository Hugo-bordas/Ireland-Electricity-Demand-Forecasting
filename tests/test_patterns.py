"""Vérifier le comptage des lacunes sur des exemples contrôlés."""

import unittest

import pandas as pd

from scripts.analyze_patterns import demand_profile, missing_runs


class MissingPatternsTests(unittest.TestCase):
    def test_runs_include_both_boundaries(self):
        load = pd.Series([None, 10, None, None, 20, None],
                         index=pd.date_range("2020-01-01", periods=6, freq="h", tz="UTC"))
        runs = missing_runs(load)
        self.assertEqual(runs["hours"].tolist(), [1, 2, 1])
        self.assertEqual(runs["at_boundary"].tolist(), [True, False, True])
        self.assertEqual(runs["start_utc"].iloc[1], load.index[2])
        self.assertEqual(runs["end_utc"].iloc[1], load.index[3])
        self.assertEqual(runs["hours"].sum(), load.isna().sum())

    def test_complete_and_fully_missing_series(self):
        index = pd.date_range("2020-01-01", periods=3, freq="h", tz="UTC")
        self.assertTrue(missing_runs(pd.Series([1, 2, 3], index=index)).empty)
        runs = missing_runs(pd.Series([float("nan")] * 3, index=index))
        self.assertEqual(runs["hours"].tolist(), [3])
        self.assertTrue(runs["at_boundary"].iloc[0])

    def test_profile_reports_observed_denominators(self):
        load = pd.Series([10, None, 30, 50],
                         index=pd.date_range("2020-01-01", periods=4, freq="h", tz="UTC"))
        profile = demand_profile(load, [0, 0, 1, 1])
        self.assertEqual(profile["mean_mw"].tolist(), [10, 40])
        self.assertEqual(profile["observed"].tolist(), [1, 2])
        self.assertEqual(profile["missing_pct"].tolist(), [50, 0])


if __name__ == "__main__":
    unittest.main()
