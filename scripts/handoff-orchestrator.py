#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Open an approved independent orchestrator tab and transfer one work scope."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from agent_naming import derive_agent_name, live_names, unique_agent_name
from dispatch_session import (
    HerdrCommandError,
    run_herdr,
    validate_current_process_in_pane,
)
from dispatch_state import (
    dump_json,
    load_json,
    straw_boss_root,
)


MAX_CONTINUITY_CHARS = 1600
MAX_PROMPT_CHARS = 3000
ACCEPT_TIMEOUT_SECONDS = 20.0
ACCEPT_POLL_SECONDS = 0.25
AGENT_START_PANE_READY_TIMEOUT_SECONDS = 15.0
AGENT_START_PANE_READY_POLL_SECONDS = 0.25
MAX_NAME_COLLISION_ATTEMPTS = 3
VALID_COORDINATION_GRAPHS = {
    "single-loop",
    "sub-agent fan-out/fan-in",
    "orchestrator-worker",
}


class TabCreationError(ValueError):
    """Preserve any created Herdr ids so the caller can clean partial results."""

    def __init__(
        self, message: str, *, tab_id: str | None = None, pane_id: str | None = None
    ) -> None:
        super().__init__(message)
        self.tab_id = tab_id
        self.pane_id = pane_id


def compact_values(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def continuity_payload(args: argparse.Namespace) -> dict[str, object]:
    required = {
        "goal": args.goal.strip(),
        "scope": args.scope.strip(),
        "state": args.state.strip(),
        "next": args.next_action.strip(),
    }
    if not all(required.values()):
        raise ValueError("goal, scope, state, and next action must be non-empty")
    optional = {
        "decisions": compact_values(args.decision),
        "terms": compact_values(args.term),
        "evidence": compact_values(args.evidence),
        "exclusions": compact_values([*args.exclude, *args.retains]),
    }
    payload: dict[str, object] = {
        **required,
        **{key: value for key, value in optional.items() if value},
    }
    size = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    if size > MAX_CONTINUITY_CHARS:
        raise ValueError(
            f"continuity payload is {size} characters; compact it to {MAX_CONTINUITY_CHARS}"
        )
    return payload


def render_prompt(path: Path, continuity: dict[str, object]) -> str:
    lines = [
        "Invoke `boss-say` with this orchestrator handoff file.",
        f"Orchestrator handoff file: {path}",
        "That skill records acceptance after it establishes the work route.",
    ]
    labels = (
        ("Goal", "goal"),
        ("Scope", "scope"),
        ("Confirmed decisions", "decisions"),
        ("User terms", "terms"),
        ("Current state", "state"),
        ("Evidence", "evidence"),
        ("Next", "next"),
        ("Exclusions", "exclusions"),
    )
    for label, key in labels:
        value = continuity.get(key)
        if isinstance(value, list):
            if value:
                lines.append(f"{label}: {'; '.join(value)}")
        elif value:
            lines.append(f"{label}: {value}")
    prompt = "\n".join(lines)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ValueError(
            f"generated handoff prompt is {len(prompt)} characters; limit is {MAX_PROMPT_CHARS}"
        )
    return prompt


def source_workspace(source_pane_id: str) -> str:
    payload = run_herdr(["pane", "get", source_pane_id])
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict) or pane.get("pane_id") != source_pane_id:
        raise ValueError(f"herdr could not resolve source pane {source_pane_id!r}")
    workspace_id = pane.get("workspace_id")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise ValueError(f"source pane {source_pane_id!r} has no workspace id")
    return workspace_id


def create_tab(workspace_id: str, cwd: Path, label: str) -> tuple[str, str]:
    payload = run_herdr(
        [
            "tab",
            "create",
            "--workspace",
            workspace_id,
            "--cwd",
            str(cwd),
            "--label",
            label,
            "--no-focus",
        ]
    )
    result = payload.get("result", {})
    tab = result.get("tab")
    pane = result.get("root_pane")
    tab_id = tab.get("tab_id") if isinstance(tab, dict) else None
    pane_tab_id = pane.get("tab_id") if isinstance(pane, dict) else None
    pane_id = pane.get("pane_id") if isinstance(pane, dict) else None
    known_tab_id = next(
        (
            value
            for value in (tab_id, pane_tab_id)
            if isinstance(value, str) and value
        ),
        None,
    )
    known_pane_id = pane_id if isinstance(pane_id, str) and pane_id else None
    if not isinstance(tab, dict) or not isinstance(pane, dict):
        raise TabCreationError(
            "herdr tab create did not return tab and root_pane",
            tab_id=known_tab_id,
            pane_id=known_pane_id,
        )
    if not isinstance(tab_id, str) or not isinstance(pane_id, str):
        raise TabCreationError(
            "herdr tab create returned no tab or pane id",
            tab_id=known_tab_id,
            pane_id=known_pane_id,
        )
    if pane_tab_id != tab_id:
        raise TabCreationError(
            "herdr tab create returned a root pane in another tab",
            tab_id=known_tab_id,
            pane_id=known_pane_id,
        )
    return tab_id, pane_id


def start_receiver(
    pane_id: str, base_name: str, agent_kind: str, agent_args: list[str]
) -> str:
    taken = live_names(run_herdr(["agent", "list"]))
    name = unique_agent_name(base_name, taken)
    readiness_deadline = monotonic() + AGENT_START_PANE_READY_TIMEOUT_SECONDS
    for attempt in range(MAX_NAME_COLLISION_ATTEMPTS + 1):
        while True:
            try:
                run_herdr(
                    [
                        "agent",
                        "start",
                        name,
                        "--kind",
                        agent_kind,
                        "--pane",
                        pane_id,
                        "--",
                        *agent_args,
                    ]
                )
                return name
            except HerdrCommandError as exc:
                remaining = readiness_deadline - monotonic()
                if exc.error_code == "agent_pane_busy" and remaining > 0:
                    sleep(min(AGENT_START_PANE_READY_POLL_SECONDS, remaining))
                    continue
                if (
                    exc.error_code != "agent_name_taken"
                    or attempt >= MAX_NAME_COLLISION_ATTEMPTS
                ):
                    raise
                taken.add(name)
                name = unique_agent_name(base_name, taken)
                break
    raise AssertionError("unreachable name retry")


def rename_tab(tab_id: str, name: str) -> str | None:
    last_error: ValueError | None = None
    for _ in range(2):
        try:
            run_herdr(["tab", "rename", tab_id, name])
            return None
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    return f"tab naming failed after two attempts; handoff continued: {last_error}"


def wait_for_acceptance(path: Path, timeout_seconds: float) -> dict[str, Any] | None:
    deadline = monotonic() + timeout_seconds
    while True:
        payload = load_json(path)
        route = payload.get("route")
        if (
            payload.get("status") == "accepted"
            and payload.get("accepted_by_pane") == payload.get("receiver_pane_id")
            and isinstance(payload.get("accepted_at"), str)
            and isinstance(route, dict)
            and route.get("routed_through") == "boss-say"
            and isinstance(route.get("owner"), str)
            and bool(route["owner"].strip())
            and route.get("coordination_graph") in VALID_COORDINATION_GRAPHS
            and isinstance(route.get("reality_anchor"), str)
            and bool(route["reality_anchor"].strip())
            and isinstance(route.get("routed_at"), str)
        ):
            return payload
        remaining = deadline - monotonic()
        if remaining <= 0:
            return None
        sleep(min(ACCEPT_POLL_SECONDS, remaining))


def offer_prompt(pane_id: str, prompt: str) -> None:
    run_herdr(["agent", "prompt", pane_id, prompt])


def close_failed_receiver(tab_id: str, pane_id: str | None) -> str | None:
    errors: list[str] = []
    for _ in range(2):
        try:
            run_herdr(["tab", "close", tab_id])
            return None
        except ValueError as exc:
            errors.append(str(exc))
    if pane_id is not None:
        try:
            run_herdr(["agent", "send-keys", pane_id, "esc"])
        except ValueError as exc:
            errors.append(str(exc))
        try:
            run_herdr(["pane", "close", pane_id])
        except ValueError as exc:
            errors.append(str(exc))
        else:
            for _ in range(2):
                try:
                    run_herdr(["tab", "close", tab_id])
                    return None
                except ValueError as exc:
                    errors.append(str(exc))
    return "; ".join(errors)


def handoff(args: argparse.Namespace) -> dict[str, object]:
    if not args.user_approved:
        raise ValueError("orchestrator handoff requires explicit user approval")
    validate_current_process_in_pane(args.source_pane_id)
    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        raise ValueError(f"handoff cwd is not a directory: {cwd}")
    continuity = continuity_payload(args)
    retained = compact_values(args.retains)
    workspace_id = source_workspace(args.source_pane_id)
    base_name = derive_agent_name("orchestrator", args.slug)
    tab_id: str | None = None
    pane_id: str | None = None
    handoff_path = (
        straw_boss_root()
        / "handoffs"
        / f"{base_name}-{uuid.uuid4().hex[:10]}.json"
    )
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        try:
            tab_id, pane_id = create_tab(workspace_id, cwd, base_name)
        except TabCreationError as exc:
            tab_id = exc.tab_id
            pane_id = exc.pane_id
            raise
        name = start_receiver(pane_id, base_name, args.agent_kind, args.agent_arg)
        tab_label_warning = rename_tab(tab_id, name)
        record: dict[str, object] = {
            **continuity,
            "status": "offered",
            "source_pane_id": args.source_pane_id,
            "receiver_pane_id": pane_id,
            "receiver_tab_id": tab_id,
            "receiver_name": name,
            "offered_at": datetime.now(timezone.utc).isoformat(),
        }
        dump_json(handoff_path, record)
        prompt = render_prompt(handoff_path, continuity)
        accepted: dict[str, Any] | None = None
        timeout = args.accept_timeout_seconds
        prompt_error: ValueError | None = None
        for _ in range(2):
            accepted = wait_for_acceptance(handoff_path, 0)
            if accepted is not None:
                break
            try:
                offer_prompt(pane_id, prompt)
            except ValueError as exc:
                prompt_error = exc
                continue
            accepted = wait_for_acceptance(handoff_path, timeout)
            if accepted is not None:
                break
        if accepted is None:
            detail = f": {prompt_error}" if prompt_error is not None else ""
            raise ValueError(
                f"receiving orchestrator did not accept after two attempts{detail}"
            )
        result: dict[str, object] = {
            "accepted": True,
            "scope": continuity["scope"],
            "receiver_name": name,
            "receiver_tab_id": tab_id,
            "receiver_pane_id": pane_id,
            "retained": retained,
            "close_source_pane": not bool(retained),
            "accepted_at": accepted["accepted_at"],
            "route": accepted["route"],
        }
        if tab_label_warning is not None:
            result["warning"] = tab_label_warning
        handoff_path.unlink(missing_ok=True)
        return result
    except ValueError as exc:
        cleanup_error: str | None = None
        if tab_id is not None:
            cleanup_error = close_failed_receiver(tab_id, pane_id)
        if cleanup_error is not None:
            recovery = load_json(handoff_path) if handoff_path.is_file() else {
                **continuity,
                "source_pane_id": args.source_pane_id,
                "receiver_pane_id": pane_id,
                "receiver_tab_id": tab_id,
            }
            recovery["status"] = "cleanup-failed"
            recovery["cleanup_error"] = cleanup_error
            dump_json(handoff_path, recovery)
            raise ValueError(
                f"{exc}; failed to close the new orchestrator tab; recovery record "
                f"is {handoff_path}: {cleanup_error}"
            ) from exc
        handoff_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-approved", action="store_true")
    parser.add_argument("--source-pane-id", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--agent-kind", choices=["claude", "codex"], required=True)
    parser.add_argument("--agent-arg", action="append", default=[])
    parser.add_argument("--goal", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--decision", action="append", default=[])
    parser.add_argument("--term", action="append", default=[])
    parser.add_argument("--state", required=True)
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--next", dest="next_action", required=True)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--retains", action="append", default=[])
    parser.add_argument(
        "--accept-timeout-seconds",
        type=float,
        default=ACCEPT_TIMEOUT_SECONDS,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.accept_timeout_seconds < 0:
        print("error: acceptance timeout must be non-negative", file=sys.stderr)
        return 1
    try:
        result = handoff(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if result["close_source_pane"]:
        close_error: ValueError | None = None
        for _ in range(2):
            try:
                run_herdr(["pane", "close", args.source_pane_id])
                close_error = None
                break
            except ValueError as exc:
                close_error = exc
        if close_error is not None:
            print(
                f"warning: accepted handoff, but source pane stayed open: {close_error}",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
