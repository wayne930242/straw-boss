"""Starting a dispatched worker in its own herdr pane and proving it took the task.

`launch` is the whole sequence; the phases below are the order it runs them in.
One attempt is a `_LaunchAttempt` rather than a closure because a name collision
mid-start rewrites the agent name the rest of that attempt uses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Any

from straw_boss.dispatch.launch.agent import (
    decoy_orchestrator_warning,
    ensure_coordinator_named,
    live_agent,
    live_agent_identity,
    settled_agent,
    start_agent_when_pane_ready,
    startup_gate,
    wait_for_agent_session,
)
from straw_boss.dispatch.launch.pane import (
    create_worker_pane,
    name_task_tab,
    name_worker_pane,
    pane_excerpt,
)
from straw_boss.dispatch.launch.prompt import (
    PromptDeliveryError,
    prompt_task_with_confirmation,
)
from straw_boss.dispatch.launch.provider import provider_profile_args
from straw_boss.dispatch.launch.retry import (
    LaunchAttemptError,
    is_retryable,
    launch_failure_message,
    launch_retry_backoff_seconds,
    record_launch_failure,
    rotate_session_id,
    spent_session_ids,
)
from straw_boss.dispatch.state import (
    confirm_dispatch,
    dump_json,
    launch_failure_path,
    launch_receipt_path,
    load_json,
    sha256_text,
)
from straw_boss.herdr.session import (
    agent_matches_identity,
    resolve_endpoint,
    session_value,
)
from straw_boss.herdr.transport import HerdrCommandError, run_herdr
from straw_boss.naming import derive_agent_name, live_names, unique_agent_name

MAX_NAME_COLLISION_ATTEMPTS = 5


def load_pending_instruction(instruction_path: str) -> tuple[Path, dict[str, Any], Path]:
    """The instruction this launch may act on, with its contract verified."""
    inst_path = Path(instruction_path).resolve()
    if not inst_path.is_file():
        raise ValueError(f"no instruction file at {inst_path}")
    instruction = load_json(inst_path)
    if instruction.get("status") != "pending":
        raise ValueError("only a pending dispatch can be launched")
    if instruction.get("mode") != "herdr-pane":
        raise ValueError("launch-dispatched-agent.py currently supports herdr-pane dispatches")

    contract_path = Path(str(instruction.get("contract_path", "")))
    if not contract_path.is_file():
        raise ValueError(f"dispatch contract is missing at {contract_path}")
    if sha256_text(contract_path.read_text()) != instruction.get("contract_sha256"):
        raise ValueError("dispatch contract digest does not match the instruction")
    return inst_path, instruction, contract_path


def pin_codex_main_agent(inst_path: Path, instruction: dict[str, Any]) -> None:
    """Pin a modern Codex conversation while the originally recorded terminal
    still proves ownership. A resumed legacy endpoint uses rebind-dispatch.py.
    """
    if instruction.get("main_agent_kind") != "codex":
        return
    endpoint = resolve_endpoint(instruction, "main")
    main_agent = live_agent(endpoint.pane_id)
    if main_agent.get("pane_id") != endpoint.pane_id or not agent_matches_identity(
        main_agent, "codex", endpoint.expected_session_id, endpoint.expected_terminal_id
    ):
        raise ValueError("main agent identity mismatch before launch")
    instruction["main_agent_session_id"] = session_value(main_agent)
    dump_json(inst_path, instruction)


class _LaunchAttempt:
    """One start-to-delivery attempt, and the naming state a retry inside it needs."""

    def __init__(
        self,
        instruction: dict[str, Any],
        contract_path: Path,
        name: str | None,
        agent_args: list[str],
    ) -> None:
        self.instruction = instruction
        self.contract_path = contract_path
        self.is_coworker = bool(instruction.get("parent_instruction_path"))
        self.name_is_derived = name is None
        self.base_candidate_name = ""
        self.known_taken_names: set[str] = set()
        if self.name_is_derived:
            agent_role = "coworker" if self.is_coworker else "worker"
            workroom = instruction.get("role") or instruction["app"]
            self.base_candidate_name = derive_agent_name(agent_role, str(workroom))
            self.known_taken_names = live_names(run_herdr(["agent", "list"]))
            name = unique_agent_name(self.base_candidate_name, self.known_taken_names)
            self.known_taken_names.add(name)
        self.name = name
        self.agent_kind = str(instruction.get("agent_kind"))
        self.base_provider_args = provider_profile_args(instruction, agent_args)

    def _next_name(self) -> str:
        self.name = unique_agent_name(self.base_candidate_name, self.known_taken_names)
        self.known_taken_names.add(self.name)
        return self.name

    def _provider_args(self) -> list[str]:
        if self.agent_kind == "claude":
            return [
                "--session-id",
                str(self.instruction["session_id"]),
                "--name",
                str(self.name),
                "--append-system-prompt-file",
                str(self.contract_path),
                *self.base_provider_args,
            ]
        if self.agent_kind == "codex":
            return [
                "-c",
                (
                    "developer_instructions=Before any task action, read and follow "
                    f"the mandatory contract at {self.contract_path}."
                ),
                *self.base_provider_args,
            ]
        raise ValueError(f"unsupported agent kind {self.agent_kind!r}")

    def _start_agent(self, pane_id: str, provider_args: list[str]) -> ValueError | None:
        """Start the agent, minting a fresh name for as long as herdr reports a
        collision. Returns the error to weigh against the settled agent, if any.
        """
        collision_retries = 0
        while True:
            try:
                start_agent_when_pane_ready(
                    [
                        "agent",
                        "start",
                        str(self.name),
                        "--kind",
                        self.agent_kind,
                        "--pane",
                        pane_id,
                        "--",
                        *provider_args,
                    ]
                )
                return None
            except HerdrCommandError as exc:
                if (
                    not self.name_is_derived
                    or exc.error_code != "agent_name_taken"
                    or collision_retries >= MAX_NAME_COLLISION_ATTEMPTS
                ):
                    return exc
                collision_retries += 1
                self._next_name()
                provider_args = self._provider_args()
            except ValueError as exc:
                return exc

    def _clear_startup_gate(self, pane_id: str, gate: tuple[str, bool] | None) -> None:
        if self.agent_kind == "claude":
            # Claude Code's startup gates -- folder trust first among them --
            # render as a select list whose highlighted option is "No, exit".
            # Enter, or the task itself which ends in one, picks that option and
            # exits a worker that had already booted. No retry can answer this; a
            # human can, in this pane, and answering it also records the decision
            # so the next launch into this directory runs clean.
            gate_excerpt, marker_seen = gate if gate else ("", False)
            recovery = (
                'the gate preselects "No, exit" and anything sent there would '
                "exit the worker. Answer it in the Herdr tab (or "
                f"`herdr agent send-keys {pane_id} down enter` to take the "
                "second option), then close that pane and run this launch again"
                if marker_seen
                else "only a human can answer what it is waiting on, and a "
                "blind keystroke risks picking a decline option that exits "
                "the worker. Answer it in the Herdr tab from what the pane "
                "shows below, then close that pane and run this launch again"
            )
            raise LaunchAttemptError(
                f"the worker in pane {pane_id!r} stopped on a Claude Code "
                "startup gate before its first turn, so the task cannot be "
                f"submitted: {recovery}",
                retryable=False,
                pane_id=pane_id,
                keep_pane=True,
                pane_excerpt=gate_excerpt or pane_excerpt(pane_id),
            )
        run_herdr(["agent", "send-keys", pane_id, "enter"])
        run_herdr(
            [
                "agent",
                "wait",
                pane_id,
                "--until",
                "idle",
                "--until",
                "blocked",
                "--timeout",
                "15000",
            ]
        )

    def _bind_session(self, pane_id: str) -> tuple[str, str | None, str | None]:
        terminal_id, session_id = live_agent_identity(pane_id, self.agent_kind)
        if self.agent_kind != "claude":
            return terminal_id, session_id, None
        observed_session_id = wait_for_agent_session(pane_id, required=False)
        if observed_session_id is None:
            # herdr reads a Claude pane's session from its terminal title, and
            # some panes never carry one. The agent was started with
            # --session-id, so the preassigned id is the session running in that
            # pane; recording it beats discarding a task the worker already
            # accepted.
            return (
                terminal_id,
                self.instruction.get("session_id"),
                f"herdr never exposed agent_session.value for pane {pane_id!r}; "
                "recorded the session id this launch assigned the agent instead",
            )
        if observed_session_id != self.instruction.get("session_id"):
            raise ValueError(
                f"launched Claude session {observed_session_id!r} does not match preassigned session "
                f"{self.instruction.get('session_id')!r}"
            )
        return terminal_id, observed_session_id, None

    def run(self) -> dict[str, Any]:
        # Set once the worker is confirmed to be holding the task: from there on
        # nothing in this launch may close its pane, for the same reason a missed
        # prompt handoff does not -- the agent is booted and working, and only
        # this launcher's own bookkeeping is unfinished.
        delivered = False
        provider_args = self._provider_args()
        pane_label_warning: str | None = None
        try:
            pane_id, tab_id = create_worker_pane(self.instruction)
        except ValueError as exc:
            # No pane survived this, including the tab-mismatch case that closes
            # its own; there is nothing to keep and nothing to read.
            raise LaunchAttemptError(str(exc), retryable=is_retryable(exc)) from exc
        try:
            start_error = self._start_agent(pane_id, provider_args)

            try:
                agent = settled_agent(pane_id)
            except ValueError:
                if start_error is not None:
                    raise start_error
                raise
            if start_error is not None and agent.get("agent_status") != "blocked":
                raise start_error
            pane_label_warning = name_worker_pane(pane_id, str(self.name))
            gate = startup_gate(pane_id, agent) if self.agent_kind == "claude" else None
            if gate is not None or agent.get("agent_status") == "blocked":
                self._clear_startup_gate(pane_id, gate)

            prompt_task_with_confirmation(
                pane_id, str(self.instruction["task"]), self.agent_kind
            )
            delivered = True
            terminal_id, session_id, session_fingerprint_warning = self._bind_session(
                pane_id
            )
        except LaunchAttemptError:
            raise
        except PromptDeliveryError as exc:
            # The agent is up; only the opening prompt did not land. Closing the
            # pane here would throw away a booted session whose sole defect is a
            # missed handoff, so leave it standing and say where it is.
            raise LaunchAttemptError(
                str(exc),
                retryable=False,
                pane_id=exc.pane_id,
                keep_pane=True,
                pane_excerpt=pane_excerpt(exc.pane_id),
            ) from exc
        except ValueError as exc:
            excerpt = pane_excerpt(pane_id)
            if delivered:
                raise LaunchAttemptError(
                    f"{exc}; the task was already confirmed delivered, so the worker in "
                    f"pane {pane_id!r} is running it and only this launch's own "
                    "bookkeeping failed -- no receipt is written, so the instruction "
                    "stays pending until someone reconciles it",
                    retryable=False,
                    pane_id=pane_id,
                    keep_pane=True,
                    pane_excerpt=excerpt,
                ) from exc
            raise LaunchAttemptError(
                str(exc),
                retryable=is_retryable(exc, excerpt),
                pane_id=pane_id,
                pane_excerpt=excerpt,
            ) from exc

        return {
            "name": str(self.name),
            "pane_id": pane_id,
            "tab_id": tab_id,
            "session_id": session_id,
            "herdr_terminal_id": terminal_id,
            "pane_label_warning": pane_label_warning,
            "session_fingerprint_warning": session_fingerprint_warning,
        }


def run_attempts(
    attempt: _LaunchAttempt, inst_path: Path, instruction: dict[str, Any]
) -> dict[str, Any]:
    """Retry the whole launch over transient trips, on a fresh session id each time."""
    agent_kind = attempt.agent_kind
    spent = spent_session_ids(inst_path)
    if agent_kind == "claude" and str(instruction["session_id"]) in spent:
        # An earlier run of this launcher already handed that id to a started
        # agent, so reusing it now would only reproduce its startup refusal.
        rotate_session_id(inst_path, instruction)

    backoff = launch_retry_backoff_seconds()
    attempts: list[dict[str, Any]] = []
    for index, delay in enumerate(backoff):
        if delay:
            sleep(delay)
        if index and agent_kind == "claude" and attempts[-1]["pane_id"]:
            # Only an attempt that got as far as a pane can have started an agent
            # on the current id; one that never did leaves it unspent.
            rotate_session_id(inst_path, instruction)
        session_id_used = instruction.get("session_id")
        if session_id_used:
            spent.add(str(session_id_used))
        try:
            return attempt.run()
        except LaunchAttemptError as exc:
            record: dict[str, Any] = {
                "attempt": index + 1,
                "pane_id": exc.pane_id,
                "session_id": session_id_used,
                "retryable": exc.retryable,
                "pane_left_open": exc.keep_pane,
                "error": str(exc),
                "pane_excerpt": exc.pane_excerpt or None,
                "failed_at": datetime.now(timezone.utc).isoformat(),
            }
            if exc.pane_id and not exc.keep_pane:
                try:
                    run_herdr(["pane", "close", exc.pane_id])
                except ValueError as close_error:
                    record["pane_close_error"] = str(close_error)
            attempts.append(record)
            failure_path = record_launch_failure(inst_path, attempts, spent)
            if exc.retryable and index < len(backoff) - 1:
                continue
            raise ValueError(launch_failure_message(exc, attempts, failure_path)) from exc
    raise AssertionError("launch backoff schedule was empty")


def write_launch_receipt(
    inst_path: Path,
    instruction: dict[str, Any],
    landed: dict[str, Any],
    agent_kind: str,
    tab_label_warning: str | None,
) -> Path:
    receipt = {
        "instruction_path": str(inst_path),
        "contract_sha256": instruction["contract_sha256"],
        "agent_kind": agent_kind,
        **landed,
        "launched_at": datetime.now(timezone.utc).isoformat(),
    }
    if tab_label_warning is not None:
        receipt["tab_label_warning"] = tab_label_warning
    receipt_path = launch_receipt_path(inst_path)
    dump_json(receipt_path, receipt)
    launch_failure_path(inst_path).unlink(missing_ok=True)
    return receipt_path


def decoy_warning(
    instruction: dict[str, Any], landed: dict[str, Any], is_coworker: bool
) -> str | None:
    """Name the coordinator's own pane, and flag panes still posing as one."""
    try:
        agent_list_payload = run_herdr(["agent", "list"])
    except ValueError:
        return None
    if not is_coworker:
        try:
            ensure_coordinator_named(instruction, live_names(agent_list_payload))
        except ValueError:
            pass
    exclude_pane_ids = {landed["pane_id"]}
    for pane_field in ("main_agent_herdr_pane_id", "root_main_agent_herdr_pane_id"):
        pane_value = instruction.get(pane_field)
        if isinstance(pane_value, str) and pane_value:
            exclude_pane_ids.add(pane_value)
    try:
        return decoy_orchestrator_warning(agent_list_payload, exclude_pane_ids)
    except ValueError:
        return None


def confirm_warning(inst_path: Path) -> str | None:
    """Bind pane and session identities onto the instruction, against the receipt
    just written.

    Left to a separate coordinator step, the instruction stayed "pending" with no
    herdr_pane_id whenever that step was missed, and every status report the
    worker sent failed with "dispatch instruction has no worker herdr pane" --
    with the worker already running the task.
    """
    try:
        confirm_dispatch(inst_path)
    except (ValueError, KeyError, OSError) as exc:
        stem = inst_path.name.removesuffix(".json")
        app, separator, slug = stem.partition("--")
        retry = (
            f"dispatch-task.py confirm --app {app} --slug {slug}"
            if separator
            else "dispatch-task.py confirm"
        )
        return (
            f"the worker is running but this dispatch is not confirmed ({exc}); "
            f"it cannot report status until you run: {retry}"
        )
    return None


def launch(
    instruction_path: str,
    name: str | None,
    agent_args: list[str],
) -> dict[str, Any]:
    inst_path, instruction, contract_path = load_pending_instruction(instruction_path)
    pin_codex_main_agent(inst_path, instruction)

    attempt = _LaunchAttempt(instruction, contract_path, name, agent_args)
    tab_label_warning = (
        None if attempt.is_coworker else name_task_tab(instruction, inst_path)
    )

    landed = run_attempts(attempt, inst_path, instruction)
    receipt_path = write_launch_receipt(
        inst_path, instruction, landed, attempt.agent_kind, tab_label_warning
    )

    result: dict[str, Any] = {"launch_receipt_path": str(receipt_path), "launched": True}
    decoy = decoy_warning(instruction, landed, attempt.is_coworker)
    confirm = confirm_warning(inst_path)
    result["confirmed"] = confirm is None

    warnings = [
        warning
        for warning in (
            tab_label_warning,
            landed.get("pane_label_warning"),
            landed.get("session_fingerprint_warning"),
            decoy,
            confirm,
        )
        if isinstance(warning, str) and warning
    ]
    if warnings:
        result["warning"] = "; ".join(warnings)
    return result
