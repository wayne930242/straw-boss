"""集中讀取專案 apps 設定，並相容舊版目錄。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class AppsConfigMissing(ValueError):
    """新舊位置都沒有設定。"""


@dataclass(frozen=True)
class AppsConfig:
    path: Path
    payload: dict[str, Any]
    legacy: bool


@dataclass(frozen=True)
class LocalFileHazard:
    path: str
    sensitive: bool
    risk: str | None


@dataclass(frozen=True)
class AppHazards:
    note: str | None
    local_files: tuple[LocalFileHazard, ...]

    def __bool__(self) -> bool:
        return bool(self.note) or bool(self.local_files)


def read_apps_config(repo_root: Path) -> AppsConfig:
    """只在新路徑不存在時回退；保留未知欄位與實際來源。"""
    repo_root = repo_root.resolve()
    canonical = repo_root / ".straw-boss" / "apps.json"
    legacy = repo_root / ".claude" / "straw-boss" / "apps.json"
    for path in (canonical, legacy):
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError(f"apps config cannot be accessed: {path}: {exc}") from exc
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"apps config cannot be read: {path}: {exc}") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("apps"), list):
            raise ValueError(f"apps config must contain an apps array: {path}")
        return AppsConfig(path=path, payload=payload, legacy=path == legacy)
    raise AppsConfigMissing(f"apps config is missing: {canonical} (legacy: {legacy})")


def resolve_app_hazards(repo_root: Path, app_name: str) -> AppHazards | None:
    """This app's `note` and `localFiles` hazards, for a dispatch contract.

    Returns `None` when apps.json doesn't exist, has no entry for this app, or
    the entry carries no hazard facts -- a dispatch must not fail just because
    hazard notes are absent. `localFiles[].note` is already a risk description,
    never the file's actual contents, so rendering it verbatim cannot leak a
    secret value even for a `sensitive: true` entry.
    """
    try:
        config = read_apps_config(repo_root)
    except AppsConfigMissing:
        return None
    matches = [
        item
        for item in config.payload.get("apps", [])
        if isinstance(item, dict) and item.get("name") == app_name
    ]
    if len(matches) != 1:
        return None
    app = matches[0]

    note = app.get("note")
    note = note if isinstance(note, str) and note.strip() else None

    local_files: list[LocalFileHazard] = []
    raw_local_files = app.get("localFiles")
    if isinstance(raw_local_files, list):
        for entry in raw_local_files:
            if not isinstance(entry, dict):
                continue
            path = entry.get("path")
            if not isinstance(path, str) or not path.strip():
                continue
            risk = entry.get("note")
            local_files.append(
                LocalFileHazard(
                    path=path,
                    sensitive=bool(entry.get("sensitive", False)),
                    risk=risk if isinstance(risk, str) and risk.strip() else None,
                )
            )

    hazards = AppHazards(note=note, local_files=tuple(local_files))
    return hazards if hazards else None
