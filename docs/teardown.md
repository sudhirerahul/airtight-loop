# Teardown — airtight-loop

## What this is

A toy sports-exchange (order book + settlement engine, Java) wrapped in an
automation platform: a failing test triggers Opus 4.8 to patch it, but the
patch only merges after it survives a replay backtest against a captured
**live** market window (real odds from The Odds API, real outcomes from
ESPN's public scoreboard). A flight recorder logs every fix-loop and
replay-gate run — cost, latency, verdict, feed health — into a single-file
dashboard. The point isn't the exchange; it's the infrastructure that lets
AI ship into one safely, proven against real data that misbehaves the way
production data does.

Everything named below is real, not simulated: real Java tests, real
Opus-authored commits, real GitHub Actions runs, a real required-status-check
blocking a merge (PR #5), real ESPN capture, and a dashboard rendering real
recorded runs, not placeholder numbers.

## What this is not

**A genuinely working prototype, not a production system.** Specifically:

- The order book/settlement engine is a toy — two-outcome markets only, no
  partial-fill netting beyond what Day 1's tests cover, no margining.
- Market data is **captured, not streamed** — pollers snapshot a window,
  replay is deterministic over that snapshot, not a live feed.
- Single-repo, single-user. No auth, no multi-tenant isolation, no SLA.
- No real production traffic or real money has ever touched this system.

Outreach copy about this project should say "prototype" or "demo," never
"product."

## Automation-opportunities map

One concrete, non-hypothetical workflow this platform automates or de-risks
per internal persona — the honest surface where cross-functional
collaboration would plug in (see the JD-coverage note below for why this is
a map, not a claim of collaboration already done):

| Persona | Workflow this automates/de-risks |
|---|---|
| **Trading / product** | Standing up a new market today means hand-matching The Odds API's sport-key convention to ESPN's sport/league path convention, then hand-writing a schema-correct replay fixture — easy to get subtly wrong and hard to notice until replay silently uses the wrong window. `skills/scaffold-new-market` turns that into one command that generates a verified fixture and prints the exact capture commands. |
| **Engineering** | Every AI-authored patch is regression-tested against real settlement math (`replay/diff_gate.py`), not just unit tests — the Day 3 seeded bug is the proof: it passes `mvn test` cleanly but the gate blocks it on a real P&L divergence. That's the difference between "tests are green" and "this is safe to merge" for anything that touches money math. |
| **Ops / QA** | `feed/resilience.py`'s typed gap/drift events plus the flight recorder's feed-health table turn "is the data feed healthy" from something you'd only notice when a poll silently returns nothing into a first-class, always-visible metric. |

## Honest JD-coverage note

Against the role's actual 6 responsibilities (per the live posting): CI/CD
for autonomous dev loops, end-to-end pipeline reliability/observability,
internal tooling, AI-workflow performance/safety, and demonstrating AI
possibilities are all **solidly covered** by real, verified artifacts in
this repo. **Cross-functional collaboration is the one honestly thin item**
— this is a solo demo with no real teammates, so the automation-opportunities
map above is a signal that the author thinks cross-functionally, not proof
that cross-functional collaboration happened. Don't inflate it in outreach.
