"""Polls ESPN's public scoreboard endpoint (no API key required) for live game
state and appends settlement-relevant state transitions to
feed/captured/scores.ndjson.

Confirmed live and keyless during research for this project:
https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard

Env vars:
  SCORES_SPORT                 default "basketball"
  SCORES_LEAGUE                default "nba"
  SCORES_POLL_INTERVAL_SECONDS default 60
  SCORES_POLL_ONCE=1            poll once and exit instead of looping
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from schema import FeedValidationError, parse_score_event

SPORT = os.environ.get("SCORES_SPORT", "basketball")
LEAGUE = os.environ.get("SCORES_LEAGUE", "nba")
API_URL = f"https://site.api.espn.com/apis/site/v2/sports/{SPORT}/{LEAGUE}/scoreboard"

CAPTURE_DIR = Path(__file__).parent / "captured"
CAPTURE_FILE = CAPTURE_DIR / "scores.ndjson"
QUARANTINE_FILE = CAPTURE_DIR / "scores.quarantine.ndjson"

# In-memory dedup so we only emit a row on an actual status transition, not every poll.
_last_status_by_event: dict[str, str] = {}


def fetch_scoreboard() -> dict:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "airtight-loop/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def capture_once() -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        payload = fetch_scoreboard()
    except urllib.error.HTTPError as exc:
        print(f"[scores_poller] HTTP error {exc.code} -- backing off, will retry next interval", file=sys.stderr)
        return 0
    except urllib.error.URLError as exc:
        print(f"[scores_poller] network error, holding last-known-good state: {exc}", file=sys.stderr)
        return 0

    events = payload.get("events")
    if events is None:
        with QUARANTINE_FILE.open("a") as quarantine:
            quarantine.write(json.dumps({
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "reason": "top-level 'events' key missing -- possible schema drift",
                "raw_keys": list(payload.keys()),
            }) + "\n")
        return 0

    written = 0
    with CAPTURE_FILE.open("a") as out, QUARANTINE_FILE.open("a") as quarantine:
        for raw_event in events:
            try:
                event = parse_score_event(raw_event)
            except FeedValidationError as exc:
                quarantine.write(json.dumps({
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "reason": str(exc),
                    "raw": raw_event,
                }) + "\n")
                continue

            if _last_status_by_event.get(event.event_id) == event.status:
                continue
            _last_status_by_event[event.event_id] = event.status

            record = {"captured_at": datetime.now(timezone.utc).isoformat(), **event.__dict__}
            out.write(json.dumps(record) + "\n")
            written += 1

    return written


def main() -> None:
    interval_seconds = int(os.environ.get("SCORES_POLL_INTERVAL_SECONDS", "60"))
    once = os.environ.get("SCORES_POLL_ONCE") == "1"

    while True:
        written = capture_once()
        print(f"[scores_poller] captured {written} score-state transitions at {datetime.now(timezone.utc).isoformat()}")
        if once:
            break
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
