"""Provider arguments a dispatch instruction pins for its worker."""

from __future__ import annotations

from straw_boss.dispatch.permission import permission_flags, tier_flags
from straw_boss.dispatch.coworker_permission import validate_coworker_args


def _option_present(args: list[str], flags: tuple[str, ...]) -> bool:
    return any(
        arg in flags or any(arg.startswith(f"{flag}=") for flag in flags)
        for arg in args
    )

def _codex_effort_present(args: list[str]) -> bool:
    return any(
        arg.startswith("model_reasoning_effort=")
        or arg.startswith("-c=model_reasoning_effort=")
        or arg.startswith("--config=model_reasoning_effort=")
        for arg in args
    )

def provider_profile_args(
    instruction: dict[str, object], extra_args: list[str]
) -> list[str]:
    agent_kind = str(instruction.get("agent_kind"))
    if instruction.get("parent_instruction_path"):
        validate_coworker_args(agent_kind, extra_args)
        if instruction.get("agent_profile") is not None:
            raise ValueError("coworker provider profiles cannot override inherited permissions")
    profile = instruction.get("agent_profile")
    model = instruction.get("agent_model")
    effort = instruction.get("agent_effort")
    advisor = instruction.get("advisor_model")

    for value, label in (
        (profile, "agent_profile"),
        (model, "agent_model"),
        (effort, "agent_effort"),
        (advisor, "advisor_model"),
    ):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"dispatch instruction has invalid {label}")

    resolved: list[str] = []
    # Mirror the main agent's restriction tier before anything else, so a worker
    # never launches more guarded than the session that dispatched it. A kind
    # with no documented flag for the tier keeps the provider default, which is
    # never more permissive than what is being mirrored. A caller that writes
    # any permission flag of its own owns the whole slot: matching only the
    # identical flag used to send `--permission-mode plan` alongside a mirrored
    # `--dangerously-skip-permissions`.
    if not _option_present(extra_args, permission_flags(agent_kind)):
        resolved.extend(
            tier_flags(instruction.get("main_agent_permission_tier"), agent_kind)
        )
    if agent_kind == "claude":
        mappings = (
            (profile, ("--agent",)),
            (model, ("--model",)),
            (effort, ("--effort",)),
            (advisor, ("--advisor",)),
        )
        for value, flags in mappings:
            if value is None:
                continue
            if _option_present(extra_args, flags):
                raise ValueError(
                    f"raw provider argument {flags[0]} duplicates the dispatch instruction"
                )
            resolved.extend([flags[0], str(value)])
    elif agent_kind == "codex":
        if advisor is not None:
            raise ValueError("Codex has no native advisor; advisor_model requires Claude Code")
        for value, flags, emitted_flag in (
            (profile, ("--profile", "-p"), "--profile"),
            (model, ("--model", "-m"), "--model"),
        ):
            if value is None:
                continue
            if _option_present(extra_args, flags):
                raise ValueError(
                    f"raw provider argument {emitted_flag} duplicates the dispatch instruction"
                )
            resolved.extend([emitted_flag, str(value)])
        if effort is not None:
            if _codex_effort_present(extra_args):
                raise ValueError(
                    "raw model_reasoning_effort duplicates the dispatch instruction"
                )
            resolved.extend(["-c", f"model_reasoning_effort={effort}"])
    elif agent_kind in {"agy", "antigravity"}:
        if advisor is not None:
            raise ValueError(
                "Antigravity has no native advisor; advisor_model requires Claude Code"
            )
        mappings = (
            (profile, ("--agent",)),
            (model, ("--model",)),
            (effort, ("--effort",)),
        )
        for value, flags in mappings:
            if value is None:
                continue
            if _option_present(extra_args, flags):
                raise ValueError(
                    f"raw provider argument {flags[0]} duplicates the dispatch instruction"
                )
            resolved.extend([flags[0], str(value)])
    else:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    return [*resolved, *extra_args]
