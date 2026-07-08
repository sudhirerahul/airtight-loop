"""Shared feed-health layer for both pollers: retry-with-backoff on transient
errors, and typed feed-health events (gaps, schema-drift bursts) distinct from
the per-row quarantining schema.py already does. Feed health is a first-class
telemetry signal here, not an edge case to swallow -- every event this module
records is meant to be picked up by the telemetry layer later.

Kept stdlib-only, matching the rest of feed/.
"""

from __future__ import annotations

import json
import time
import urllib.error
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

CAPTURE_DIR = Path(__file__).parent / "captured"

# On a 429, the request was rejected before The Odds API bills a credit against
# it -- see tasks/lessons.md on not over-reading the free-tier headline number.
# Retrying a handful of times with backoff is safe; it doesn't burn extra quota.
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY_SECONDS = 2.0
DEFAULT_DRIFT_THRESHOLD = 0.3  # share of a poll's rows quarantined before it's "drift", not noise

T = TypeVar("T")


@dataclass(frozen=True)
class FeedHealthEvent:
    feed_name: str
    event_type: str  # "gap" | "drift"
    detail: str
    occurred_at: str


def _health_file(feed_name: str) -> Path:
    return CAPTURE_DIR / f"{feed_name}.health.ndjson"


def record_health_event(feed_name: str, event_type: str, detail: str) -> None:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    event = FeedHealthEvent(
        feed_name=feed_name,
        event_type=event_type,
        detail=detail,
        occurred_at=datetime.now(timezone.utc).isoformat(),
    )
    with _health_file(feed_name).open("a") as out:
        out.write(json.dumps(asdict(event)) + "\n")


def record_gap(feed_name: str, reason: str) -> None:
    """A poll produced nothing usable after retries -- hold last-known-good state
    and mark the gap explicitly rather than silently skipping it."""
    record_health_event(feed_name, "gap", reason)


def detect_drift(feed_name: str, quarantined_count: int, total_count: int,
                  threshold: float = DEFAULT_DRIFT_THRESHOLD) -> bool:
    """A burst of quarantined rows in one poll (vs. one isolated bad row) usually
    means the upstream response shape changed, not that one record is malformed.
    Returns True (and records a "drift" event) when that share exceeds threshold."""
    if total_count == 0 or quarantined_count == 0:
        return False
    share = quarantined_count / total_count
    if share > threshold:
        record_health_event(
            feed_name, "drift",
            f"{quarantined_count}/{total_count} rows quarantined this poll ({share:.0%} > {threshold:.0%} threshold)",
        )
        return True
    return False


def fetch_with_backoff(
    fetch_fn: Callable[[], T],
    feed_name: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> T | None:
    """Retries fetch_fn() with exponential backoff on rate-limiting (429) or
    transient network errors. Other HTTP errors (4xx/5xx that aren't 429) are
    treated as non-transient and fail immediately without retrying. Returns
    None (after recording a gap event) if every attempt is exhausted."""
    last_reason = "unknown error"
    for attempt in range(1, max_attempts + 1):
        try:
            return fetch_fn()
        except urllib.error.HTTPError as exc:
            if exc.code != 429:
                record_gap(feed_name, f"HTTP error {exc.code}: {exc.reason}")
                return None
            last_reason = f"rate limited (429), attempt {attempt}/{max_attempts}"
        except urllib.error.URLError as exc:
            last_reason = f"network error, attempt {attempt}/{max_attempts}: {exc}"

        if attempt < max_attempts:
            delay = base_delay * (2 ** (attempt - 1))
            sleep_fn(delay)

    record_gap(feed_name, f"exhausted {max_attempts} attempts, last error: {last_reason}")
    return None
