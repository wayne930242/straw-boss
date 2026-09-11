"""Shared paths and durable state for dispatched-agent scripts."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import uuid
from pathlib import Path
from typing import Any

from straw_boss import PLUGIN_ROOT, SCRIPTS_DIR


def straw_boss_root() -> Path:
    return Path.home() / ".straw-boss"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def contract_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.contract.md"
    )


def launch_receipt_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.launch.json"
    )


def launch_failure_path(instruction_path: Path) -> Path:
    """Where a failed launch leaves its reason.

    A launch that never succeeds writes no receipt and leaves the instruction
    `pending`, so without this file an abandoned dispatch is indistinguishable
    from one nobody started -- with no pane id to go and look at either.
    """
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.launch-failure.json"
    )


# Files that share an instruction's <app>--<slug> stem, are owned by it, and are
# archived with it. Kept in one place because two readers depend on the exact
# set: wrap-up moves them, and any *.json scan has to skip the ones that would
# otherwise be read as instructions in their own right.
INSTRUCTION_SIBLING_SUFFIXES = (
    ".contract.md",
    ".launch.json",
    ".launch-failure.json",
    ".messages.jsonl",
    ".progress.jsonl",
    ".status.json",
)


def instruction_sibling_paths(instruction_path: Path) -> list[Path]:
    stem = instruction_path.name.removesuffix(".json")
    return [
        instruction_path.with_name(f"{stem}{suffix}")
        for suffix in INSTRUCTION_SIBLING_SUFFIXES
    ]


def standalone_status_path(instruction_path: Path) -> Path:
    return instruction_path.with_name(
        f"{instruction_path.name.removesuffix('.json')}.status.json"
    )


def plan_status_path(plan_slug: str, task_id: str) -> Path:
    return straw_boss_root() / "plans" / plan_slug / "status" / f"{task_id}.json"


def resolve_instruction_status_path(
    instruction_path: Path, instruction: dict[str, Any]
) -> Path:
    plan_id = instruction.get("plan_id")
    task_id = instruction.get("task_id")
    if plan_id is not None and task_id is not None:
        return plan_status_path(str(plan_id).removeprefix("p-"), str(task_id))
    return standalone_status_path(instruction_path)


SUPPORTED_AGENT_KINDS = ("claude", "codex")


def load_herdr_pane_instruction(
    instruction_path: str | Path,
    *,
    label: str,
    requires: str,
    undispatched_hint: str,
) -> tuple[Path, dict[str, Any]]:
    """An instruction file that names a confirmed herdr-pane worker.

    Three preconditions travel together -- the file exists, it is a herdr-pane
    dispatch of a supported agent kind, and a pane id was recorded for it -- so
    a caller that checks two of them fails later and less legibly than one that
    checks none. `requires` and `undispatched_hint` carry what this particular
    caller needs it for, because "there is nothing to recover" and "was dispatch
    confirmed?" send an operator to different places.
    """
    inst_path = Path(instruction_path)
    if not inst_path.is_file():
        raise ValueError(f"no {label} file at {inst_path}")
    instruction = load_json(inst_path)

    mode = instruction.get("mode")
    agent_kind = instruction.get("agent_kind")
    if mode != "herdr-pane" or agent_kind not in SUPPORTED_AGENT_KINDS:
        raise ValueError(
            f"{label} {inst_path} is mode={mode!r} agent_kind={agent_kind!r} -- {requires}"
        )
    if not instruction.get("herdr_pane_id"):
        raise ValueError(
            f"{label} {inst_path} has no herdr_pane_id recorded -- {undispatched_hint}"
        )
    return inst_path, instruction


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def runtime_launcher_path() -> Path:
    return straw_boss_root() / "bin" / "run-straw-boss-script.py"


def _launcher_protocol(text: str) -> int:
    match = re.search(r"^RUNTIME_LAUNCHER_PROTOCOL = (\d+)$", text, re.MULTILINE)
    return int(match.group(1)) if match else -1


def install_runtime_launcher() -> Path:
    source = SCRIPTS_DIR / "run-straw-boss-script.py"
    source_text = source.read_text()
    destination = runtime_launcher_path()
    try:
        installed_text = destination.read_text()
    except OSError:
        installed_text = ""
    if _launcher_protocol(installed_text) >= _launcher_protocol(source_text):
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(source_text)
    temporary.replace(destination)
    return destination


def _uses_managed_plugin_cache(root: Path) -> bool:
    normalized = root.as_posix()
    return "/.claude/plugins/cache/" in normalized or "/.codex/plugins/cache/" in normalized


def render_dispatch_contract(
    instruction_path: Path,
    coworker_context: dict[str, Any] | None = None,
    *,
    mode: str = "herdr-pane",
    agent_kind: str = "claude",
) -> str:
    if mode != "herdr-pane":
        raise ValueError(f"unsupported dispatch mode {mode!r}")
    if agent_kind not in {"claude", "codex", "agy", "antigravity"}:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")
    origin_root = PLUGIN_ROOT
    launcher = runtime_launcher_path()

    def command(script_name: str) -> str:
        parts = [
            "uv",
            "run",
            "--script",
            str(launcher),
            "--origin-root",
            str(origin_root),
        ]
        if _uses_managed_plugin_cache(origin_root):
            parts.append("--prefer-installed")
        parts.extend(["--script", script_name, "--"])
        return shlex.join(parts)

    progress = command("report-progress.py")
    status = command("report-task-status.py")
    message = command("send-dispatch-message.py")
    coworker_rules = ""
    if coworker_context is not None:
        writable_paths = coworker_context.get("coworker_writable_paths", [])
        if writable_paths:
            rendered_paths = ", ".join(f"`{path}`" for path in writable_paths)
            work_scope = (
                "- Your writable scope is limited to these repo-relative paths: "
                f"{rendered_paths}.\n"
            )
        else:
            work_scope = "- This is review-only: inspect and report without modifying files.\n"
        coworker_rules = (
            "- You are one direct coworker of another dispatched worker and share its exact worktree.\n"
            f"{work_scope}"
            "- Return your result to the parent through the status command; the parent owns integration and cleanup. Complete this task directly rather than coordinating another coworker.\n"
        )
    path_argument = f"--instruction-path {shlex.quote(str(instruction_path))}"
    return f"""# Straw Boss dispatched-agent contract

This contract is mandatory for this dispatched session.

- Your canonical instruction path is `{instruction_path}`, and its `task` field is the work you are here to do.
- You are an independent agent: you and the user own the specification, design, implementation, and the verification method inside the reality anchor this dispatch names -- settling the anchor yourselves when it names none -- and the main agent accepts those decisions. Investigate this working directory yourself.
{coworker_rules}- Do not use SendMessage, direct `herdr agent prompt`, pane ids, session ids, or agent names for cross-session communication.
- Messages and status notes are delta-only and at most two sentences; identity, history, and evidence go in repeatable `--ref '<artifact/source>'` arguments.
- Report progress with:
  `{progress} {path_argument} --note '<summary>'`
- Reach the main agent with these two commands -- a question for integrated context, and a checkpoint naming who can unblock you, after whose reply you continue instead of replacing it with a terminal status:
  `{message} {path_argument} --to main --intent question --message '<delta>' [--ref '<source>']`
  `{status} {path_argument} --status <awaiting-user-input|awaiting-main-agent|awaiting-authorization> --note '<what you need>' [--ref '<proof>']`
- Before stopping after completed work, report terminal `done` or `failed` with the same status script, carrying the finished change-set's review disposition; it persists and notifies the main agent through Herdr.
"""


def confirm_dispatch(
    path: Path,
    pane_id: str | None = None,
    tab_id: str | None = None,
    observed_session_id: str | None = None,
) -> dict[str, Any]:
    """Bind a launched dispatch's pane/session identities and mark it in-progress.

    The launcher calls this itself the moment it writes a matching receipt, so a
    worker can report its own status without waiting on a separate coordinator
    step. `dispatch-task.py confirm` calls the same function for a dispatch whose
    launch wrote a receipt but could not finish its own bookkeeping.
    """
    if not path.is_file():
        raise ValueError(f"no instruction file at {path}")
    payload = load_json(path)
    status = payload["status"]
    if status == "in-progress":
        return {"instruction_path": str(path), "already_confirmed": True}
    if status != "pending":
        raise ValueError(
            f"instruction at {path} is {status!r}, not 'pending' -- "
            f"refusing to confirm a dispatch that wasn't just written"
        )
    if payload.get("mode") == "herdr-pane":
        receipt_path = launch_receipt_path(path)
        if not receipt_path.is_file():
            raise ValueError(
                f"no launch receipt at {receipt_path} -- start this dispatch through "
                "launch-dispatched-agent.py before confirming it"
            )
        receipt = load_json(receipt_path)
        receipt_instruction_path = receipt.get("instruction_path")
        if (
            not isinstance(receipt_instruction_path, str)
            or Path(receipt_instruction_path).resolve() != path.resolve()
        ):
            raise ValueError(
                f"launch receipt instruction_path={receipt_instruction_path!r} "
                f"does not match {str(path)!r}"
            )
        expected_receipt = {
            "contract_sha256": payload.get("contract_sha256"),
            "agent_kind": payload.get("agent_kind"),
        }
        for field, expected in expected_receipt.items():
            if receipt.get(field) != expected:
                raise ValueError(
                    f"launch receipt {field}={receipt.get(field)!r} does not match {expected!r}"
                )
        if pane_id is not None and receipt.get("pane_id") != pane_id:
            raise ValueError("launch receipt pane id does not match --pane-id")
        if tab_id is not None and receipt.get("tab_id") != tab_id:
            raise ValueError("launch receipt tab id does not match --tab-id")
        receipt_session_id = receipt.get("session_id")
        receipt_terminal_id = receipt.get("herdr_terminal_id")
        if payload.get("agent_kind") == "codex" and (
            not isinstance(receipt_terminal_id, str) or not receipt_terminal_id
        ):
            raise ValueError("launch receipt has no herdr terminal id")
        if observed_session_id is not None and receipt_session_id != observed_session_id:
            raise ValueError("launch receipt session id does not match --observed-session-id")
        pane_id = str(receipt["pane_id"])
        tab_id = receipt.get("tab_id")
        observed_session_id = (
            receipt_session_id if isinstance(receipt_session_id, str) else None
        )
        if isinstance(receipt_terminal_id, str) and receipt_terminal_id:
            payload["herdr_terminal_id"] = receipt_terminal_id

    payload["status"] = "in-progress"
    if pane_id is not None:
        payload["herdr_pane_id"] = pane_id
    if tab_id is not None:
        payload["herdr_tab_id"] = tab_id
    if observed_session_id is not None:
        # claude was launched with the pre-generated session_id passed as
        # --session-id, so the two must match -- a mismatch means the pane
        # this confirms isn't the one this dispatch launched. Other agent
        # kinds (e.g. codex) don't accept a caller-supplied session id -- the
        # pre-generated one was never passed to the launch command, so it's
        # replaced with what the agent itself reported instead of compared.
        if payload["agent_kind"] == "claude" and payload["session_id"] != observed_session_id:
            raise ValueError(
                f"observed session id {observed_session_id!r} does not match the session id "
                f"{payload['session_id']!r} recorded at write time -- the agent in this pane may "
                f"not be the one this dispatch launched"
            )
        payload["session_id"] = observed_session_id
    elif payload["agent_kind"] == "claude":
        raise ValueError("Claude launch receipt has no session id")
    else:
        payload["session_id"] = None
    dump_json(path, payload)
    return {"instruction_path": str(path)}
