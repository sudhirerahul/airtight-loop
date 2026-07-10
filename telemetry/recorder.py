"""Flight recorder: aggregates real data from agent/runs/*.json (fix-loop),
replay/runs/*.json (replay gate), and feed/captured/*.{ndjson,health.ndjson}
(feed health) into one JSON blob, then embeds it into dashboard.html so the
dashboard is a single static file -- no server, no fetch(), works from a
plain `file://` open.

Cost is computed from real token_usage recorded by fix_loop.py (added
alongside this file) using Anthropic's published per-model pricing. Runs
predating that change have no token_usage and get cost_usd: null rather than
a guessed number.

Kept stdlib-only, matching feed/ and replay/'s convention.

Usage: python3 telemetry/recorder.py
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIX_RUNS_DIR = REPO_ROOT / "agent" / "runs"
REPLAY_RUNS_DIR = REPO_ROOT / "replay" / "runs"
CAPTURE_DIR = REPO_ROOT / "feed" / "captured"
DASHBOARD_PATH = Path(__file__).parent / "dashboard.html"

# Verified via the Anthropic API pricing table (per 1M tokens), not guessed.
HAIKU_PRICE_PER_M = {"input": 1.00, "output": 5.00}
OPUS_PRICE_PER_M = {"input": 5.00, "output": 25.00}


def _parse_run_timestamp(stem: str) -> str | None:
    """Filenames start with a fixed 16-char '%Y%m%dT%H%M%SZ' prefix."""
    try:
        return datetime.strptime(stem[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def _cost_usd(token_usage: dict | None) -> float | None:
    if not token_usage:
        return None
    haiku = (
        token_usage.get("haiku_input_tokens", 0) / 1_000_000 * HAIKU_PRICE_PER_M["input"]
        + token_usage.get("haiku_output_tokens", 0) / 1_000_000 * HAIKU_PRICE_PER_M["output"]
    )
    opus = (
        token_usage.get("opus_input_tokens", 0) / 1_000_000 * OPUS_PRICE_PER_M["input"]
        + token_usage.get("opus_output_tokens", 0) / 1_000_000 * OPUS_PRICE_PER_M["output"]
    )
    return round(haiku + opus, 4)


def load_fix_runs() -> list[dict]:
    runs = []
    for path in sorted(FIX_RUNS_DIR.glob("*.json")):
        record = json.loads(path.read_text())
        record["timestamp"] = _parse_run_timestamp(path.stem)
        record["cost_usd"] = _cost_usd(record.get("token_usage"))
        runs.append(record)
    return runs


def load_replay_runs() -> list[dict]:
    runs = []
    for path in sorted(REPLAY_RUNS_DIR.glob("*.json")):
        record = json.loads(path.read_text())
        record["timestamp"] = _parse_run_timestamp(path.stem)
        runs.append(record)
    return runs


def load_feed_health() -> dict:
    health = {}
    for feed_name in ("odds", "scores"):
        ingested_file = CAPTURE_DIR / f"{feed_name}.ndjson"
        quarantine_file = CAPTURE_DIR / f"{feed_name}.quarantine.ndjson"
        health_file = CAPTURE_DIR / f"{feed_name}.health.ndjson"

        ingested = sum(1 for line in ingested_file.read_text().splitlines() if line) if ingested_file.exists() else 0
        quarantined = sum(1 for line in quarantine_file.read_text().splitlines() if line) if quarantine_file.exists() else 0
        events = []
        if health_file.exists():
            events = [json.loads(line) for line in health_file.read_text().splitlines() if line]
        gaps = sum(1 for e in events if e.get("event_type") == "gap")
        drift = sum(1 for e in events if e.get("event_type") == "drift")

        health[feed_name] = {
            "ingested": ingested,
            "quarantined": quarantined,
            "gaps": gaps,
            "drift_events": drift,
            "uptime": round(ingested / (ingested + gaps), 4) if (ingested + gaps) > 0 else None,
        }
    return health


def check_human_overrides(fix_runs: list[dict]) -> None:
    """Best-effort: was a fix-loop PR merged despite a failing replay-gate check?
    Mutates each run in place with a `human_override` field: True/False/None (unknown --
    gh unavailable, PR not found, or checks not queryable). Never fabricates a verdict."""
    for run in fix_runs:
        pr_url = run.get("pr_url")
        if not pr_url:
            continue
        run["human_override"] = None
        try:
            view = subprocess.run(
                ["gh", "pr", "view", pr_url, "--json", "state,number"],
                capture_output=True, text=True, timeout=15,
            )
            if view.returncode != 0 or not view.stdout.strip():
                continue
            info = json.loads(view.stdout)
            if info.get("state") != "MERGED":
                run["human_override"] = False
                continue
            checks = subprocess.run(
                ["gh", "pr", "checks", str(info["number"]), "--json", "name,conclusion"],
                capture_output=True, text=True, timeout=15,
            )
            if not checks.stdout.strip():
                continue
            check_list = json.loads(checks.stdout)
            replay_failed = any(
                c.get("name") == "replay-gate" and c.get("conclusion") not in ("SUCCESS", "NEUTRAL", None)
                for c in check_list
            )
            run["human_override"] = replay_failed
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError, KeyError):
            continue


def build_summary(fix_runs: list[dict], replay_runs: list[dict]) -> dict:
    fixed = sum(1 for r in fix_runs if r.get("verdict") == "fixed")
    unresolved = sum(1 for r in fix_runs if r.get("verdict") == "unresolved")
    known_costs = [r["cost_usd"] for r in fix_runs if r.get("cost_usd") is not None]
    wall_clocks = [r["wall_clock_seconds"] for r in fix_runs if r.get("wall_clock_seconds") is not None]

    replay_pass = sum(1 for r in replay_runs if r.get("verdict") == "pass")
    replay_blocked = sum(1 for r in replay_runs if r.get("verdict") == "blocked")

    overrides = [r.get("human_override") for r in fix_runs if r.get("pr_url")]

    return {
        "total_fix_runs": len(fix_runs),
        "fixed": fixed,
        "unresolved": unresolved,
        "success_rate": round(fixed / len(fix_runs), 4) if fix_runs else None,
        "avg_wall_clock_seconds": round(sum(wall_clocks) / len(wall_clocks), 1) if wall_clocks else None,
        "total_cost_usd": round(sum(known_costs), 4) if known_costs else None,
        "avg_cost_per_fix_usd": round(sum(known_costs) / len(known_costs), 4) if known_costs else None,
        "runs_missing_cost_data": sum(1 for r in fix_runs if r.get("cost_usd") is None),
        "total_replay_runs": len(replay_runs),
        "replay_pass": replay_pass,
        "replay_blocked": replay_blocked,
        "replay_pass_rate": round(replay_pass / len(replay_runs), 4) if replay_runs else None,
        "human_overrides_detected": sum(1 for o in overrides if o is True),
        "human_overrides_unknown": sum(1 for o in overrides if o is None),
    }


def build_timeline(fix_runs: list[dict], replay_runs: list[dict]) -> list[dict]:
    timeline = []
    for r in fix_runs:
        timeline.append({
            "type": "fix",
            "timestamp": r.get("timestamp"),
            "verdict": r.get("verdict"),
            "blocked": r.get("verdict") == "unresolved",
            "label": f"{r.get('test_class')}.{r.get('test_method')}",
            "detail": r.get("pr_url") or f"unresolved after {len(r.get('attempts', []))} attempts",
            "cost_usd": r.get("cost_usd"),
            "wall_clock_seconds": r.get("wall_clock_seconds"),
        })
    for r in replay_runs:
        n_diverged = len(r.get("block_reasons", []))
        timeline.append({
            "type": "replay",
            "timestamp": r.get("timestamp"),
            "verdict": r.get("verdict"),
            "blocked": r.get("verdict") == "blocked",
            "label": f"baseline {r.get('baseline_ref')}",
            "detail": f"{n_diverged} order(s) diverged from baseline P&L" if n_diverged else "matched baseline P&L",
            "candidate_wall_clock_millis": r.get("candidate_wall_clock_millis"),
        })
    timeline.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    return timeline


def render_dashboard(data: dict) -> None:
    html = DASHBOARD_PATH.read_text()
    # Embedded values include LLM-authored text (root_cause strings) -- escape "</"
    # so a literal "</script>" inside a JSON string can't prematurely close the tag.
    payload = json.dumps(data, indent=2).replace("</", "<\\/")
    updated, count = re.subn(
        r'(<script id="telemetry-data" type="application/json">)(.*?)(</script>)',
        lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3),
        html,
        flags=re.DOTALL,
    )
    if count != 1:
        raise RuntimeError("dashboard.html is missing the #telemetry-data script tag")
    DASHBOARD_PATH.write_text(updated)


def main() -> None:
    fix_runs = load_fix_runs()
    replay_runs = load_replay_runs()
    check_human_overrides(fix_runs)
    feed_health = load_feed_health()
    summary = build_summary(fix_runs, replay_runs)
    timeline = build_timeline(fix_runs, replay_runs)

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "feed_health": feed_health,
        "fix_runs": fix_runs,
        "replay_runs": replay_runs,
        "timeline": timeline,
    }

    render_dashboard(data)
    print(f"[recorder] {summary['total_fix_runs']} fix runs, {summary['total_replay_runs']} replay runs, "
          f"dashboard updated at {DASHBOARD_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
