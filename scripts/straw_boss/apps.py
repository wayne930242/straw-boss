"""集中讀取專案 apps 設定，並相容舊版目錄。"""

from __future__ import annotations

import json
import re
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
    """只在新路徑不存在時回退；保留未知欄位與實際來源。

    Every free-text hazard field in the config -- each app's `note` and each
    `localFiles[].note` -- is checked here, at the single point where
    `apps.json` becomes data, for a value that looks like it quotes a
    credential (see `_reject_if_it_quotes_a_credential`). Every reader of this
    config (`resolve_app_hazards`, `copy-local-files.py`'s `configured_app`)
    goes through this function first, so none of them need to repeat it.
    """
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
        _reject_credential_shaped_notes(path, payload["apps"])
        return AppsConfig(path=path, payload=payload, legacy=path == legacy)
    raise AppsConfigMissing(f"apps config is missing: {canonical} (legacy: {legacy})")


# A guard against an author accidentally pasting a credential's actual value
# into a hazard note, not a general secret scanner and not a guarantee against
# every way one could be hidden in text. Precision is the priority here, not
# recall: this check's only failure mode is blocking a dispatch outright, and
# a false positive there teaches authors to phrase hazard notes around the
# scanner, which costs more safety than the shape it would have caught. Only
# two high-precision shapes are checked: an `=` assignment with any
# identifier-shaped key, and a bare token/base64 blob. A `Key: value` colon
# label (e.g. "private key: managed by Ansible") is deliberately NOT checked
# -- that phrasing is exactly how a `localFiles` note is meant to name which
# secret a file holds, so a keyword-gated colon rule fires on the field's own
# job. The tradeoff: a value written as `password: hunter2example` passes.
_CREDENTIAL_ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*=\s*\S{6,}")
# A bare token, checked two ways: a short list of well-known credential
# prefixes (a GitHub/GitLab/Anthropic/OpenAI/AWS/Google/Slack token, or a
# JWT's `eyJ...`), and a long unbroken run of base64-alphabet characters with
# no path or kebab-case separators. `/` and `-` are deliberately left out of
# the base64-blob shape -- this file's real hazard notes routinely spell out
# repo-relative paths (`wdmis/backend/waydosoft...`) and multi-word resource
# names (`port--moldplan-frontend-2--...`), which would otherwise be flagged
# on every dispatch to those apps. That trades recall (a real secret that
# happens to be all path- or kebab-shaped slips through) for a check that
# stays usable against real notes instead of misfiring on ordinary prose.
_CREDENTIAL_PREFIX_TOKEN_RE = re.compile(
    r"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|glpat-|sk-ant-|sk-proj-|sk-live-|"
    r"sk-test-|AKIA|ASIA|AIza|eyJ|xox[abpr]-)[A-Za-z0-9_-]{8,}"
)
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+]{24,}={0,2}")
_IDENTIFIER_SHAPED_RE = re.compile(r"^[A-Z0-9]+={0,2}$")


def _quotes_a_credential(text: str) -> bool:
    if (
        _CREDENTIAL_ASSIGNMENT_RE.search(text)
        or _CREDENTIAL_PREFIX_TOKEN_RE.search(text)
    ):
        return True
    return any(
        not _IDENTIFIER_SHAPED_RE.match(match.group(0))
        for match in _BASE64_BLOB_RE.finditer(text)
    )


def _reject_if_it_quotes_a_credential(
    *, config_path: Path, app_name: object, field: str, text: str
) -> None:
    """Fails loudly when `text` looks like it quotes a credential's value.

    Applied to every free-text field that reaches a reader -- every app's
    `note` and every `localFiles[].note` -- at `read_apps_config`, the single
    point where `apps.json` becomes data, so every reader inherits the same
    guard. A dispatch or copy that refuses to run is visible; a hazard note
    silently shortened at render time is not. The message never repeats the
    matched text, since that would defeat the check it is enforcing.
    """
    if _quotes_a_credential(text):
        raise ValueError(
            f"{config_path}: app {app_name!r} field {field!r} looks like it quotes a "
            "credential value -- rewrite it in apps.json to describe the risk, not the value"
        )


def _reject_credential_shaped_notes(config_path: Path, apps: list[Any]) -> None:
    for item in apps:
        if not isinstance(item, dict):
            continue
        app_name = item.get("name")
        note = item.get("note")
        if isinstance(note, str) and note.strip():
            _reject_if_it_quotes_a_credential(
                config_path=config_path, app_name=app_name, field="note", text=note
            )
        raw_local_files = item.get("localFiles")
        if not isinstance(raw_local_files, list):
            continue
        for entry in raw_local_files:
            if not isinstance(entry, dict):
                continue
            risk = entry.get("note")
            if not (isinstance(risk, str) and risk.strip()):
                continue
            path = entry.get("path")
            field = f"localFiles[{path!r}].note" if isinstance(path, str) else "localFiles[].note"
            _reject_if_it_quotes_a_credential(
                config_path=config_path, app_name=app_name, field=field, text=risk
            )


def resolve_app_hazards(repo_root: Path, app_name: str) -> AppHazards | None:
    """This app's `note` and `localFiles` hazards, for a dispatch contract.

    Returns `None` when apps.json doesn't exist, or has no entry for this
    app -- a dispatch must not fail just because hazard notes are absent.
    Raises when more than one entry shares this name: that is a config
    defect, and folding it into the "no entry" case would silently drop the
    app's hazards along with the error. `read_apps_config` already rejects
    any free-text field that looks like it quotes a credential's value, so
    this function does not repeat that check.
    `dispatch.state.render_app_hazards_section` renders whatever this
    function returns faithfully; it does not sanitize.
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
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(
            f"{config.path}: app {app_name!r} is configured {len(matches)} times; "
            "apps.json must contain at most one entry per app name"
        )
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
            risk = risk if isinstance(risk, str) and risk.strip() else None
            local_files.append(
                LocalFileHazard(
                    path=path,
                    sensitive=bool(entry.get("sensitive", False)),
                    risk=risk,
                )
            )

    hazards = AppHazards(note=note, local_files=tuple(local_files))
    return hazards if hazards else None
