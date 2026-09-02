#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Start or resume one headless dispatch with durable provider identity."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable

from dispatch_state import dump_json, load_json, resolve_instruction_status_path


CHECKPOINTS = {
    "awaiting-authorization",
    "awaiting-user-input",
    "awaiting-main-agent",
}


@contextmanager
def headless_claim(path: Path, action: str):
    """Hold one crash-safe, process-wide claim for this instruction."""

    claim_path = path.with_name(
        f"{path.name.removesuffix('.json')}.headless.lock"
    )
    descriptor = os.open(claim_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                f"another headless operation already owns {path}"
            ) from exc
        metadata = json.dumps(
            {
                "pid": os.getpid(),
                "action": action,
                "claimed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).encode()
        os.ftruncate(descriptor, 0)
        os.write(descriptor, metadata)
        os.fsync(descriptor)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def configured_args(instruction: dict[str, Any], agent_args: list[str]) -> list[str]:
    kind = instruction["agent_kind"]
    resolved = list(agent_args)
    profile = instruction.get("agent_profile")
    model = instruction.get("agent_model")
    effort = instruction.get("agent_effort")
    advisor = instruction.get("advisor_model")
    if kind == "claude":
        for flag, value in (
            ("--agent", profile),
            ("--model", model),
            ("--effort", effort),
            ("--advisor", advisor),
        ):
            if value is not None:
                resolved.extend([flag, str(value)])
    else:
        if advisor is not None:
            raise ValueError("headless Codex does not support an advisor")
        if profile is not None:
            resolved.extend(["--profile", str(profile)])
        if model is not None:
            resolved.extend(["--model", str(model)])
        if effort is not None:
            resolved.extend(["-c", f"model_reasoning_effort={effort}"])
    return resolved


def codex_resume_args(
    instruction: dict[str, Any], agent_args: list[str]
) -> list[str]:
    resolved: list[str] = []
    if "--dangerously-bypass-approvals-and-sandbox" in agent_args:
        resolved.append("--dangerously-bypass-approvals-and-sandbox")
    model = instruction.get("agent_model")
    effort = instruction.get("agent_effort")
    if model is not None:
        resolved.extend(["--model", str(model)])
    if effort is not None:
        resolved.extend(["-c", f"model_reasoning_effort={effort}"])
    return resolved


def run_streaming(
    command: list[str],
    cwd: Path,
    *,
    capture_thread: bool,
    on_started: Callable[[], None] | None = None,
    on_thread: Callable[[str], None] | None = None,
) -> tuple[int, str | None]:
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        raise ValueError(f"could not start {command[0]!r}: {exc}") from exc
    thread_id: str | None = None
    assert process.stdout is not None
    try:
        if on_started is not None:
            on_started()
        for line in process.stdout:
            print(line, end="", file=sys.stderr, flush=True)
            if capture_thread and thread_id is None:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "thread.started":
                    value = event.get("thread_id") or event.get("threadId")
                    if isinstance(value, str) and value:
                        thread_id = value
                        if on_thread is not None:
                            on_thread(value)
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    return process.wait(), thread_id


def validated_instruction(path: Path) -> tuple[dict[str, Any], Path, Path]:
    if not path.is_file():
        raise ValueError(f"no dispatch instruction at {path}")
    instruction = load_json(path)
    if instruction.get("mode") != "claude-p":
        raise ValueError("headless runner requires a claude-p instruction")
    contract_path = Path(str(instruction.get("contract_path", ""))).resolve()
    if not contract_path.is_file():
        raise ValueError(f"dispatch contract is missing at {contract_path}")
    repo_root = Path(str(instruction.get("repo_root", ""))).resolve()
    if not repo_root.is_dir():
        raise ValueError(f"dispatch repo_root is not a directory: {repo_root}")
    return instruction, contract_path, repo_root


def _start_claimed(path: Path, agent_args: list[str]) -> dict[str, object]:
    instruction, contract_path, repo_root = validated_instruction(path)
    if instruction.get("status") != "pending":
        raise ValueError("only a pending headless dispatch can be started")
    kind = instruction.get("agent_kind")
    provider_args = configured_args(instruction, agent_args)
    if kind == "claude":
        command = [
            "claude",
            "-p",
            "--session-id",
            str(instruction["session_id"]),
            "--append-system-prompt-file",
            str(contract_path),
            *provider_args,
            str(instruction["task"]),
        ]
        capture_thread = False
    elif kind == "codex":
        command = [
            "codex",
            "exec",
            "--json",
            *provider_args,
            "-c",
            f"developer_instructions={contract_path.read_text()}",
            str(instruction["task"]),
        ]
        capture_thread = True
    else:
        raise ValueError(f"unsupported headless agent kind {kind!r}")

    def record_started() -> None:
        instruction["status"] = "in-progress"
        instruction["headless_started_at"] = datetime.now(timezone.utc).isoformat()
        if kind == "codex":
            instruction["headless_resume_args"] = codex_resume_args(
                instruction, agent_args
            )
        dump_json(path, instruction)

    def record_thread(value: str) -> None:
        instruction["provider_thread_id"] = value
        dump_json(path, instruction)

    returncode, thread_id = run_streaming(
        command,
        repo_root,
        capture_thread=capture_thread,
        on_started=record_started,
        on_thread=record_thread,
    )
    if returncode != 0:
        raise ValueError(f"headless {kind} exited with status {returncode}")
    if kind == "codex" and thread_id is None:
        raise ValueError("headless Codex emitted no thread.started identity")
    status_path = resolve_instruction_status_path(path, instruction)
    if not status_path.is_file():
        raise ValueError("headless process exited without reporting a status")
    return {
        "instruction_path": str(path),
        "provider_thread_id": thread_id,
        "status_path": str(status_path),
    }


def start(path: Path, agent_args: list[str]) -> dict[str, object]:
    with headless_claim(path, "start"):
        return _start_claimed(path, agent_args)


def _resume_claimed(path: Path, answer: str) -> dict[str, object]:
    instruction, contract_path, repo_root = validated_instruction(path)
    if instruction.get("agent_kind") != "codex":
        raise ValueError("only a headless Codex dispatch can resume")
    deadline = monotonic() + 5.0
    thread_id = instruction.get("provider_thread_id")
    while (
        not isinstance(thread_id, str) or not thread_id
    ) and monotonic() < deadline:
        sleep(0.05)
        instruction = load_json(path)
        thread_id = instruction.get("provider_thread_id")
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("headless Codex instruction has no provider thread id")
    status_path = resolve_instruction_status_path(path, instruction)
    if not status_path.is_file():
        raise ValueError("headless Codex has no persisted checkpoint")
    before = status_path.read_text()
    checkpoint = load_json(status_path).get("status")
    if checkpoint not in CHECKPOINTS:
        raise ValueError(f"headless Codex status {checkpoint!r} is not resumable")
    resume_args = instruction.get("headless_resume_args", [])
    if not isinstance(resume_args, list) or not all(
        isinstance(value, str) for value in resume_args
    ):
        raise ValueError("headless Codex instruction has invalid resume arguments")
    command = [
        "codex",
        "exec",
        "resume",
        "--json",
        *resume_args,
        "-c",
        f"developer_instructions={contract_path.read_text()}",
        thread_id,
        answer,
    ]
    returncode, _ = run_streaming(command, repo_root, capture_thread=False)
    if returncode != 0:
        raise ValueError(f"headless Codex resume exited with status {returncode}")
    if not status_path.is_file() or status_path.read_text() == before:
        raise ValueError("resumed Codex thread exited without a new status revision")
    return {
        "instruction_path": str(path),
        "provider_thread_id": thread_id,
        "status_path": str(status_path),
    }


def resume(path: Path, answer: str) -> dict[str, object]:
    with headless_claim(path, "resume"):
        return _resume_claimed(path, answer)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--instruction-path", required=True, type=Path)
    start_parser.add_argument("--agent-arg", action="append", default=[])
    resume_parser = sub.add_parser("resume")
    resume_parser.add_argument("--instruction-path", required=True, type=Path)
    resume_parser.add_argument("--answer", required=True)
    args = parser.parse_args()
    try:
        if args.action == "start":
            result = start(args.instruction_path.resolve(), args.agent_arg)
        else:
            result = resume(args.instruction_path.resolve(), args.answer)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
