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
