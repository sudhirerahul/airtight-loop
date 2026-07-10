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

## Day 3 — replay gate (in progress)

Design decisions (locked in before implementing):

- **Maven structure**: root `pom.xml` reactor with `<modules>engine, replay</modules>`.
  `replay/pom.xml` depends on `com.novig:engine:0.1.0`. Keeps `cd engine && mvn -q test`
  working unchanged; new `replay` module builds via the reactor so `replay` can depend
  on `engine`'s compiled classes without a separate install step.
- **No new JSON library.** Captured ndjson rows are flat objects (dataclass fields +
  `captured_at`, no nesting) — a small hand-rolled flat-JSON-line reader in
  `replay/src/main/java/com/novig/replay/NdjsonReader.java` is enough, keeping the
  "no heavy deps" ethos consistent with the stdlib-only Python side.
- **`replay/` stays structurally outside `agent/fix_loop.py`'s `MAIN_SRC`**
  (`engine/src/main/java`) — the replay gate is the independent grader and must never
  be in the autonomous loop's writable blast radius.
- **Odds -> orders conversion** (`ReplayHarness`): no real "size" field exists in
  American odds data, so don't invent one arbitrarily. Model each bookmaker's h2h
  quote as a synthetic two-sided quote around its own implied probability (small
  fixed spread, fixed synthetic quantity) for the "OUTCOME_A = home team wins"
  contract. Divergent bookmaker lines are what generates real fills — this mirrors
  actual line-shopping/arbitrage dynamics instead of a fabricated size field.
- **Seeded Day-3 bug**: new `PriceConverter.americanOddsToPriceTicks(int)` in
  `engine/`, used only by `ReplayHarness`. Correct version rounds half-up. The seeded
  demo bug truncates instead. `PriceConverterTest` uses round-number American odds
  (-150, +100, -300, +150 — all exact fractions, no rounding ambiguity) so truncation
  and rounding agree and **the test passes on both the correct and buggy version**.
  Realistic non-round odds (e.g. +118 -> round 46 vs truncate 45) only show up in
  real/realistic captured data, which is exactly what the replay gate replays — so
  the bug is invisible to unit tests but visible to replay. Lives in `engine/` (not
  `replay/`) so "mvn test passes" is literally the existing CI `test` job, and is
  kept out of the untouched Day-1 `OrderBook`/`SettlementEngine` bug entirely.
- **`diff_gate.py`**: builds "baseline" (given git ref, via `git worktree add` into a
  temp dir) and "candidate" (current working tree / PR head) independently, runs
  `ReplayHarness <odds.ndjson> <scores.ndjson>` against both over the *same* captured
  window, diffs the two JSON summaries. Thresholds: any nonzero per-order settlement
  P&L delta -> BLOCK (exit 1); wall-clock latency regression > 20% -> WARN only
  (exit 0). `ReplayHarness` JSON contract:
  `{"markets": {event_id: {"pnl_by_order": {...}, "fill_count": n}}, "wall_clock_millis": n}`.
- **No live odds capture exists yet** (`ODDS_API_KEY` still unset, carried over from
  Day 1). Day 3 uses a hand-authored fixture odds window
  (`replay/testdata/sample_window/odds.ndjson`) referencing the SAME real completed
  game already in `feed/captured/scores.ndjson` (event 401859967, Spurs @ Knicks) —
  real settlement outcome, synthetic pre-game odds (can't retroactively capture
  historical odds on the free tier). Clearly labeled as a fixture, not a live
  capture. **Follow-up once `ODDS_API_KEY` is obtained**: do a real live odds+scores
  capture window and re-run the replay gate against it before the Day 4 demo video.
- **CI**: new `.github/workflows/replay-gate.yml` on `pull_request` (separate from
  `autonomous-loop.yml`'s `push`-triggered jobs, so it doesn't interfere with the
  Day 2 loop). Marking it a *required* status check is a GitHub branch-protection
  setting — a manual step (or an explicit `gh api`/UI action) called out separately,
  not silently automated.

Tasks:

- [x] Root `pom.xml` reactor + `replay/pom.xml`
- [x] `PriceConverter.java` (correct, round-half-up) + `PriceConverterTest.java`
- [x] `replay/NdjsonReader.java` (flat-JSON-line parser)
- [x] `replay/ReplayHarness.java` (odds->orders, replay, settle, JSON output)
- [x] Fixture window: `replay/testdata/sample_window/odds.ndjson`
- [x] Replay module tests (NdjsonReader + ReplayHarness against fixture)
- [x] `replay/diff_gate.py` (git-worktree baseline vs candidate, thresholds)
- [x] `feed/resilience.py` (backoff, gap, drift) + wire into both pollers
- [x] Seed the Day-3 bug on a separate branch (buggy `PriceConverter`), prove
      `mvn test` green there + replay gate blocks it against main
- [x] `.github/workflows/replay-gate.yml`
- [x] Local end-to-end verification (mirroring Day 1/2's real-run standard)
- [x] Push `main` + demo branch, open PR (see "Real-repo verification" below —
      PR #5, real CI confirmed failing)
- [ ] Wire required status check (deferred to user, manual GitHub UI step —
      see "Open items" below)
- [x] **Opus 4.8 checkpoint verification — PASS** (recovered from an
      earlier session's uncommitted work — see the Day 3 verdict below and
      `tasks/lessons.md`'s 2026-07-10 entry)

### Local verification evidence (2026-07-08, before Opus checkpoint)

- `mvn -pl replay -am test -Dtest='!OrderBookTest#partialFillLeavesRemainderRestingInBook'`
  (excludes only the known, permanent Day-1 bug's test method — a CLI test
  filter, not a code change) → engine: `Tests run: 9, Failures: 0` (incl. new
  `PriceConverterTest`); replay: `Tests run: 8, Failures: 0`
  (`NdjsonReaderTest` + `ReplayHarnessTest`, the latter including a real-fixture
  smoke test asserting fills > 0 and zero-sum settlement).
- `python3 -m unittest test_resilience` (feed/) → 8/8 pass. `python3 -m
  unittest test_diff_gate` (replay/) → 5/5 pass.
- Live-ran `scores_poller.py` against real ESPN once more with the resilience
  wiring in place — real row appended, no regressions, no spurious health
  events on a healthy poll.
- `ReplayHarness` CLI dry run against the fixture:
  `{"markets":{"401859967":{"pnl_by_order":{...10 orders...},"fill_count":5}},"wall_clock_millis":138}`
  — 5 real fills from divergent bookmaker lines, zero-sum P&L.
- **`diff_gate.py --baseline-ref main` on clean `main` → PASS** (identical
  code both sides, only a latency WARN — see caveat below).
- **Seeded the bug on `demo/day3-pnl-replay-bug`** (one line: `PriceConverter`
  swaps `Math.round(...)` for a truncating `(long) (...)` cast, framed as an
  innocuous perf micro-optimization commit). Confirmed `mvn -f engine/pom.xml
  test` on that branch: `Tests run: 10, Failures: 1` — **same single
  pre-existing Day-1 failure, nothing new fails**, `PriceConverterTest` still
  green (its fixtures are exact fractions where truncation==rounding).
  **`diff_gate.py --baseline-ref main` on that branch → BLOCKED**, real
  nonzero P&L deltas on 5 of 10 orders in market `401859967` (e.g.
  `betmgm-6-buy`: baseline -580 -> candidate 0, delta 580) — genuine
  tests-green-replay-catches-it divergence, not a fabricated result.
- **Caveat for the demo recording**: `diff_gate`'s latency WARN threshold
  (20%) is noisy at this workload's scale (single-digit-ms JVM runs vary
  20-70% run to run from JIT/OS scheduling noise, not real regressions) — seen
  on both the clean-main smoke test and the bug-branch test. Expected and
  harmless (it's a WARN, never a block), but worth calling out on camera so it
  doesn't read as a second, unexplained finding.

### Real-repo verification (2026-07-08, after user confirmed pushing)

- Pushed `main` (`385fcd4`) to `origin/main`.
- Pushed `demo/day3-pnl-replay-bug` and opened a real PR:
  **https://github.com/sudhirerahul/airtight-loop/pull/5**.
- **Real GitHub Actions `replay-gate` check on PR #5 → `fail`**
  (run `28971467461`, job `85967959296`). Log shows the *exact same* P&L
  deltas as the local run (e.g. `betmgm-6-buy`: baseline -580 -> candidate 0),
  confirming the CI-hosted result matches the local one byte-for-byte, not
  just "should work." This is the real, required-check-eligible failure the
  demo's "money shot" needs.

### Open items before Day 3 is fully closed

1. **Marking `replay-gate` a required status check** is a GitHub
   branch-protection setting (Settings -> Branches -> protect `main` ->
   required status checks) — user chose to do this manually in the UI rather
   than via `gh api`. Not done automatically. PR #5 stays open, unmerged, as
   the demo artifact (mirrors how Day 2's fix-loop PR stays open by design).
2. **Still no live odds capture** (`ODDS_API_KEY` unset, carried over from Day
   1). Get a free key and do a real live odds+scores capture window before
   the Day 4 demo video; swap it in for (or alongside) the fixture window.

## Day 4 — telemetry + skills + demo

Design decisions:

- **Two upstream additive changes, no behavior change.** `agent/fix_loop.py`
  now captures real `resp.usage.input_tokens`/`output_tokens` from both the
  Haiku classify call and each Opus fix-generation call, threaded into a
  `token_usage` summary on the saved run record. `replay/diff_gate.py` now
  writes a `replay/runs/<ts>.json` record (verdict, block/warn reasons,
  both builds' wall-clock, market count) — it never persisted anything
  before Day 4. Neither change touches the fix loop's guardrails or the
  gate's block/pass logic.
- **Real pricing, not estimated.** `telemetry/recorder.py`'s cost-per-fix
  math uses Anthropic's published per-1M-token pricing for Haiku 4.5
  ($1/$5) and Opus 4.8 ($5/$25), verified via the `claude-api` skill at
  build time, not guessed. Runs predating the `token_usage` field (the Day 2
  sample) get `cost_usd: null`, never a fabricated number.
- **Dashboard is a static file with embedded data, not a live app.**
  `recorder.py` regex-replaces the JSON inside dashboard.html's
  `#telemetry-data` script tag on every run — no server, no `fetch()`, works
  opening the file directly. LLM-authored text (root causes) gets its
  `</` sequences escaped before embedding so it can't break out of the
  script tag.
- **`human_override` is a real, best-effort check, not fabricated.** For
  each fix-loop PR, `recorder.py` shells out to `gh pr view`/`gh pr checks`
  to see if it was merged despite a failing `replay-gate` check; if `gh`
  is unavailable or a PR can't be queried it's marked unknown (`null`),
  never guessed. No override has occurred yet in this repo's real history
  (both fix-loop PRs and the Day-3 demo PR remain open by design) — the
  dashboard correctly shows 0, not a fabricated example.

Tasks:

- [x] `agent/fix_loop.py` — real per-attempt token usage, threaded into
      `save_run_record`'s new `token_usage` field
- [x] `replay/diff_gate.py` — `save_run_record()` writing
      `replay/runs/<ts>.json`; `.gitignore` entry added
- [x] Generated one real replay run record by re-running `diff_gate.py`
      against `demo/day3-pnl-replay-bug` vs `main` (reproduces Day 3's
      exact blocked P&L deltas) and force-added it (provenance sample,
      same convention as Day 2's)
- [x] `telemetry/recorder.py` (stdlib-only) + `telemetry/dashboard.html`
      (single-file, `dataviz`-skill-validated palette, no server)
- [x] `skills/scaffold-new-market/` — verified against a real NHL scaffold,
      checked field-for-field against `feed/schema.py`'s dataclasses
- [x] `docs/teardown.md` (boundary statement + automation-opportunities map
      + honest JD-coverage note)
- [x] **Opus 4.8 checkpoint verification — PASS WITH NOTES** (see Checkpoint
      verdicts below; one real gap found and fixed same session)
- [ ] Record demo video — **manual follow-up, not something this session
      can do** (no camera/screen-recorder access). Script is in the full
      plan doc's "Demo script" section.

### Local verification evidence (2026-07-10)

- `python3 -m py_compile agent/fix_loop.py replay/diff_gate.py` — clean.
- Re-ran `diff_gate.py --baseline-ref main` from `demo/day3-pnl-replay-bug`:
  same 5 P&L deltas as Day 3's original evidence, byte-for-byte
  (`betmgm-6-buy` -580->0, `draftkings-1-sell` 610->0, three ±10 deltas) —
  `replay/runs/20260710T200616Z.json` records it as `"verdict": "blocked"`.
- `python3 telemetry/recorder.py` — real output: `1 fix runs, 1 replay runs,
  dashboard updated`. The one fix run (Day 2's committed sample, predates
  `token_usage`) correctly shows `cost_usd: null` and
  `runs_missing_cost_data: 1` rather than a guessed cost; `human_override`
  for it resolved to `false` via a live `gh pr view` call (PR #1 is open,
  unmerged). The one replay run correctly shows `verdict: blocked`, its 5
  real order-level deltas, and both builds' real wall-clock times.
- `dashboard.html` structural check (Python `html.parser`, tag-balance) —
  clean. Dark/light status palette (`#0ca30c`/`#d03b3b`) passed the
  `dataviz` skill's six-checks validator in both modes (CVD ΔE 12.4,
  contrast >=3:1 on both surfaces). Opened in the default browser via
  `open` for visual confirmation — Playwright MCP was disconnected this
  session so a screenshot couldn't be captured directly.
- `skills/scaffold-new-market/scripts/scaffold_market.py nhl` — generated
  `replay/testdata/nhl_window/`; both placeholder rows were constructed as
  real `feed.schema.OddsTick`/`ScoreEvent` dataclass instances (not just
  eyeballed against the field list) — 0 extra/missing fields either way.
  Test fixture removed afterward (verification only, not a deliverable).
- `engine/`: `mvn -q test` still `Tests run: 10, Failures: 1` — the one
  pre-existing Day-1 failure, confirming nothing above touched engine code.

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

### Day 3 — PASS (2026-07-08)

Independent Opus 4.8 review (did not implement or fix anything; rebuilt every
module myself, re-ran all suites, ran both harness + gate by hand, reproduced the
seeded bug end-to-end, and independently queried the live GitHub state):

- **Toolchain — PASS.** `java -version` = OpenJDK 21.0.11 (Homebrew), `mvn` =
  3.9.16 running on JDK 26 (language level pinned to 21 by the poms — as
  documented). PATH prefix from `tasks/lessons.md` worked as noted.
- **Reactor build — PASS.** `cd engine && mvn -q test` standalone → `Tests run: 10,
  Failures: 1` (the 3 new `PriceConverterTest` + 4 `OrderBookTest` + 3
  `SettlementEngineTest`; the single failure is the permanent Day-1 partial-fill
  bug, untouched). `mvn -pl replay -am test -Dtest='!OrderBookTest#partialFill...'`
  → engine 9/0, replay **8/0** (`NdjsonReaderTest` 4 + `ReplayHarnessTest` 4). The
  replay module's own tests genuinely pass — independently re-run, not trusted.
- **Code read line-by-line + hand-trace — PASS.** Hand-traced
  `divergentBookmakerLines...` (-150 vs -400 → home ticks 60/80; B-2-buy@79 crosses
  resting A-1-sell@61, fills 10 @ 61; OUTCOME_A_WINS → buyer B-2-buy +390, seller
  A-1-sell -390) — matches the test's asserted values exactly. Odds→prob math
  (`100/(odds+100)` / `-odds/(-odds+100)`, round-half-up) is correct; BUY/SELL side
  assignment in `SettlementEngine.settle` is correct; home→OUTCOME_A / away→OUTCOME_B
  mapping correct; `toJson` escaping + TreeMap ordering deterministic. Note:
  `SYNTHETIC_QUANTITY=10` on both sides of every quote means every fill is a *full*
  fill (tradeQty always 10), so the Day-1 `OrderBook` partial-fill bug never fires
  during replay — the two seeded bugs are cleanly independent, as claimed.
- **ReplayHarness CLI — PASS.** Ran against `testdata/sample_window/` myself:
  `fill_count:5`, 10 orders, and I summed the `pnl_by_order` values by hand →
  **exactly 0** (zero-sum verified, not asserted on faith). `betmgm-6-buy=-580`
  matches the self-report.
- **diff_gate.py security + correctness — PASS.** No `shell=True` anywhere; all
  `git`/`mvn`/`java` calls are argv lists; `--baseline-ref` reaches `git worktree
  add --detach <path> <ref>` as a discrete trailing argv element (no injection). The
  worktree cleanup is in a `finally` (`:141-145`) and I confirmed empirically that
  after a run `git worktree list` shows only `main` (no leaked temp worktree). The
  "compile-only, no install" design genuinely avoids the shared-`~/.m2` GAV
  collision it frets about: `~/.m2/repository/com/novig/engine/0.1.0/` contains
  **only `*.lastUpdated` markers, no jar/pom** — engine is never installed, so the
  reactor always builds fresh bytecode from each checkout's own `target/classes`.
  Worst case for a hostile `--baseline-ref` is a build/worktree failure (exit 1),
  not code execution.
- **Seeded Day-3 bug — PASS (reproduced end-to-end).** `git diff main..demo` shows
  exactly the claimed one-line change (`Math.round(...)` → `(long) (...)` cast) in a
  commit disguised as "perf: avoid Math.round overhead in price conversion hot
  path". On `demo/day3-pnl-replay-bug`: `mvn -f engine/pom.xml test` → `Tests run:
  10, Failures: 1` (same single Day-1 failure, nothing new); `PriceConverterTest`
  still 3/3 green (its fixtures are exact fractions where trunc==round). Then
  `python3 replay/diff_gate.py --baseline-ref main` from that branch → **BLOCKED,
  exit 1**, with real deltas (`betmgm-6-buy: -580 → 0`, `draftkings-1-sell: 610 →
  0`, three ±10 deltas) — genuine tests-green / replay-catches-it divergence.
  Returned to `main` afterward; tree clean.
- **Real GitHub state — PASS.** `gh pr view 5` → real, **OPEN**, title "perf: avoid
  Math.round overhead...", head `demo/day3-pnl-replay-bug`. `gh pr checks 5` →
  `replay-gate` = **fail** (run `28971467461`, job `85967959296`); CodeRabbit
  passed. `gh run view 28971467461 --log` shows the *identical* five P&L deltas as
  my local run, byte-for-byte (baseline -580 → candidate 0 on betmgm-6-buy, etc.).
  The CI failure is real and required-check-eligible.
- **resilience.py + wiring — PASS.** `fetch_with_backoff` retries 429/`URLError`
  with exponential backoff (`base*2^(n-1)`), fails non-429 HTTP immediately without
  retry, records a `gap` on exhaustion; `detect_drift` records a `drift` event only
  above threshold and is null-safe on `total==0`. Both pollers fully *replaced*
  their old inline fetch try/except with a single `fetch_with_backoff(...)` call (no
  duplicated blocks) and call `detect_drift(feed, quarantined, len(events))` with
  sensible args. `python3 -m unittest test_resilience` → **8/8**; `test_diff_gate`
  → **5/5** (both re-run by me).
- **Fixtures + hygiene — PASS.** `testdata/sample_window/scores.ndjson` is a
  byte-identical 2-row prefix of the real `feed/captured/scores.ndjson` (the live
  file has one extra later poll row, same game 401859967 / winner=away — no
  settlement impact). `odds.ndjson` matches `feed/schema.py`'s `OddsTick` shape
  exactly and includes the non-round values (`+118`, `+105`, `-155`) that expose
  the bug. `git ls-files` shows **no `target/`, no `.env`, no live `captured/*`**;
  `.gitignore` covers all three. No secrets in any Day-3 commit.

- **NOTE (robustness, not a defect):** `NdjsonReader` uses raw `charAt` indexing;
  a truncated row (e.g. a key with no following `:`) throws
  `StringIndexOutOfBoundsException` rather than the intended
  `IllegalArgumentException`, and `ReplayHarness.readRows` (`ReplayHarness.java:170-179`)
  only catches `IOException` — so a malformed *captured* row would crash the harness
  with a stack trace instead of being quarantined the way the feed side quarantines
  bad rows. Input is trusted internal capture data, so low risk, but it diverges
  from the pipeline's "quarantine, don't crash" ethos. (`NdjsonReader.java:36,56`.)
- **NOTE (minor local/CI inconsistency):** `diff_gate.default_scores_file()`
  (`diff_gate.py:46-48`) prefers `feed/captured/scores.ndjson` when present, so a
  *local* run replays against the real captured scores (3 rows) while *CI* (where
  `captured/` is gitignored and absent) replays against the fixture (2 rows). Same
  event and final outcome, so P&L is identical either way here — but "the same
  captured window" is not literally byte-identical between local and CI. Harmless
  given the identical outcome; worth knowing before swapping in a live odds capture.
- **DESIGN CHOICE I'd flag (not a defect):** blocking on *any* nonzero per-order
  P&L delta is deliberately strict — a legitimate refactor that shifts rounding by
  one tick anywhere would block. Correct for this demo's "settlement must be
  byte-identical" thesis; a production gate would want a tolerance/allowlist path.
  Similarly, modeling only each bookmaker's *home*-team quote (away quotes are
  filtered out and unused) is a documented, internally-consistent simplification,
  not a bug. The 20% latency WARN being noisy at single-digit-ms scale is already
  acknowledged in the evidence and is WARN-only.
- **Verdict: PASS — proceed to Day 4.** Every claim in the Day-3 section was
  independently reproduced: reactor + standalone builds, replay 8/8, hand-verified
  zero-sum replay output, a security-clean gate whose worktree cleanup and
  no-install GAV avoidance I confirmed empirically, and a seeded bug that is
  invisible to unit tests yet blocks the gate both locally and on the real PR #5 CI
  run with byte-identical deltas. No security or correctness defects in the Day-3
  code; the three items above are robustness/design notes, none blocking.

### Day 4 — PASS WITH NOTES (2026-07-10)

Independent Opus 4.8 review (did not implement; re-read every new/changed file
line by line, re-ran the toolchain, re-generated the dashboard, reproduced the
scaffold with dataclass construction, and diffed the two upstream files against
`HEAD`):

- **Additive-only upstream changes — PASS.** `git diff HEAD -- agent/fix_loop.py
  replay/diff_gate.py` confirmed both changes are strictly additive. In
  `fix_loop.py`: the classify→guardrail→patch→retest→guardrail→PR flow is
  untouched — `is_within_main_src` still resolves both paths (the Day-2
  hardening is intact), `MAX_ATTEMPTS` loop bound unchanged, revert-on-red and
  the test-file-touched guardrail unchanged. In `diff_gate.py`: the new
  `save_run_record` call is inserted after `diff_summaries` and before the
  unchanged `if block_reasons: return 1` — the block/warn decision logic (any
  nonzero per-order P&L delta blocks; >20% latency warns only) is byte-for-byte
  unchanged.
- **Security review of new code — PASS.** `recorder.py`'s two `gh` calls use
  argv lists, no `shell=True`, 15s timeouts; `pr_url` reaches `gh pr view` as a
  discrete argv element (no shell-injection surface); broad `except` clauses
  leave `human_override=None` on any failure, never a guess. `scaffold_market.py`
  looks up the sport name in a fixed dict — `slug` (and therefore the output
  path) can never be steered outside `replay/testdata/` by user input; an
  unknown name just exits 1. `dashboard.html` has no `eval`/`new Function`; the
  `innerHTML` sinks only inject derived numbers, `pr_url`, and a regex-constrained
  `test_class.test_method` — the LLM-authored `root_cause` text is never rendered
  into `innerHTML`. The `</` → `<\/` escape before embedding JSON into the
  `<script>` tag is real and correctly implemented (verified by reading, not on
  faith): a literal `</script>` inside a JSON string becomes the harmless 3-char
  `<\/script>`, and `\/` is a valid JSON escape `JSON.parse` restores to `/`.
- **Independent reproduction of local evidence — PASS.** `py_compile` clean on
  all four new/changed Python files. `cd engine && mvn -q test` →
  `Tests run: 10, Failures: 1` (the one pre-existing Day-1 failure, nothing new).
  Re-ran `telemetry/recorder.py` — regenerated `dashboard.html` is byte-identical
  to the committed one except `generated_at`, confirming the embedded JSON
  faithfully mirrors on-disk `agent/runs/`, `replay/runs/`, `feed/captured/`. The
  Day-2 fix sample (predates `token_usage`) correctly shows `cost_usd: null`;
  `human_override: false` for it is a real live `gh` result (PR #1 open,
  unmerged), not a guess. Independently verified the cost formula against
  synthetic input (null→`None`; 1M-tokens-each→`$36.00` = 1+5+5+25; a realistic
  case→`$0.0745`) — Haiku $1/$5 and Opus $5/$25 per 1M applied correctly. Ran
  `scaffold_market.py nhl`, loaded the generated JSON, and constructed real
  `OddsTick`/`ScoreEvent` dataclass instances from it — 0 missing/extra fields
  (only `captured_at` beyond the schema, the standard capture-metadata field).
  Test directory deleted afterward; confirmed clean. `replay/runs/
  20260710T200616Z.json` content matches the original Day-3 evidence exactly
  (market `401859967`, same 5 P&L deltas, `verdict: blocked`).
- **`.gitignore` — PASS on pattern; real gap found and fixed same session.**
  `replay/runs/*.json` is correctly ignored, mirroring `agent/runs/*.json` — but
  the checkpoint caught that the claimed force-added provenance sample
  (`replay/runs/20260710T200616Z.json`) was NOT actually tracked
  (`git ls-files replay/runs/` was empty at review time), contradicting this
  file's own "force-added it" claim. Fixed immediately after the checkpoint:
  `git add -f replay/runs/20260710T200616Z.json`, now confirmed tracked.
- **`docs/teardown.md` + `SKILL.md` — PASS.** Boundary statement honest (toy
  engine, captured-not-streamed, no auth/money, "prototype not product").
  Automation-opportunities map ties to real artifacts. JD-coverage note
  correctly flags cross-functional collaboration as thin, doesn't overclaim it.
  SKILL.md's field/env-var/verification claims match the script and
  `feed/schema.py`.
- **Demo video — not a defect.** Correctly disclosed as a manual follow-up (no
  recording capability this session); not flagged as a gap.
- **Verdict: PASS WITH NOTES — Day 4 accepted.** All code is genuinely additive
  with no behavior change to the fix loop's guardrails or the gate's block/pass
  logic; the new telemetry/skill/docs code is secure and correct; every piece of
  local evidence reproduced independently. One real gap found (the provenance
  sample wasn't actually force-added despite the claim) — fixed same session,
  immediately after the checkpoint, before this verdict was recorded.

**Separately, a real Day-3 checkpoint verdict recovered this session:** the
`### Day 3 — PASS` section above was written by an earlier session but never
committed — it existed only in the now-abandoned iCloud-path working copy (see
`tasks/lessons.md`, 2026-07-10 entry). Recovered by diffing that copy's tracked
files against `git HEAD` before it's discarded; no other uncommitted work was
found in it beyond this one block.
