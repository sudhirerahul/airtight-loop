"""Replay gate: builds a "baseline" git ref and the current candidate working
tree, runs ReplayHarness against both over the same captured window, and
blocks (nonzero exit) if per-order settlement P&L diverges at all. A wall-clock
latency regression over 20% is a warning only, not a block.

Deliberately network-independent: builds via `mvn -pl replay -am compile`
(reactor compile only -- no `install`, no `package`), so each build's replay
classes come straight from that checkout's own target/classes, never touching
the shared ~/.m2 local repo. That matters here specifically: baseline and
candidate can have *different* com.novig:engine:0.1.0 bytecode (that's the
whole point of the diff), and installing both to the same local-repo GAV would
risk one silently clobbering the other.

Usage:
  python3 replay/diff_gate.py [--baseline-ref REF] [--odds PATH] [--scores PATH]

Defaults to feed/captured/{odds,scores}.ndjson if present (a real live
capture), else the checked-in fixture window in replay/testdata/sample_window/.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ODDS = REPO_ROOT / "replay" / "testdata" / "sample_window" / "odds.ndjson"
FIXTURE_SCORES = REPO_ROOT / "replay" / "testdata" / "sample_window" / "scores.ndjson"
RUNS_DIR = Path(__file__).parent / "runs"
LATENCY_WARN_THRESHOLD = 0.20


class GateError(Exception):
    pass


def default_odds_file() -> Path:
    real = REPO_ROOT / "feed" / "captured" / "odds.ndjson"
    return real if real.exists() else FIXTURE_ODDS


def default_scores_file() -> Path:
    real = REPO_ROOT / "feed" / "captured" / "scores.ndjson"
    return real if real.exists() else FIXTURE_SCORES


def build_replay_classes(repo_dir: Path) -> None:
    proc = subprocess.run(
        ["mvn", "-q", "-pl", "replay", "-am", "compile"],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GateError(f"build failed in {repo_dir}:\n{proc.stdout}\n{proc.stderr}")


def run_replay_harness(repo_dir: Path, odds_file: Path, scores_file: Path) -> dict:
    classpath = f"{repo_dir / 'engine' / 'target' / 'classes'}:{repo_dir / 'replay' / 'target' / 'classes'}"
    proc = subprocess.run(
        ["java", "-cp", classpath, "com.novig.replay.ReplayHarness", str(odds_file), str(scores_file)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GateError(f"ReplayHarness failed in {repo_dir}:\n{proc.stdout}\n{proc.stderr}")
    lines = [line for line in proc.stdout.strip().splitlines() if line]
    if not lines:
        raise GateError(f"ReplayHarness produced no output in {repo_dir}")
    return json.loads(lines[-1])


def build_baseline_worktree(baseline_ref: str) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="airtight-loop-baseline-"))
    tmp_dir.rmdir()  # git worktree add requires the target not to already exist
    proc = subprocess.run(
        ["git", "worktree", "add", "--detach", str(tmp_dir), baseline_ref],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GateError(f"git worktree add failed for {baseline_ref}:\n{proc.stdout}\n{proc.stderr}")
    return tmp_dir


def remove_worktree(tmp_dir: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(tmp_dir)], cwd=REPO_ROOT, capture_output=True)
    shutil.rmtree(tmp_dir, ignore_errors=True)


def diff_summaries(baseline: dict, candidate: dict) -> tuple[list[str], list[str]]:
    """Returns (block_reasons, warn_reasons)."""
    block_reasons: list[str] = []
    warn_reasons: list[str] = []

    empty_market = {"pnl_by_order": {}, "fill_count": 0}
    all_markets = set(baseline.get("markets", {})) | set(candidate.get("markets", {}))
    for market_id in sorted(all_markets):
        base_market = baseline.get("markets", {}).get(market_id, empty_market)
        cand_market = candidate.get("markets", {}).get(market_id, empty_market)

        all_orders = set(base_market["pnl_by_order"]) | set(cand_market["pnl_by_order"])
        for order_id in sorted(all_orders):
            base_pnl = base_market["pnl_by_order"].get(order_id, 0)
            cand_pnl = cand_market["pnl_by_order"].get(order_id, 0)
            if base_pnl != cand_pnl:
                block_reasons.append(
                    f"market {market_id} order {order_id}: baseline P&L {base_pnl} -> candidate P&L {cand_pnl} "
                    f"(delta {cand_pnl - base_pnl})"
                )

    base_latency = baseline.get("wall_clock_millis", 0)
    cand_latency = candidate.get("wall_clock_millis", 0)
    if base_latency > 0:
        regression = (cand_latency - base_latency) / base_latency
        if regression > LATENCY_WARN_THRESHOLD:
            warn_reasons.append(
                f"latency regression {regression:.0%}: baseline {base_latency}ms -> candidate {cand_latency}ms"
            )

    return block_reasons, warn_reasons


def save_run_record(record: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RUNS_DIR / f"{ts}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    print(f"[diff_gate] run record written to {path.relative_to(REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="origin/main")
    parser.add_argument("--odds", type=Path, default=None)
    parser.add_argument("--scores", type=Path, default=None)
    args = parser.parse_args()

    odds_file = (args.odds or default_odds_file()).resolve()
    scores_file = (args.scores or default_scores_file()).resolve()
    print(f"[diff_gate] replaying {odds_file.relative_to(REPO_ROOT)} / {scores_file.relative_to(REPO_ROOT)}")

    print(f"[diff_gate] candidate = current working tree ({REPO_ROOT})")
    build_replay_classes(REPO_ROOT)
    candidate_summary = run_replay_harness(REPO_ROOT, odds_file, scores_file)

    print(f"[diff_gate] baseline = {args.baseline_ref}")
    worktree = build_baseline_worktree(args.baseline_ref)
    try:
        build_replay_classes(worktree)
        baseline_summary = run_replay_harness(worktree, odds_file, scores_file)
    finally:
        remove_worktree(worktree)

    block_reasons, warn_reasons = diff_summaries(baseline_summary, candidate_summary)

    for reason in warn_reasons:
        print(f"[diff_gate] WARN: {reason}", file=sys.stderr)

    verdict = "blocked" if block_reasons else "pass"
    save_run_record({
        "baseline_ref": args.baseline_ref,
        "verdict": verdict,
        "block_reasons": block_reasons,
        "warn_reasons": warn_reasons,
        "candidate_wall_clock_millis": candidate_summary.get("wall_clock_millis"),
        "baseline_wall_clock_millis": baseline_summary.get("wall_clock_millis"),
        "market_count": len(set(baseline_summary.get("markets", {})) | set(candidate_summary.get("markets", {}))),
    })

    if block_reasons:
        print("[diff_gate] BLOCKED: candidate diverges from baseline settlement P&L", file=sys.stderr)
        for reason in block_reasons:
            print(f"[diff_gate]   {reason}", file=sys.stderr)
        return 1

    print("[diff_gate] PASS: candidate matches baseline settlement P&L over the replayed window")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GateError as exc:
        print(f"[diff_gate] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
