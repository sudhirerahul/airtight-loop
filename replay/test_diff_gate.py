"""Unit tests for diff_gate's pure comparison logic (no git/mvn/java needed).
Run with: python3 -m unittest replay/test_diff_gate.py -v
"""

from __future__ import annotations

import unittest

from diff_gate import diff_summaries


class DiffSummariesTest(unittest.TestCase):
    def test_identical_summaries_pass_clean(self):
        summary = {"markets": {"E1": {"pnl_by_order": {"o1": 100, "o2": -100}, "fill_count": 1}},
                   "wall_clock_millis": 50}
        block, warn = diff_summaries(summary, summary)
        self.assertEqual([], block)
        self.assertEqual([], warn)

    def test_pnl_divergence_blocks(self):
        baseline = {"markets": {"E1": {"pnl_by_order": {"o1": 100, "o2": -100}, "fill_count": 1}},
                    "wall_clock_millis": 50}
        candidate = {"markets": {"E1": {"pnl_by_order": {"o1": 99, "o2": -99}, "fill_count": 1}},
                     "wall_clock_millis": 50}
        block, warn = diff_summaries(baseline, candidate)
        self.assertEqual(2, len(block))
        self.assertIn("o1", block[0])

    def test_market_missing_from_candidate_blocks(self):
        baseline = {"markets": {"E1": {"pnl_by_order": {"o1": 50}, "fill_count": 1}}, "wall_clock_millis": 10}
        candidate = {"markets": {}, "wall_clock_millis": 10}
        block, warn = diff_summaries(baseline, candidate)
        self.assertEqual(1, len(block))

    def test_latency_regression_over_threshold_warns_only(self):
        baseline = {"markets": {}, "wall_clock_millis": 100}
        candidate = {"markets": {}, "wall_clock_millis": 130}
        block, warn = diff_summaries(baseline, candidate)
        self.assertEqual([], block)
        self.assertEqual(1, len(warn))

    def test_latency_regression_under_threshold_is_silent(self):
        baseline = {"markets": {}, "wall_clock_millis": 100}
        candidate = {"markets": {}, "wall_clock_millis": 110}
        block, warn = diff_summaries(baseline, candidate)
        self.assertEqual([], block)
        self.assertEqual([], warn)


if __name__ == "__main__":
    unittest.main()
