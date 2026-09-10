"""The worker's herdr pane and the tab it shares with its coordinator."""

from __future__ import annotations

from pathlib import Path

from straw_boss.herdr.transport import run_herdr, run_herdr_raw


PANE_EXCERPT_LINES = 60

PANE_EXCERPT_MAX_CHARS = 2000

def herdr_pane(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["pane", "get", pane_id])
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict) or pane.get("pane_id") != pane_id:
        raise ValueError(f"herdr could not resolve pane {pane_id!r}")
    if not pane.get("tab_id"):
        raise ValueError(f"herdr pane {pane_id!r} did not expose a tab id")
    return pane

def create_worker_pane(instruction: dict[str, object]) -> tuple[str, str]:
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        raise ValueError("dispatch instruction has no main-agent herdr pane")
    main_pane = herdr_pane(main_pane_id)
    main_tab_id = str(main_pane["tab_id"])

    cwd = Path(str(instruction.get("repo_root", ""))).resolve()
    if not cwd.is_dir():
        raise ValueError(f"dispatch repo_root is not a directory: {cwd}")
    payload = run_herdr(
        [
            "pane",
            "split",
            main_pane_id,
            "--direction",
            "right",
            "--cwd",
            str(cwd),
            "--no-focus",
        ]
    )
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict):
        raise ValueError("herdr pane split did not return a pane")
    pane_id = pane.get("pane_id")
    tab_id = pane.get("tab_id")
    if not isinstance(pane_id, str) or not pane_id:
        raise ValueError("herdr pane split did not return a pane id")
    if tab_id != main_tab_id:
        try:
            run_herdr(["pane", "close", pane_id])
        except ValueError as close_error:
            raise ValueError(
                f"worker pane landed in tab {tab_id!r}, expected {main_tab_id!r}; "
                f"cleanup also failed: {close_error}"
            ) from close_error
        raise ValueError(
            f"worker pane landed in tab {tab_id!r}, expected main-agent tab {main_tab_id!r}"
        )
    return pane_id, main_tab_id

def name_worker_pane(pane_id: str, name: str) -> str | None:
    """Best-effort pane label after the final agent name is known.

    A label improves operator orientation but is not part of dispatch identity,
    so two failed attempts return a warning instead of blocking task delivery.
    """
    last_error: ValueError | None = None
    for _ in range(2):
        try:
            run_herdr(["pane", "rename", pane_id, name])
            return None
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    return f"worker pane {pane_id!r} could not be named {name!r}: {last_error}"

def dispatch_slug(inst_path: Path) -> str:
    """The task slug an instruction filename carries, as `<app>--<slug>.json`."""
    stem = inst_path.stem
    _, separator, slug = stem.partition("--")
    if not separator or not slug:
        raise ValueError(f"instruction filename {stem!r} carries no '--<slug>' part")
    return slug

def name_task_tab(instruction: dict[str, object], inst_path: Path) -> str | None:
    """Best-effort shared-tab label before the worker pane is created.

    The tab is labelled with the task, not the coordinator: every dispatch for
    one app derives the same coordinator name, so naming tabs after it made two
    tabs working different tasks read identically. Agent names stay on panes,
    where `ensure_coordinator_named` and `name_worker_pane` put them. A tab
    hosting several dispatches shows the most recently dispatched task.
    """
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        return "task tab naming skipped: dispatch has no main-agent pane"
    try:
        label = dispatch_slug(inst_path)
        tab_id = str(herdr_pane(main_pane_id)["tab_id"])
    except ValueError as exc:
        return f"task tab naming failed; dispatch continued: {exc}"
    last_error: ValueError | None = None
    for _ in range(2):
        try:
            run_herdr(["tab", "rename", tab_id, label])
            return None
        except ValueError as exc:
            last_error = exc
    assert last_error is not None
    return (
        f"task tab {tab_id!r} could not be named {label!r}; "
        f"dispatch continued: {last_error}"
    )

def pane_excerpt(pane_id: str) -> str:
    """What the worker pane was showing when an attempt failed.

    The agent's own last words -- a startup gate, a refused session id, a crash
    -- exist only on that pane, and the failure path closes it, so read it
    before deciding anything.
    """
    try:
        text = run_herdr_raw(
            [
                "pane",
                "read",
                pane_id,
                "--lines",
                str(PANE_EXCERPT_LINES),
                "--source",
                "visible",
            ]
        )
    except ValueError:
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)[-PANE_EXCERPT_MAX_CHARS:].strip()
