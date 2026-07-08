# airtight-loop

Demo project for the Novig "AI Automation Engineer" role (confirmed live via Ashby
posting job id `1bc54185-7095-4499-b291-7076192a865e`). Full plan lives at
`~/.claude/plans/vivid-waddling-wigderson.md` — read that first for the why and the
full spec. This file is the living, in-repo reference for conventions and state.

## What this is

A toy sports-exchange (order book + settlement engine, Java) wrapped in an
automation platform: a failing test triggers an AI agent to patch it, but the PR
only merges after the diff survives a replay backtest against captured **live**
market data. Order flow comes from The Odds API (real moneyline/spread odds);
settlement outcomes come from ESPN's public scoreboard API (real game results).
The point is the infrastructure that lets AI ship into production safely, not the
exchange itself.

## Orchestration model for this build

- **Sonnet 5 implements.** All module code (Java engine, Python pollers, CI
  workflows, skills, dashboard) is written directly by the main session.
- **Opus 4.8 verifies, and only verifies.** After each module/checkpoint, an Opus
  4.8 subagent independently rebuilds and re-runs the relevant checks and reviews
  the diff — it does not trust self-reported "tests pass," and it does not write
  implementation code. Opus's total share of the build effort is scoped to ~10%:
  checkpoint verification only, not a second implementer.
- Checkpoint verdicts get logged in `tasks/todo.md` under the relevant phase.

## Toolchain

- Java 21 (Homebrew `openjdk@21`) + Maven (Homebrew `maven`, itself pulls its own
  `openjdk@26` — this is fine, Maven's `<maven.compiler.source>` in `engine/pom.xml`
  pins language level to 21 regardless of which JDK runs the build).
  `export PATH="/opt/homebrew/opt/openjdk@21/bin:/opt/homebrew/bin:$PATH"` before
  running `mvn` if it's not already on PATH.
- Python 3.9 (system). Pollers use **stdlib only** (`urllib.request`, no
  `requests`) so `python3 feed/odds_poller.py` runs with zero `pip install` steps.

## Build / test commands

```bash
cd engine && mvn -q test          # engine unit tests
cd feed && python3 scores_poller.py     # ESPN, keyless, safe to run anytime
                                          # (set SCORES_POLL_ONCE=1 to run once and exit)
cd feed && ODDS_API_KEY=... python3 odds_poller.py   # requires free key from
                                                       # https://the-odds-api.com/
```

## Conventions / gotchas

- **The Odds API free tier is 500 *credits*/month, not 500 requests.** Cost per
  call = `markets x regions`. `odds_poller.py` requests one region + one market
  (h2h) per call (~1 credit) on purpose — don't widen `ODDS_REGION`/add markets
  without recalculating the monthly budget (~80-100 calls/month at 1 credit each).
- **`captured/*.ndjson` is append-only** and is the replay input for Day 3's
  `ReplayHarness`. Don't hand-edit it; if you need a clean window, start a new
  capture file rather than truncating (preserves provenance of what was actually
  captured live vs. synthesized).
- **Malformed feed rows are quarantined, not dropped silently or crashed on** —
  see `feed/schema.py`'s `FeedValidationError` and the `*.quarantine.ndjson` files.
  This is deliberate: feed health is a first-class telemetry signal, not an
  edge case to swallow.
- **`OrderBook.java` has one intentionally seeded bug** (Day 1): a partially
  filled resting order is unconditionally popped from the book instead of having
  its remaining quantity reduced, so liquidity vanishes after any partial fill.
  `OrderBookTest.partialFillLeavesRemainderRestingInBook` is written to fail
  against this bug on purpose — it's the target for the Day 2 autonomous fix
  loop. Don't "fix" it manually; that's the point of Day 2.
- A second, separate bug will be seeded in Day 3: one that passes all unit tests
  but shifts settlement P&L when replayed — that's the replay-gate's reason to
  exist. Do not conflate it with the Day 1 bug above.

## Status log

- **Day 1 (engine + live pollers) — DONE. Opus 4.8 checkpoint: PASS.** Independent
  rebuild + re-test confirmed the seeded bug is real and isolated, the rest of the
  matching/settlement logic is correct, and both pollers behave as claimed (ESPN
  live-verified, odds parser unit-verified pending an API key). Full verdict in
  `tasks/todo.md`.
- **Day 2 (autonomous fix loop) — DONE. Opus 4.8 checkpoint: PASS WITH NOTES.**
  `agent/fix_loop.py` (Haiku 4.5 classifies -> Opus 4.8 patches -> retest -> PR)
  and `.github/workflows/autonomous-loop.yml` both verified end-to-end against the
  real, public `sudhirerahul/airtight-loop` GitHub repo: a real CI-triggered run
  (`test` fails on the seeded bug -> `auto-fix` succeeds) opened a real PR
  (github-actions[bot], #2) with the correct minimal patch, test file untouched.
  Two real defects the checkpoint found were fixed same day: a lexical (not
  resolved) path-containment guard that could be bypassed via `..` traversal, and
  a deterministic branch-name collision that caused duplicate PRs on repeat runs
  against an unadvanced `main`. Full verdict + fixes in `tasks/todo.md`. The Day 1
  seeded bug remains unmerged on `main` by design — fix loop output lives in PRs,
  not merged, so Day 3's replay-gate work starts from the same red baseline.
  Next: Day 3, the replay gate.
