---
name: scaffold-new-market
description: Scaffolds a new sport/market for airtight-loop's replay gate — given a sport name, generates a replay/testdata/<slug>_window/ fixture directory (README + schema-valid placeholder odds.ndjson/scores.ndjson) and prints the exact poller env-var commands needed to start a real capture. Use when asked to add a new sport, market, or league to this repo, or to set up a replay/backtest window for one.
---

# scaffold-new-market

Trading/product-facing tooling: turns "let's list a new sport" from a
manual, error-prone setup (matching The Odds API's sport-key convention to
ESPN's sport/league path convention, hand-writing a schema-correct fixture)
into one command. This is the one skill this demo ships (see
`docs/teardown.md` for why just one, and the automation-opportunities map
for the other two personas).

## When to use this

Invoke when the user asks to add/support/scaffold a new sport, market, or
league for this repo, or wants a fresh `replay/testdata/` window to backtest
against.

## What it does

1. Maps a plain-English sport name (e.g. "nfl", "nhl", "premier league") to
   the two identifier conventions this repo's pollers already use:
   - **The Odds API** sport key (`ODDS_SPORT` in `feed/odds_poller.py`) —
     e.g. `basketball_nba`, `americanfootball_nfl`.
   - **ESPN** site-API sport/league path segments (`SCORES_SPORT`/
     `SCORES_LEAGUE` in `feed/scores_poller.py`) — e.g. `basketball`/`nba`,
     `football`/`nfl`.
2. Creates `replay/testdata/<slug>_window/` with:
   - `README.md` (same shape as `replay/testdata/sample_window/README.md`:
     states plainly whether the odds/scores rows are a real capture or a
     hand-authored fixture, and why).
   - `odds.ndjson` — one placeholder row matching `feed/schema.py`'s
     `OddsTick` fields exactly.
   - `scores.ndjson` — one placeholder row matching `feed/schema.py`'s
     `ScoreEvent` fields exactly.
3. Prints the exact commands to start a real live capture for that sport,
   and the `replay/diff_gate.py` invocation to replay it once real data
   replaces the placeholder rows.

## How to run it

```bash
python3 skills/scaffold-new-market/scripts/scaffold_market.py <sport-name>
# e.g.
python3 skills/scaffold-new-market/scripts/scaffold_market.py nhl
```

Run with no argument (or an unrecognized name) to print the list of sports
the script currently knows.

## Important: only major sports are pre-verified

The script's lookup table only covers sports whose Odds-API-key /
ESPN-path pair line up with what's *already confirmed working in this
repo* (NBA — live-verified in Day 1) or are extremely well-established
public conventions (NFL, MLB, NHL). For anything else, **verify both
identifiers yourself** against
[The Odds API's sports list](https://the-odds-api.com/sports-odds-data/sports-apis.html)
and a live ESPN scoreboard URL
(`https://site.api.espn.com/apis/site/v2/sports/<sport>/<league>/scoreboard`)
before trusting the generated fixture's env-var commands — the script
will not silently guess an unlisted sport's keys.

## After scaffolding

1. Get a free key at https://the-odds-api.com/ if you don't have one yet
   (see `tasks/todo.md` / `CLAUDE.md` — `ODDS_API_KEY` is still unset as of
   Day 3).
2. Run both pollers for the new sport (commands printed by the script) to
   capture a real window into `feed/captured/`.
3. Copy the real captured rows over the placeholder ones in
   `replay/testdata/<slug>_window/`, update its README to say "real
   capture" instead of "placeholder fixture," and re-run
   `replay/diff_gate.py` against the new window before relying on it.
