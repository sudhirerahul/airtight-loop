"""Autonomous fix loop: a failing JUnit test in engine/ gets routed to Haiku 4.5
(cheap file classification), patched by Opus 4.8, re-tested, and opened as a PR
if green. See ../CLAUDE.md and tasks/todo.md for the project context.

This is the one Python file in the repo that needs a pip dependency
(`anthropic`) -- unlike the stdlib-only pollers in feed/, calling Claude isn't
optional here. `pip install anthropic` before running.

Env vars:
  ANTHROPIC_API_KEY    required
  AGENT_MAX_ATTEMPTS   default 2
  GITHUB_TOKEN         required for `gh pr create` (gh CLI must be authenticated)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"
MAIN_SRC = ENGINE_DIR / "src" / "main" / "java"
TEST_SRC = ENGINE_DIR / "src" / "test" / "java"
PROMPTS_DIR = Path(__file__).parent / "prompts"
RUNS_DIR = Path(__file__).parent / "runs"

HAIKU_MODEL = "claude-haiku-4-5-20251001"
OPUS_MODEL = "claude-opus-4-8"
MAX_ATTEMPTS = int(os.environ.get("AGENT_MAX_ATTEMPTS", "2"))

CLASSIFY_TOOL = {
    "name": "classify_failure",
    "description": "Identify the single source file most likely responsible for the failing test.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_file": {
                "type": "string",
                "description": "Path relative to repo root, e.g. engine/src/main/java/com/novig/engine/OrderBook.java",
            },
        },
        "required": ["source_file"],
    },
}

APPLY_FIX_TOOL = {
    "name": "apply_fix",
    "description": "Apply a fix to the implicated source file.",
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "file_path": {"type": "string"},
            "new_content": {"type": "string"},
        },
        "required": ["root_cause", "file_path", "new_content"],
    },
}


class FixLoopError(Exception):
    pass


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        ["mvn", "-q", "test"],
        cwd=ENGINE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = proc.stdout + proc.stderr
    return proc.returncode == 0, output


def extract_failing_test(output: str) -> tuple[str, str] | None:
    match = re.search(r"\[ERROR\]\s+(\w+)\.(\w+):\d+", output)
    if not match:
        return None
    return match.group(1), match.group(2)


def find_test_file(class_name: str) -> Path | None:
    matches = list(TEST_SRC.rglob(f"{class_name}.java"))
    return matches[0] if matches else None


def list_main_source_files() -> list[str]:
    return sorted(str(p.relative_to(REPO_ROOT)) for p in MAIN_SRC.rglob("*.java"))


def classify_failure(client: anthropic.Anthropic, class_name: str, method_name: str, failure_output: str) -> str:
    candidates = list_main_source_files()
    prompt = (
        f"Failing test: {class_name}.{method_name}\n\n"
        f"Maven failure output:\n{failure_output[-4000:]}\n\n"
        f"Candidate source files:\n" + "\n".join(candidates)
    )
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=256,
        system=(PROMPTS_DIR / "classify_prompt.md").read_text(),
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_failure"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input["source_file"]
    raise FixLoopError("Haiku did not return a tool_use block")


def generate_fix(
    client: anthropic.Anthropic,
    test_file: Path,
    source_file: str,
    failure_output: str,
    previous_attempt: dict | None,
) -> dict:
    source_path = REPO_ROOT / source_file
    prompt_parts = [
        f"Failing test source ({test_file.relative_to(REPO_ROOT)}):\n```java\n{test_file.read_text()}\n```",
        f"Suspected source file ({source_file}):\n```java\n{source_path.read_text()}\n```",
        f"Maven failure output:\n{failure_output[-4000:]}",
    ]
    if previous_attempt:
        prompt_parts.append(
            "A previous attempt's root_cause was: " + previous_attempt["root_cause"]
            + "\nThat patch still failed with:\n" + previous_attempt["failure_output"][-2000:]
        )
    resp = client.messages.create(
        model=OPUS_MODEL,
        max_tokens=8000,
        system=(PROMPTS_DIR / "fix_prompt.md").read_text(),
        tools=[APPLY_FIX_TOOL],
        tool_choice={"type": "tool", "name": "apply_fix"},
        messages=[{"role": "user", "content": "\n\n".join(prompt_parts)}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise FixLoopError("Opus did not return a tool_use block")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=check)


def open_pr(test_class: str, method_name: str, root_cause: str, attempts: int) -> str:
    short_sha = git("rev-parse", "--short", "HEAD").stdout.strip()
    branch = f"fix/{method_name}-{short_sha}"
    git("checkout", "-b", branch)
    git("add", "-A")
    commit_msg = (
        f"Autonomous fix: {test_class}.{method_name}\n\n"
        f"Root cause (Opus 4.8): {root_cause}\n"
        f"Attempts: {attempts}"
    )
    git("commit", "--author", "airtight-loop-bot <noreply@anthropic.com>", "-m", commit_msg)
    git("push", "-u", "origin", branch)
    body = (
        "### Autonomous fix\n\n"
        f"**Failing test:** `{test_class}.{method_name}`\n"
        f"**Root cause (Opus 4.8):** {root_cause}\n"
        f"**Attempts:** {attempts}\n\n"
        "Classified by Haiku 4.5, patched by Opus 4.8, verified green by re-running "
        "`mvn test` before opening this PR. Test file was not modified."
    )
    proc = subprocess.run(
        [
            "gh", "pr", "create",
            "--title", f"Autonomous fix: {test_class}.{method_name}",
            "--body", body,
            "--base", "main",
            "--head", branch,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def save_run_record(record: dict) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    test_name = record.get("test_method", "unknown")
    path = RUNS_DIR / f"{ts}-{test_name}.json"
    path.write_text(json.dumps(record, indent=2, default=str))
    print(f"[fix_loop] run record written to {path.relative_to(REPO_ROOT)}")


def main() -> int:
    start = time.time()
    green, output = run_tests()
    if green:
        print("[fix_loop] tests already green, nothing to do")
        return 0

    failing = extract_failing_test(output)
    if not failing:
        print("[fix_loop] tests failed but no test method could be parsed from output:", file=sys.stderr)
        print(output[-4000:], file=sys.stderr)
        return 1
    class_name, method_name = failing
    test_file = find_test_file(class_name)
    if test_file is None:
        print(f"[fix_loop] could not locate test file for {class_name}", file=sys.stderr)
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[fix_loop] ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    client = anthropic.Anthropic(api_key=api_key)

    attempts_log: list[dict] = []
    previous_attempt: dict | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[fix_loop] attempt {attempt}/{MAX_ATTEMPTS} for {class_name}.{method_name}")

        source_file = classify_failure(client, class_name, method_name, output)
        source_path = REPO_ROOT / source_file
        if not source_path.is_relative_to(MAIN_SRC):
            print(f"[fix_loop] refusing: classified file outside engine/src/main/java: {source_file}", file=sys.stderr)
            attempts_log.append({"attempt": attempt, "error": "classification outside main src", "source_file": source_file})
            continue

        fix = generate_fix(client, test_file, source_file, output, previous_attempt)
        fix_path = REPO_ROOT / fix["file_path"]
        if not fix_path.is_relative_to(MAIN_SRC):
            print(f"[fix_loop] refusing: fix path outside engine/src/main/java: {fix['file_path']}", file=sys.stderr)
            attempts_log.append({"attempt": attempt, "error": "fix path outside main src", "root_cause": fix.get("root_cause")})
            continue

        original_content = fix_path.read_text()
        fix_path.write_text(fix["new_content"])

        green, retest_output = run_tests()
        attempts_log.append({
            "attempt": attempt,
            "source_file": fix["file_path"],
            "root_cause": fix["root_cause"],
            "result": "green" if green else "red",
        })

        if not green:
            fix_path.write_text(original_content)
            previous_attempt = {"root_cause": fix["root_cause"], "failure_output": retest_output}
            output = retest_output
            continue

        touched = git("diff", "--name-only").stdout.splitlines()
        if str(test_file.relative_to(REPO_ROOT)) in touched:
            print("[fix_loop] guardrail violation: test file was modified, reverting", file=sys.stderr)
            fix_path.write_text(original_content)
            attempts_log[-1]["result"] = "rejected (test file touched)"
            continue

        pr_url = open_pr(class_name, method_name, fix["root_cause"], attempt)
        print(f"[fix_loop] PR opened: {pr_url}")
        save_run_record({
            "test_class": class_name,
            "test_method": method_name,
            "verdict": "fixed",
            "attempts": attempts_log,
            "pr_url": pr_url,
            "wall_clock_seconds": round(time.time() - start, 1),
        })
        return 0

    print(f"[fix_loop] gave up after {MAX_ATTEMPTS} attempts", file=sys.stderr)
    save_run_record({
        "test_class": class_name,
        "test_method": method_name,
        "verdict": "unresolved",
        "attempts": attempts_log,
        "wall_clock_seconds": round(time.time() - start, 1),
    })
    return 1


if __name__ == "__main__":
    sys.exit(main())
