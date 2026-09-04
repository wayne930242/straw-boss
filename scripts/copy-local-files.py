#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Validate and copy one app's declared local files into a worktree."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def load_config(repo_root: Path) -> dict[str, Any]:
    path = repo_root / ".claude" / "straw-boss" / "apps.json"
    if not path.is_file():
        raise ValueError(f"apps config is missing: {path}")
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"apps config cannot be read: {path}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("apps"), list):
        raise ValueError(f"apps config must contain an apps array: {path}")
    return payload


def configured_app(payload: dict[str, Any], app_name: str) -> dict[str, Any]:
    matches = [
        item
        for item in payload["apps"]
        if isinstance(item, dict) and item.get("name") == app_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"apps config must contain exactly one app named {app_name!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def relative_path(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty relative path")
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"{field} must be relative: {value!r}")
    return path


def resolve_inside(root: Path, relative: Path, field: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{field} escapes its root: {relative.as_posix()!r}")
    return resolved


def git_toplevel(path: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"cannot resolve git top-level for {path}: {exc}") from exc
    return Path(result.stdout.strip()).resolve()


def describe(entry: dict[str, Any]) -> str:
    path = str(entry["path"])
    note = entry.get("note")
    return f"{path} ({note})" if isinstance(note, str) and note else path


def copy_local_files(
    repo_root: Path,
    app_name: str,
    worktree: Path,
    *,
    allow_sensitive: bool,
) -> dict[str, list[str]]:
    repo_root = repo_root.resolve()
    worktree = worktree.resolve()
    if not repo_root.is_dir():
        raise ValueError(f"repo root is not a directory: {repo_root}")
    if not worktree.is_dir():
        raise ValueError(f"worktree is not a directory: {worktree}")

    app = configured_app(load_config(repo_root), app_name)
    app_dir = relative_path(app.get("dir"), f"app {app_name!r} dir")
    source_root = resolve_inside(repo_root, app_dir, f"app {app_name!r} dir")
    if not source_root.is_dir():
        raise ValueError(f"app source directory is missing: {app_dir.as_posix()}")
    source_git_root = git_toplevel(source_root)
    worktree_git_root = git_toplevel(worktree)
    if worktree_git_root != worktree:
        raise ValueError(
            f"worktree must be its git top-level: expected {worktree}, "
            f"found {worktree_git_root}"
        )
    try:
        app_path_in_worktree = source_root.relative_to(source_git_root)
    except ValueError as exc:
        raise ValueError(
            f"app source {source_root} is outside its git top-level {source_git_root}"
        ) from exc
    destination_root = resolve_inside(
        worktree, app_path_in_worktree, f"app {app_name!r} worktree directory"
    )

    entries = app.get("localFiles", [])
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise ValueError(f"app {app_name!r} localFiles must be an array")

    copies: list[tuple[dict[str, Any], Path, Path]] = []
    skipped_optional: list[str] = []
    missing_required: list[str] = []
    unapproved_sensitive: list[str] = []
    destination_conflicts: list[str] = []
    planned_destinations: list[tuple[str, Path]] = []

    for index, raw_entry in enumerate(entries):
        if not isinstance(raw_entry, dict):
            raise ValueError(f"localFiles[{index}] must be an object")
        entry = raw_entry
        relative = relative_path(entry.get("path"), f"localFiles[{index}].path")
        source = resolve_inside(
            source_root, relative, f"localFiles[{index}].path"
        )
        destination = resolve_inside(
            destination_root, relative, f"localFiles[{index}].path destination"
        )
        optional = entry.get("optional", False)
        sensitive = entry.get("sensitive", False)
        if not isinstance(optional, bool):
            raise ValueError(f"localFiles[{index}].optional must be a boolean")
        if not isinstance(sensitive, bool):
            raise ValueError(f"localFiles[{index}].sensitive must be a boolean")

        if not source.exists():
            if optional:
                skipped_optional.append(describe(entry))
            else:
                missing_required.append(describe(entry))
            continue
        if sensitive and not allow_sensitive:
            unapproved_sensitive.append(describe(entry))
        if destination.exists() or destination.is_symlink():
            destination_conflicts.append(relative.as_posix())
        for planned_name, planned_destination in planned_destinations:
            if (
                destination == planned_destination
                or destination.is_relative_to(planned_destination)
                or planned_destination.is_relative_to(destination)
            ):
                destination_conflicts.append(
                    f"{relative.as_posix()} overlaps {planned_name}"
                )
        planned_destinations.append((relative.as_posix(), destination))
        copies.append((entry, source, destination))

    problems: list[str] = []
    if missing_required:
        problems.append("missing required local files: " + ", ".join(missing_required))
    if unapproved_sensitive:
        problems.append(
            "sensitive local files require --allow-sensitive after user approval: "
            + ", ".join(unapproved_sensitive)
        )
    if destination_conflicts:
        problems.append(
            "worktree destinations already exist: " + ", ".join(destination_conflicts)
        )
    if problems:
        raise ValueError("; ".join(problems))

    copied: list[str] = []
    for entry, source, destination in copies:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
        copied.append(describe(entry))

    return {"copied": copied, "skipped_optional": skipped_optional}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy configured app-local files into a verified worktree."
    )
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--app", required=True)
    parser.add_argument("--worktree", required=True, type=Path)
    parser.add_argument("--allow-sensitive", action="store_true")
    args = parser.parse_args()

    try:
        result = copy_local_files(
            args.repo_root,
            args.app,
            args.worktree,
            allow_sensitive=args.allow_sensitive,
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
