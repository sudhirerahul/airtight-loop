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

## Day 2 — autonomous fix loop

- [x] `agent/fix_loop.py` + prompts
- [x] GitHub Actions wiring (`.github/workflows/autonomous-loop.yml`)
- [x] End-to-end: seeded `OrderBookTest` failure -> Opus 4.8 patch -> green -> PR opens
- [x] **Opus 4.8 checkpoint verification — PASS WITH NOTES**

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

### Day 2 — PASS WITH NOTES (2026-07-08)

Independent Opus 4.8 review (did not implement; re-read all code, re-ran the script,
re-ran CI inspection, empirically tested the guardrail):

- **Code + seeded bug — PASS.** Seeded bug intact and untouched on `main`
  (`OrderBook.java:60`, unconditional `queue.pollFirst()`); `mvn test` red
  (`Tests run: 7, Failures: 1`). Prompts and workflow read and correct.
- **Security/guardrails — PASS except one real defect (CONCERN).**
  No API-key/token *values* are ever printed (only a "not set" status at
  `fix_loop.py:223`). No `shell=True`; all `mvn`/`git`/`gh` calls use argv lists,
  and `root_cause`/`file_path`/`new_content` reach git/gh as discrete argv elements
  (no injection). `MAX_ATTEMPTS` is a bounded `range()` (default 2) — cannot loop
  forever. On a red attempt the source file is reverted to `original_content`
  (`fix_loop.py:258-259`), and again on the test-file-touched guardrail (`:267`);
  no partial patch leaks. **DEFECT:** the `is_relative_to(MAIN_SRC)` path guard
  (`fix_loop.py:235` and `:242`) is *lexical*, not resolved. `..` traversal
  bypasses it — empirically, `engine/src/main/java/../../../../../agent/fix_loop.py`
  returns `is_relative_to == True` yet resolves *outside* `MAIN_SRC`. An
  LLM-controlled `file_path` (fed by attacker-influenceable test source / maven
  output) could therefore write outside `engine/src/main/java` (e.g. overwrite the
  workflow YAML or the agent itself). Not currently exploited (forced tool-use +
  prompt says "use the exact path given"), but the guard does not do what it
  claims. Fix: `fix_path.resolve().is_relative_to(MAIN_SRC.resolve())`.
- **Independent local re-run — PASS (with a robustness note).** Ran
  `/usr/bin/python3 agent/fix_loop.py` myself against clean red `main`. It
  classified `OrderBook.java`, Opus 4.8 produced a **byte-identical** correct patch
  (added `resting.reduceRemaining(tradeQty)`; made the pop conditional on
  `resting.remainingQuantity() == 0`), tests went green (independently confirmed
  `Tests run: 7, Failures: 0, BUILD SUCCESS`), and it committed touching **only**
  `OrderBook.java` — not the test. The script's `git push` then failed on a
  deterministic branch-name collision: branch is `fix/<method>-<HEAD-short-sha>`,
  and since `main` never advances, every run yields the same name and collides with
  the already-open fix PR on it. Restored `main` to clean red afterward.
- **CI runs — PASS.** Runs `28959216066` (workflow_dispatch) and `28959400612`
  (push) both show `test`=failure, `auto-fix`=success. PR #2
  (github-actions[bot], open) carries the correct minimal diff, only
  `OrderBook.java`, no test file. NOTE: an extra bot PR #3 (byte-identical to #2,
  from the run-record push re-triggering the loop) exists and was *not* in the
  self-report — benign, but it shows every push to `main` accumulates another
  near-duplicate fix PR (the fix never merges to main by design).
- **Repo permission escalation — PASS, minor over-grant.**
  `default_workflow_permissions: write` + `can_approve_pull_request_reviews: true`,
  scoped to this single demo repo (not org-wide) — appropriate. `contents: write` +
  `pull-requests: write` are genuinely required (push branch + open PR).
  `can_approve_pull_request_reviews` is not actually used by this workflow — slightly
  broader than necessary, harmless here.
- **Workflow YAML — PASS.** `auto-fix` has `needs: test` + `if: failure()` (runs
  only on test failure). Triggers are `push:[main]` + `workflow_dispatch`, not
  `pull_request`; a bot PR pushes a `fix/*` branch (filtered out) and does not push
  `main`, so it does not re-trigger `auto-fix` — no infinite loop. A merged fix would
  push `main`, re-run `test` green, and skip `auto-fix`. Reasoning confirmed correct.
- **Verdict: PASS WITH NOTES — proceed to Day 3.** Core pipeline is genuinely
  functional (independently reproduced byte-identical fix + green + correct PRs, test
  never touched, real CI proof). Two real, non-blocking follow-ups: (1) harden the
  lexical `is_relative_to` guard with `.resolve()`; (2) make the fix branch name
  unique per run to avoid push collisions / duplicate-PR accumulation.

**Both follow-ups fixed same day, post-checkpoint:**
- `is_within_main_src()` (`agent/fix_loop.py`) now resolves both paths before the
  containment check; re-tested against the exact exploit path the checkpoint agent
  used (`engine/src/main/java/../../../../../agent/fix_loop.py`) — now correctly
  rejected (previously passed the lexical check).
- `open_pr()` branch name now includes a per-run `HH:MM:SS` suffix
  (`fix/<method>-<short-sha>-<time>`), so re-runs against an unadvanced `main` no
  longer collide on push.
- Closed duplicate PR #3 (byte-identical to #2, caused by the collision above).
  PR #2 (github-actions[bot]) remains as the canonical CI-triggered Day 2 artifact.
