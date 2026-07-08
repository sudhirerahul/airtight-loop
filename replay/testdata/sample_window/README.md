# Fixture capture window

`scores.ndjson` is a copy of the real, live-captured row in
`feed/captured/scores.ndjson` (real ESPN result: event 401859967, San Antonio
Spurs 90 @ New York Knicks 94, final, winner=away).

`odds.ndjson` is **hand-authored, not a live capture** — `ODDS_API_KEY` hasn't
been set up yet (see `tasks/todo.md`), and The Odds API's free tier doesn't
serve historical odds, so this specific game's real in-game odds can't be
captured retroactively. It's schema-valid (matches `feed/schema.py`'s
`OddsTick` shape exactly) and timeline-consistent with the real game (quotes
during 14:00-14:20Z, game finalized ~15:53Z per the real `captured_at`), and
deliberately includes several non-round American odds (e.g. `+105`, `-155`,
`+118`) that expose a truncation-vs-rounding difference in price conversion —
exactly the kind of value real bookmaker lines actually produce.

**Follow-up**: once a free key is obtained, do a real live odds+scores capture
and replace/supplement this fixture before recording the Day 4 demo video.
