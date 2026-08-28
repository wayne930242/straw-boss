#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Bring one coworker beside the current dispatched worker."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from dispatch_state import load_json


SCRIPTS = Path(__file__).resolve().parent


def run_public_script(script_name: str, args: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script_name), *args],
        capture_output=True,
        text=True,
        timeout=45,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"{script_name} failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{script_name} returned non-JSON output") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{script_name} returned an invalid result")
    return payload


def dispatch_coworker(
    parent_instruction_path: str,
    slug: str,
    task: str,
    name: str | None,
    agent_kind: str,
    writable_paths: list[str],
    agent_args: list[str],
) -> dict[str, Any]:
    parent_path = Path(parent_instruction_path).resolve()
    if not parent_path.is_file():
        raise ValueError(f"no parent worker instruction at {parent_path}")
    parent = load_json(parent_path)
    app = str(parent.get("app", ""))
    repo_root = str(parent.get("repo_root", ""))
    if not app or not repo_root:
        raise ValueError("parent instruction has no app or repo_root")

    write_args = [
        "write",
        "--app",
        app,
        "--slug",
        slug,
        "--task",
        task,
        "--mode",
        "herdr-pane",
        "--repo-root",
        repo_root,
        "--agent-kind",
        agent_kind,
        "--parent-instruction-path",
        str(parent_path),
    ]
    for writable_path in writable_paths:
        write_args.extend(["--writable-path", writable_path])
    written = run_public_script("dispatch-task.py", write_args)
    instruction_path = str(written["instruction_path"])

    launch_args = ["--instruction-path", instruction_path]
    if name is not None:
        launch_args.extend(["--name", name])
    effective_agent_args = list(agent_args)
    if agent_kind == "codex" and not writable_paths and not effective_agent_args:
        effective_agent_args = ["--sandbox", "read-only"]
    for agent_arg in effective_agent_args:
        launch_args.append(f"--agent-arg={agent_arg}")
    launched = run_public_script("launch-dispatched-agent.py", launch_args)
    run_public_script("dispatch-task.py", ["confirm", "--app", app, "--slug", slug])

    receipt = load_json(Path(str(launched["launch_receipt_path"])))
    return {
        "instruction_path": instruction_path,
        "pane_id": receipt["pane_id"],
        "tab_id": receipt["tab_id"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-instruction-path", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--name",
        default=None,
        help="operator-visible herdr agent name; omit for one the launcher derives automatically",
    )
    parser.add_argument("--agent-kind", required=True, choices=("claude", "codex"))
    parser.add_argument("--writable-path", action="append", default=[])
    parser.add_argument("--agent-arg", action="append", default=[])
    args = parser.parse_args()
    try:
        result = dispatch_coworker(
            args.parent_instruction_path,
            args.slug,
            args.task,
            args.name,
            args.agent_kind,
            args.writable_path,
            args.agent_arg,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
