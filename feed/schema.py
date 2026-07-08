"""Expected shapes for live feed events, plus lightweight validation.

Not a full JSON-schema validator -- just the fields this pipeline actually reads,
so a poller can tell "the API response changed shape" apart from "the response is
empty" and quarantine the row instead of crashing the poll loop.
"""

from __future__ import annotations

from dataclasses import dataclass


class FeedValidationError(Exception):
    """Raised when a raw API record is missing a field this pipeline depends on."""


@dataclass(frozen=True)
class OddsTick:
    market_id: str
    event_id: str
    commence_time: str
    home_team: str
    away_team: str
    bookmaker: str
    outcome_name: str
    price_american: int
    last_update: str


@dataclass(frozen=True)
class ScoreEvent:
    event_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    status: str  # "scheduled" | "in_progress" | "final"
    winner: str | None  # "home" | "away" | None


def parse_odds_event(raw: dict) -> list[OddsTick]:
    """Flatten one event from The Odds API's /odds response into OddsTick rows.

    Raises FeedValidationError on missing required fields; caller should quarantine
    the raw row rather than let the whole poll crash.
    """
    required = ("id", "commence_time", "home_team", "away_team", "bookmakers")
    missing = [f for f in required if f not in raw]
    if missing:
        raise FeedValidationError(f"odds event missing fields {missing}: keys were {list(raw.keys())}")

    ticks: list[OddsTick] = []
    event_id = raw["id"]
    for bookmaker in raw.get("bookmakers", []):
        book_key = bookmaker.get("key", "unknown")
        last_update = bookmaker.get("last_update", "")
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                if "name" not in outcome or "price" not in outcome:
                    raise FeedValidationError(f"odds outcome missing name/price: {outcome}")
                ticks.append(OddsTick(
                    market_id=event_id,
                    event_id=event_id,
                    commence_time=raw["commence_time"],
                    home_team=raw["home_team"],
                    away_team=raw["away_team"],
                    bookmaker=book_key,
                    outcome_name=outcome["name"],
                    price_american=int(outcome["price"]),
                    last_update=last_update,
                ))
    return ticks


def parse_score_event(raw: dict) -> ScoreEvent:
    """Flatten one ESPN scoreboard 'event' entry into a ScoreEvent."""
    try:
        event_id = raw["id"]
        competition = raw["competitions"][0]
        competitors = competition["competitors"]
        status_state = raw["status"]["type"]["state"]  # "pre" | "in" | "post"
    except (KeyError, IndexError) as exc:
        raise FeedValidationError(
            f"score event missing expected shape: {exc}; keys were {list(raw.keys())}"
        ) from exc

    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if home is None or away is None:
        raise FeedValidationError(f"score event {event_id} missing home/away competitor")

    def team_name(competitor: dict) -> str:
        return competitor.get("team", {}).get("displayName", "unknown")

    def score(competitor: dict) -> int:
        raw_score = competitor.get("score", 0)
        try:
            return int(raw_score)
        except (TypeError, ValueError) as exc:
            raise FeedValidationError(
                f"score event {event_id} has non-numeric score: {raw_score!r}"
            ) from exc

    status_map = {"pre": "scheduled", "in": "in_progress", "post": "final"}
    mapped_status = status_map.get(status_state, status_state)

    home_score, away_score = score(home), score(away)
    winner = None
    if mapped_status == "final":
        if home_score > away_score:
            winner = "home"
        elif away_score > home_score:
            winner = "away"

    return ScoreEvent(
        event_id=event_id,
        home_team=team_name(home),
        away_team=team_name(away),
        home_score=home_score,
        away_score=away_score,
        status=mapped_status,
        winner=winner,
    )
