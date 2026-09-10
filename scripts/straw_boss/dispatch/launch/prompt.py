"""Handing the worker its opening task and proving the turn started."""

from __future__ import annotations

import base64
from time import sleep

from straw_boss.dispatch.launch.agent import live_agent
from straw_boss.dispatch.launch.retry import prompt_retry_backoff_seconds
from straw_boss.dispatch.state import sha256_text
from straw_boss.herdr.transport import (
    HerdrCommandError,
    confirm_transcript_contains,
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

def task_start_prompt(task: str) -> str:
    return f"Begin contract task.\n{task_delivery_marker(task)}"

def prompt_task_with_confirmation(pane_id: str, task: str, agent_kind: str) -> None:
    marker = task_delivery_marker(task)
    prompt = task_start_prompt(task)
    backoff = prompt_retry_backoff_seconds()
    attempts_remaining = len(backoff)
    while attempts_remaining:
        delay = backoff[len(backoff) - attempts_remaining]
        attempts_remaining -= 1
        if delay:
            sleep(delay)
        pre_send_status = live_agent(pane_id).get("agent_status")
        pre_send_status = pre_send_status if isinstance(pre_send_status, str) else None
        try:
            run_herdr(prompt_delivery_args(pane_id, prompt, pre_send_status))
        except HerdrCommandError as exc:
            if exc.error_code != "agent_prompt_stalled":
                raise
            if not attempts_remaining:
                raise PromptDeliveryError(
                    f"sent the initial task to pane {pane_id!r} via herdr "
                    f"{len(backoff)} times but herdr confirmed no attempt started a turn "
                    "(agent_prompt_stalled: the prompt likely reached only the composer, "
                    "not a real turn); refusing to write a launch receipt",
                    pane_id,
                ) from exc
            continue
        if confirm_transcript_contains(pane_id, marker, agent_kind):
            return
    raise PromptDeliveryError(
        f"sent the initial task to pane {pane_id!r} via herdr {len(backoff)} times but "
        "could not confirm it landed in the transcript via its delivery marker; refusing "
        "to write a launch receipt",
        pane_id,
    )
