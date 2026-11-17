"""Catch drift between displayed scores and the saved forecast rows."""

import unittest

from dashboard.data import load_results
from scripts.verify_results import verify_tables


class ResultVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = load_results()

    def test_reference_global_and_horizon_scores_match_all_saved_rows(self):
        summary = verify_tables(self.results['predictions'], self.results['test_metrics'],
                                self.results['test_horizons'])
        self.assertEqual(summary['test_rows'], 99576)
        self.assertEqual(summary['test_origins'], 4149)

    def test_changed_global_score_is_rejected(self):
        metrics = self.results['test_metrics'].copy()
        metrics.loc[0, 'rmse_mw'] += 1
        with self.assertRaisesRegex(ValueError, 'global test metrics'):
            verify_tables(self.results['predictions'], metrics, self.results['test_horizons'])

    def test_changed_horizon_score_is_rejected_even_with_correct_global_scores(self):
        horizons = self.results['test_horizons'].copy()
        horizons.loc[0, 'mae_mw'] += 1
        with self.assertRaisesRegex(ValueError, 'horizon metrics'):
            verify_tables(self.results['predictions'], self.results['test_metrics'], horizons)
