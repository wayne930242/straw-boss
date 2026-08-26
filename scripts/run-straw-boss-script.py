#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run a contract-approved script from the current Straw Boss installation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


RUNTIME_LAUNCHER_PROTOCOL = 2
PLUGIN_ID = "straw-boss@straw-boss"
ALLOWED_SCRIPTS = {
    "dispatch-coworker.py",
    "report-progress.py",
    "report-task-status.py",
    "send-dispatch-message.py",
}


def _command_json(command: list[str]) -> Any | None:
    executable = shutil.which(command[0])
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def _claude_plugin_root() -> Path | None:
    payload = _command_json(["claude", "plugin", "list", "--json"])
    if not isinstance(payload, list):
        return None
    for plugin in payload:
        if (
            isinstance(plugin, dict)
            and plugin.get("id") == PLUGIN_ID
            and plugin.get("enabled") is not False
            and isinstance(plugin.get("installPath"), str)
        ):
            return Path(plugin["installPath"])
    return None


def _codex_plugin_root() -> Path | None:
    payload = _command_json(["codex", "plugin", "list", "--json"])
    if not isinstance(payload, dict) or not isinstance(payload.get("installed"), list):
        return None
    for plugin in payload["installed"]:
        source = plugin.get("source") if isinstance(plugin, dict) else None
        if (
            isinstance(plugin, dict)
            and plugin.get("pluginId") == PLUGIN_ID
            and plugin.get("enabled") is not False
            and isinstance(source, dict)
            and isinstance(source.get("path"), str)
        ):
            return Path(source["path"])
    return None


def _installed_plugin_roots(origin_root: Path) -> tuple[Path | None, Path | None]:
    normalized = origin_root.expanduser().as_posix()
    if "/.codex/plugins/cache/" in normalized:
        return _codex_plugin_root(), _claude_plugin_root()
    return _claude_plugin_root(), _codex_plugin_root()


def resolve_script(origin_root: Path, script_name: str, prefer_installed: bool) -> Path:
    if script_name not in ALLOWED_SCRIPTS:
        raise ValueError(f"unsupported Straw Boss script {script_name!r}")

    override = os.environ.get("STRAW_BOSS_PLUGIN_ROOT")
    roots: list[Path] = []
    if override:
        roots.append(Path(override).expanduser())
    if prefer_installed:
        for candidate in _installed_plugin_roots(origin_root):
            if candidate is not None:
                roots.append(candidate)
    roots.append(origin_root)

    for root in roots:
        scripts_dir = (root.expanduser().resolve() / "scripts").resolve()
        script = (scripts_dir / script_name).resolve()
        if script.is_relative_to(scripts_dir) and script.is_file():
            return script
    raise ValueError(
        f"could not resolve {script_name!r} from the current Straw Boss installation "
        f"or origin {str(origin_root)!r}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin-root", required=True, type=Path)
    parser.add_argument("--prefer-installed", action="store_true")
    parser.add_argument("--script", required=True)
    parser.add_argument("script_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    script_args = list(args.script_args)
    if script_args[:1] == ["--"]:
        script_args = script_args[1:]
    try:
        script = resolve_script(args.origin_root, args.script, args.prefer_installed)
        os.execvp("uv", ["uv", "run", "--script", str(script), *script_args])
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
