"""Provider arguments a dispatch instruction pins for its worker."""

from __future__ import annotations


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
    else:
        raise ValueError(f"unsupported agent kind {agent_kind!r}")

    return [*resolved, *extra_args]
