"""Exemples contrôlés réservés aux tests, distincts des données OPSD."""

import unittest

import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from scripts.preprocessing import (
    add_calendar_features, add_lag_features, add_rolling_features, prepare_features,
)


def sample(values, start="2020-01-03 22:00"):
    return pd.DataFrame({"demand_mw": values},
                        index=pd.date_range(start, periods=len(values), freq="h", tz="UTC"))


class PreprocessingTests(unittest.TestCase):
    def test_calendar_and_weekend_boundary(self):
        frame = sample([10, 20, 30])
        result = add_calendar_features(frame)
        self.assertEqual(result["hour"].tolist(), [22, 23, 0])
        self.assertEqual(result["day_of_week"].tolist(), [4, 4, 5])
        self.assertEqual(result["month"].tolist(), [1, 1, 1])
        self.assertEqual(result["is_weekend"].tolist(), [False, False, True])
        self.assertEqual(str(result.index.tz), "UTC")

    def test_month_and_year_boundary(self):
        result = add_calendar_features(sample([1, 2], "2020-12-31 23:00"))
        self.assertEqual(result["month"].tolist(), [12, 1])
        self.assertEqual(result["hour"].tolist(), [23, 0])

    def test_utc_keeps_hourly_steps_during_dst_change(self):
        result = add_calendar_features(sample([1, 2, 3, 4], "2020-10-25 00:00"))
        self.assertEqual(result["hour"].tolist(), [0, 1, 2, 3])

    def test_lags_align_with_past_values(self):
        result = add_lag_features(sample([10, 20, 30, 40]), lags=(1, 2))
        self.assertTrue(pd.isna(result["lag_1h"].iloc[0]))
        self.assertEqual(result["lag_1h"].iloc[1:].tolist(), [10, 20, 30])
        self.assertEqual(result["lag_2h"].iloc[2:].tolist(), [10, 20])

    def test_daily_and_weekly_lags(self):
        result = add_lag_features(sample(list(range(170))))
        self.assertEqual(result["lag_24h"].iloc[168], 144)
        self.assertEqual(result["lag_168h"].iloc[168], 0)

    def test_rolling_excludes_current_value(self):
        result = add_rolling_features(sample([10, 20, 1000, 40]), windows=(2,))
        self.assertTrue(result["rolling_mean_2h"].iloc[:2].isna().all())
        self.assertEqual(result["rolling_mean_2h"].iloc[2], 15)
        self.assertEqual(result["rolling_mean_2h"].iloc[3], 510)

    def test_missing_values_remain_missing(self):
        result = prepare_features(sample([10, None, 30, 40, 50]), lags=(1,), windows=(2,))
        self.assertTrue(pd.isna(result["demand_mw"].iloc[1]))
        self.assertTrue(pd.isna(result["lag_1h"].iloc[2]))
        self.assertTrue(result["rolling_mean_2h"].iloc[2:4].isna().all())
        self.assertEqual(result["rolling_mean_2h"].iloc[4], 35)

    def test_current_and_future_changes_do_not_change_features(self):
        frame = sample([10, 20, 30, 40, 50, 60])
        changed = frame.copy()
        changed.iloc[3:, 0] = 9999
        original = prepare_features(frame, lags=(1, 2), windows=(2,))
        modified = prepare_features(changed, lags=(1, 2), windows=(2,))
        assert_frame_equal(original.drop(columns="demand_mw").iloc[:4],
                           modified.drop(columns="demand_mw").iloc[:4])

    def test_longer_forecast_horizon(self):
        frame = sample([10, 20, 30, 40, 50])
        result = prepare_features(frame, lags=(2,), windows=(2,), horizon=2)
        self.assertEqual(result["lag_2h"].iloc[3], 20)
        self.assertEqual(result["rolling_mean_2h"].iloc[3], 15)
        changed = frame.copy()
        changed.iloc[2:, 0] = 9999
        modified = prepare_features(changed, lags=(2,), windows=(2,), horizon=2)
        assert_series_equal(result.drop(columns="demand_mw").iloc[3],
                            modified.drop(columns="demand_mw").iloc[3])

    def test_input_is_not_mutated(self):
        frame = sample([10, 20, 30])
        before = frame.copy(deep=True)
        result = prepare_features(frame, lags=(1,), windows=(2,))
        assert_frame_equal(frame, before)
        self.assertTrue(result.index.equals(frame.index))
        self.assertEqual(len(result), len(frame))

    def test_invalid_indexes_are_rejected(self):
        frame = sample([10, 20, 30])
        invalid = [frame.iloc[::-1], frame.iloc[[0, 0, 1]], frame.iloc[[0, 2]],
                   frame.tz_localize(None), frame.tz_convert("Europe/Dublin"), frame.iloc[:0]]
        off_hour = frame.copy()
        off_hour.index = pd.date_range("2020-01-01 00:30", periods=3, freq="h", tz="UTC")
        invalid.append(off_hour)
        missing_date = frame.copy()
        missing_date.index = pd.DatetimeIndex([frame.index[0], pd.NaT, frame.index[2]])
        invalid.append(missing_date)
        for item in invalid:
            with self.subTest(index=item.index), self.assertRaises(ValueError):
                prepare_features(item)

    def test_invalid_parameters_are_rejected(self):
        frame = sample([10, 20, 30])
        for value in (0, -1, 1.5, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    add_lag_features(frame, lags=(value,))
                with self.assertRaises(ValueError):
                    add_rolling_features(frame, windows=(value,))
                with self.assertRaises(ValueError):
                    prepare_features(frame, horizon=value)
        with self.assertRaises(ValueError):
            add_lag_features(frame, lags=(1,), horizon=24)


if __name__ == "__main__":
    unittest.main()
