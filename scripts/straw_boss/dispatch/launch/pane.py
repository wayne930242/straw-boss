"""The worker's herdr pane and the tab it shares with its coordinator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from straw_boss.herdr.transport import run_herdr, run_herdr_raw


PANE_EXCERPT_LINES = 60

PANE_EXCERPT_MAX_CHARS = 2000

WORKER_COLUMNS = 4

# A split ratio this close to its equal-width target is left alone.
COLUMN_RATIO_TOLERANCE = 0.01

RECT_KEYS = ("x", "y", "width", "height")

def herdr_pane(pane_id: str) -> dict[str, object]:
    payload = run_herdr(["pane", "get", pane_id])
    pane = payload.get("result", {}).get("pane")
    if not isinstance(pane, dict) or pane.get("pane_id") != pane_id:
        raise ValueError(f"herdr could not resolve pane {pane_id!r}")
    if not pane.get("tab_id"):
        raise ValueError(f"herdr pane {pane_id!r} did not expose a tab id")
    return pane

def is_rect(value: object) -> bool:
    return isinstance(value, dict) and all(isinstance(value.get(key), int) for key in RECT_KEYS)

def tab_layout(pane_id: str) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, Any]]]:
    """The area, panes, and splits of the tab holding `pane_id`."""
    layout = run_herdr(["pane", "layout", "--pane", pane_id]).get("result", {}).get("layout")
    if not isinstance(layout, dict) or not is_rect(layout.get("area")):
        raise ValueError(f"herdr pane layout did not return a tab area for {pane_id!r}")
    panes = [
        pane
        for pane in layout.get("panes", [])
        if isinstance(pane, dict) and isinstance(pane.get("pane_id"), str) and is_rect(pane.get("rect"))
    ]
    splits = [
        split
        for split in layout.get("splits", [])
        if isinstance(split, dict)
        and isinstance(split.get("ratio"), (int, float))
        and is_rect(split.get("rect"))
    ]
    return layout["area"], panes, splits

def worker_split_target(main_pane_id: str) -> tuple[str, str]:
    """The pane to split for the next worker, and the direction to split it.

    The first `WORKER_COLUMNS` workers each open a full-height column beside the
    coordinator. Past that, a worker stacks under the rightmost column that
    still spans the tab's full height -- the oldest, since each new column opens
    beside the coordinator -- so eight workers read as four columns of two
    instead of eight slivers. Once every column is stacked, a new column opens
    and the next worker stacks under it.
    """
    area, panes, _ = tab_layout(main_pane_id)
    workers = [pane for pane in panes if pane["pane_id"] != main_pane_id]
    if len(workers) < WORKER_COLUMNS:
        return main_pane_id, "right"
    columns = [
        pane
        for pane in workers
        if pane["rect"]["y"] == area["y"] and pane["rect"]["height"] == area["height"]
    ]
    if not columns:
        return main_pane_id, "right"
    rightmost = max(columns, key=lambda pane: pane["rect"]["x"])
    return str(rightmost["pane_id"]), "down"

def column_resizes(
    panes: list[dict[str, Any]], splits: list[dict[str, Any]]
) -> list[tuple[str, str, float]]:
    """The `pane resize` moves that give every column in a tab an equal width.

    herdr resizes a split by moving one pane's edge by a ratio delta, and a
    split's ratio is relative to its own area, so every column split is set
    from one layout read. A column is a distinct left edge, so a stacked
    column counts once.
    """
    resizes: list[tuple[str, str, float]] = []
    for split in splits:
        if split.get("direction") != "right":
            continue
        rect = split["rect"]
        inside = [
            pane
            for pane in panes
            if rect["x"] <= pane["rect"]["x"]
            and pane["rect"]["x"] + pane["rect"]["width"] <= rect["x"] + rect["width"]
            and rect["y"] <= pane["rect"]["y"]
            and pane["rect"]["y"] + pane["rect"]["height"] <= rect["y"] + rect["height"]
        ]
        edges = {pane["rect"]["x"] for pane in inside} - {rect["x"]}
        if not edges:
            continue
        ratio = float(split["ratio"])
        boundary = min(edges, key=lambda edge: abs(edge - (rect["x"] + rect["width"] * ratio)))
        left = [pane for pane in inside if pane["rect"]["x"] < boundary]
        right = [pane for pane in inside if pane["rect"]["x"] >= boundary]
        left_columns = len({pane["rect"]["x"] for pane in left})
        right_columns = len({pane["rect"]["x"] for pane in right})
        delta = left_columns / (left_columns + right_columns) - ratio
        if abs(delta) < COLUMN_RATIO_TOLERANCE:
            continue
        if delta > 0:
            edge_pane = next(
                (pane for pane in left if pane["rect"]["x"] + pane["rect"]["width"] == boundary),
                None,
            )
            direction = "right"
        else:
            edge_pane = next(pane for pane in right if pane["rect"]["x"] == boundary)
            direction = "left"
        if edge_pane is not None:
            resizes.append((edge_pane["pane_id"], direction, abs(delta)))
    return resizes

def balance_worker_columns(main_pane_id: str) -> str | None:
    """Best-effort equal column widths after a worker opens a new column.

    Each new column halves the coordinator pane it splits from, so without this
    the coordinator narrows with every column. Width is orientation, not
    dispatch identity, so a failure returns a warning instead of failing the
    launch that already owns the new pane.
    """
    try:
        _, panes, splits = tab_layout(main_pane_id)
        for pane_id, direction, amount in column_resizes(panes, splits):
            run_herdr(
                [
                    "pane",
                    "resize",
                    "--pane",
                    pane_id,
                    "--direction",
                    direction,
                    "--amount",
                    f"{amount:.4f}",
                ]
            )
    except ValueError as exc:
        return f"worker columns could not be balanced; dispatch continued: {exc}"
    return None

def close_worker_pane(pane_id: str, main_pane_id: str | None) -> str | None:
    """Close a worker pane and give the surviving columns their width back.

    Whichever neighbour absorbs a closed column keeps its width, so a tab that
    was balanced on every split drifts out of balance on every close. Balancing
    here returns the same best-effort warning as the split path; the close
    itself has already happened by then.
    """
    run_herdr(["pane", "close", pane_id])
    if not main_pane_id:
        return "surviving columns were not balanced: dispatch has no main-agent pane"
    return balance_worker_columns(main_pane_id)

def create_worker_pane(instruction: dict[str, object]) -> tuple[str, str, str | None]:
    """Split the worker's pane into the coordinator's tab.

    Returns the pane, its tab, and a column-balancing warning when one applies.
    """
    main_pane_id = instruction.get("main_agent_herdr_pane_id")
    if not isinstance(main_pane_id, str) or not main_pane_id:
        raise ValueError("dispatch instruction has no main-agent herdr pane")
    main_pane = herdr_pane(main_pane_id)
    main_tab_id = str(main_pane["tab_id"])

    cwd = Path(str(instruction.get("repo_root", ""))).resolve()
    if not cwd.is_dir():
        raise ValueError(f"dispatch repo_root is not a directory: {cwd}")
    split_pane_id, direction = worker_split_target(main_pane_id)
    payload = run_herdr(
        [
            "pane",
            "split",
            split_pane_id,
            "--direction",
            direction,
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
    balance_warning = balance_worker_columns(main_pane_id) if direction == "right" else None
    return pane_id, main_tab_id, balance_warning

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
