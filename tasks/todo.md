# todo.md — airtight-loop build state

Full spec: `~/.claude/plans/vivid-waddling-wigderson.md`. Conventions: `../CLAUDE.md`.

## Day 1 — engine + live pollers

- [x] Repo scaffold + git init
- [x] `engine/pom.xml` (Maven, Java 21, JUnit 5)
- [x] `Order.java`, `Fill.java`, `OrderBook.java`, `SettlementEngine.java`
- [x] Unit tests: `OrderBookTest` (4 tests), `SettlementEngineTest` (3 tests)
  - Confirmed via `mvn test`: 7 run, 1 failure (seeded bug), as designed
- [x] `feed/schema.py` — `OddsTick`/`ScoreEvent` shapes + `FeedValidationError`
- [x] `feed/odds_poller.py` — verified: parser unit-checked against The Odds API's
      documented v4 shape (valid + malformed cases); missing-key path exits 1
      with a clear message. **Not yet live-captured — needs a free API key.**
- [x] `feed/scores_poller.py` — **live-verified** against the real ESPN endpoint:
      captured a real completed game (Knicks @ Spurs, 94-90, winner=away) into
      `feed/captured/scores.ndjson`, zero quarantine hits.
- [x] `CLAUDE.md` written
- [x] `.gitignore` added (captured/*.ndjson, .env, target/, __pycache__)
- [x] **Opus 4.8 checkpoint verification — PASS (both engine and feed)**
- [ ] User action needed: sign up for a free key at https://the-odds-api.com/
      and set `ODDS_API_KEY` so `odds_poller.py` can do a real capture

## Day 2 — autonomous fix loop (not started)

- [ ] `agent/fix_loop.py` + prompts
- [ ] GitHub Actions wiring (`.github/workflows/autonomous-loop.yml`)
- [ ] End-to-end: seeded `OrderBookTest` failure -> Opus 4.8 patch -> green -> PR opens

## Day 3 — replay gate (not started)

- [ ] `replay/ReplayHarness.java`, `replay/diff_gate.py`
- [ ] `feed/resilience.py` hardening (backoff, quarantine, gap-fill, drift detection
      — schema.py's quarantine path already exists; this phase adds retry/backoff)
- [ ] Seed the "passes tests, fails replay" P&L bug (separate from the Day 1 bug)
- [ ] Wire as required GitHub status check

## Day 4 — telemetry + skills + demo (not started)

- [ ] `telemetry/recorder.py` + `dashboard.html`
- [ ] One skill (`skills/scaffold-new-market`)
- [ ] `docs/teardown.md` (incl. automation-opportunities map)
- [ ] Record demo video

## Checkpoint verdicts

_(appended after each Opus 4.8 review)_

### Day 1 — PASS (2026-07-08)

Independent Opus 4.8 review (did not implement, rebuilt/re-ran everything itself):

- **engine — PASS.** Read `OrderBook.java` line by line: TreeMap ordering, `crosses()`
  direction, and FIFO time-priority all confirmed correct. Confirmed the seeded bug
  is real, exactly where claimed (`OrderBook.java:60`, unconditional `pollFirst()`
  with `resting.reduceRemaining()` never called), and the *only* correctness defect.
  Re-ran `mvn test` independently: `Tests run: 7, Failures: 1` — matches exactly.
  Hand-traced `SettlementEngine` P&L math against price=40/qty=10 for both outcomes
  — correct.
- **feed — PASS.** Re-ran `scores_poller.py` live independently, confirmed a real
  ESPN record was appended. Confirmed `odds_poller.py` exits 1 cleanly without a key.
  Independently executed (not just read) `parse_odds_event` against a realistic v4
  payload and a malformed one. Checked for API-key logging/SSRF/file-handle leaks —
  none found.
- **Non-blocking notes:** no `.gitignore` existed (fixed same day), and
  `scores_poller`'s in-memory dedup resets per one-shot run (expected behavior, not
  a defect).
- **Verdict: proceed to Day 2.**
