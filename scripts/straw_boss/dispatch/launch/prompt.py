"""Handing the worker its opening task and proving the turn started."""

from __future__ import annotations

import base64
from time import sleep

from straw_boss.dispatch.launch.agent import live_agent
from straw_boss.dispatch.launch.retry import prompt_retry_backoff_seconds
from straw_boss.dispatch.state import sha256_text
from straw_boss.herdr.transport import (
    HerdrCommandError,
    confirm_prompt_delivery,
    prompt_delivery_args,
    run_herdr,
)


TASK_DELIVERY_MARKER_PREFIX = "sb256"

class PromptDeliveryError(ValueError):
    """The agent started but its first prompt could not be confirmed as a turn.

    Kept distinct from other launch failures because the failure surface is
    different: the pane and the agent are both alive and healthy, only the
    handoff of the opening prompt did not land. Destroying that pane discards a
    booted agent and forces a full relaunch, so the caller leaves it standing
    and reports where it is.
    """

    def __init__(self, message: str, pane_id: str) -> None:
        super().__init__(message)
        self.pane_id = pane_id

def task_delivery_marker(task: str) -> str:
    digest = base64.urlsafe_b64encode(bytes.fromhex(sha256_text(task))).decode("ascii")
    return f"[{TASK_DELIVERY_MARKER_PREFIX}:{digest.rstrip('=')}]"

def task_start_prompt(task: str, contract_path: object | None = None) -> str:
    prefix = (
        f"Before any task action, read and follow the mandatory contract at {contract_path}.\n"
        if contract_path
        else ""
    )
    return f"{prefix}Begin contract task.\n{task_delivery_marker(task)}"

def prompt_task_with_confirmation(
    pane_id: str,
    task: str,
    agent_kind: str,
    contract_path: object | None = None,
) -> None:
    marker = task_delivery_marker(task)
    prompt = task_start_prompt(task, contract_path)
    backoff = prompt_retry_backoff_seconds()
    for attempt, delay in enumerate(backoff):
        if delay:
            sleep(delay)
        pre_send_status = live_agent(pane_id).get("agent_status")
        pre_send_status = pre_send_status if isinstance(pre_send_status, str) else None
        try:
            receipt = run_herdr(prompt_delivery_args(pane_id, prompt, pre_send_status))
        except HerdrCommandError as exc:
            # Preserve the launcher's bounded startup recovery. Transcript
            # absence after an accepted submission never takes this branch.
            if exc.error_code != "agent_prompt_stalled":
                raise
            if attempt + 1 < len(backoff):
                continue
            raise PromptDeliveryError(
                f"herdr reported agent_prompt_stalled for {len(backoff)} initial "
                f"task attempts in pane {pane_id!r}; refusing to write a launch receipt",
                pane_id,
            ) from exc
        try:
            confirm_prompt_delivery(receipt, pane_id, marker, agent_kind, pre_send_status)
        except ValueError as exc:
            raise PromptDeliveryError(
                f"could not confirm initial task delivery to pane {pane_id!r}: {exc}; "
                "the initial task was not resent; refusing to write a launch receipt",
                pane_id,
            ) from exc
        return
    raise PromptDeliveryError("no initial task submission attempts configured", pane_id)
