"""Polls The Odds API for live moneyline odds and appends order-book-ready
events to feed/captured/odds.ndjson.

Requires a free API key: sign up at https://the-odds-api.com/ (no card required)
and set ODDS_API_KEY. The free tier is 500 *credits*/month, not 500 requests --
cost per call is markets x regions. This poller requests one region and one
market (h2h) per call to keep each poll at ~1 credit, and is meant to run on an
interval (e.g. every 10-15 minutes during a live window), not continuously.

Env vars:
  ODDS_API_KEY               required, no default
  ODDS_SPORT                  default "basketball_nba"
  ODDS_REGION                 default "us"
  ODDS_POLL_INTERVAL_SECONDS  default 600
  ODDS_POLL_ONCE=1            poll once and exit instead of looping
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

from schema import FeedValidationError, parse_odds_event

API_BASE = "https://api.the-odds-api.com/v4"
SPORT = os.environ.get("ODDS_SPORT", "basketball_nba")
REGION = os.environ.get("ODDS_REGION", "us")
MARKET = "h2h"

CAPTURE_DIR = Path(__file__).parent / "captured"
CAPTURE_FILE = CAPTURE_DIR / "odds.ndjson"
QUARANTINE_FILE = CAPTURE_DIR / "odds.quarantine.ndjson"


def fetch_odds(api_key: str) -> list[dict]:
    url = (
        f"{API_BASE}/sports/{SPORT}/odds/"
        f"?apiKey={api_key}&regions={REGION}&markets={MARKET}&oddsFormat=american"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "airtight-loop/0.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        remaining = resp.headers.get("x-requests-remaining")
        used = resp.headers.get("x-requests-used")
        if remaining is not None:
            print(f"[odds_poller] credits remaining={remaining} used={used}", file=sys.stderr)
        return json.loads(resp.read())


def capture_once(api_key: str) -> int:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        events = fetch_odds(api_key)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            print("[odds_poller] rate limited (429) -- backing off, will retry next interval", file=sys.stderr)
            return 0
        print(f"[odds_poller] HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        return 0
    except urllib.error.URLError as exc:
        print(f"[odds_poller] network error, holding last-known-good state: {exc}", file=sys.stderr)
        return 0

    written = 0
    with CAPTURE_FILE.open("a") as out, QUARANTINE_FILE.open("a") as quarantine:
        for raw_event in events:
            try:
                ticks = parse_odds_event(raw_event)
            except FeedValidationError as exc:
                quarantine.write(json.dumps({
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "reason": str(exc),
                    "raw": raw_event,
                }) + "\n")
                continue
            for tick in ticks:
                record = {"captured_at": datetime.now(timezone.utc).isoformat(), **tick.__dict__}
                out.write(json.dumps(record) + "\n")
                written += 1
    return written


def main() -> None:
    api_key = os.environ.get("ODDS_API_KEY")
    if not api_key:
        print(
            "[odds_poller] ODDS_API_KEY is not set. Get a free key (no card required) at "
            "https://the-odds-api.com/ and set it before running. Exiting without polling.",
            file=sys.stderr,
        )
        sys.exit(1)

    interval_seconds = int(os.environ.get("ODDS_POLL_INTERVAL_SECONDS", "600"))
    once = os.environ.get("ODDS_POLL_ONCE") == "1"

    while True:
        written = capture_once(api_key)
        print(f"[odds_poller] captured {written} odds ticks at {datetime.now(timezone.utc).isoformat()}")
        if once:
            break
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
