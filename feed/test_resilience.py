"""Run with: python3 -m unittest test_resilience -v"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path

import resilience


class ResilienceTest(unittest.TestCase):
    def setUp(self):
        self._orig_capture_dir = resilience.CAPTURE_DIR
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="resilience-test-"))
        resilience.CAPTURE_DIR = self._tmp_dir
        self._sleeps: list[float] = []

    def tearDown(self):
        resilience.CAPTURE_DIR = self._orig_capture_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _fake_sleep(self, seconds: float) -> None:
        self._sleeps.append(seconds)

    def _health_events(self, feed_name: str) -> list[dict]:
        health_file = self._tmp_dir / f"{feed_name}.health.ndjson"
        if not health_file.exists():
            return []
        return [json.loads(line) for line in health_file.read_text().splitlines() if line]

    def test_succeeds_on_first_try_without_retry(self):
        result = resilience.fetch_with_backoff(lambda: "ok", "odds", sleep_fn=self._fake_sleep)
        self.assertEqual("ok", result)
        self.assertEqual([], self._sleeps)
        self.assertEqual([], self._health_events("odds"))

    def test_retries_on_429_then_succeeds(self):
        attempts = {"n": 0}

        def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
            return "ok"

        result = resilience.fetch_with_backoff(flaky, "odds", max_attempts=3, base_delay=1.0, sleep_fn=self._fake_sleep)
        self.assertEqual("ok", result)
        self.assertEqual(3, attempts["n"])
        self.assertEqual([1.0, 2.0], self._sleeps)  # exponential: base, base*2
        self.assertEqual([], self._health_events("odds"))

    def test_exhausts_retries_and_records_gap(self):
        def always_rate_limited():
            raise urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)

        result = resilience.fetch_with_backoff(always_rate_limited, "odds", max_attempts=2, base_delay=1.0, sleep_fn=self._fake_sleep)
        self.assertIsNone(result)
        events = self._health_events("odds")
        self.assertEqual(1, len(events))
        self.assertEqual("gap", events[0]["event_type"])

    def test_non_429_http_error_fails_immediately_without_retry(self):
        calls = {"n": 0}

        def unauthorized():
            calls["n"] += 1
            raise urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)

        result = resilience.fetch_with_backoff(unauthorized, "odds", max_attempts=3, sleep_fn=self._fake_sleep)
        self.assertIsNone(result)
        self.assertEqual(1, calls["n"])
        self.assertEqual([], self._sleeps)
        events = self._health_events("odds")
        self.assertEqual(1, len(events))
        self.assertIn("401", events[0]["detail"])

    def test_retries_on_network_error(self):
        attempts = {"n": 0}

        def flaky_network():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise urllib.error.URLError("connection refused")
            return "ok"

        result = resilience.fetch_with_backoff(flaky_network, "scores", max_attempts=3, base_delay=0.5, sleep_fn=self._fake_sleep)
        self.assertEqual("ok", result)

    def test_detect_drift_below_threshold_is_silent(self):
        drifted = resilience.detect_drift("odds", quarantined_count=1, total_count=20, threshold=0.3)
        self.assertFalse(drifted)
        self.assertEqual([], self._health_events("odds"))

    def test_detect_drift_above_threshold_records_event(self):
        drifted = resilience.detect_drift("odds", quarantined_count=8, total_count=20, threshold=0.3)
        self.assertTrue(drifted)
        events = self._health_events("odds")
        self.assertEqual(1, len(events))
        self.assertEqual("drift", events[0]["event_type"])

    def test_detect_drift_zero_total_is_silent(self):
        drifted = resilience.detect_drift("odds", quarantined_count=0, total_count=0)
        self.assertFalse(drifted)


if __name__ == "__main__":
    unittest.main()
