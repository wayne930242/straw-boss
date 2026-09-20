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


# A guard against an author accidentally pasting a credential's actual value
# into a hazard note, not a guarantee against every way one could be hidden in
# text. Deliberately broad within each shape it checks -- an `=` assignment
# with any identifier-shaped key, or a bare token/base64 blob -- because a
# false positive there costs the author one visible edit, which is cheaper
# than a worker never seeing a hazard note that was silently shortened to
# hide a false negative. The `Key: value` colon form is checked too, but only
# for a key that names something credential-shaped: an unrestricted colon
# check flags ordinary prose (e.g. "claim it only after the worker reports
# it: claim-resource.py wait ...") far too often to be a usable guard.
_CREDENTIAL_ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*=\s*\S{6,}")
_CREDENTIAL_KEYWORD_LABEL_RE = re.compile(
    r"(?i)\b(?:password|passwd|pwd|secret|token|key|credentials?|"
    r"api[_ -]?key|access[_ -]?key|account[_ -]?key|auth[_ -]?token|"
    r"private[_ -]?key|client[_ -]?secret|connection[_ -]?string)\b\s*:\s*\S{6,}"
)
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
        or _CREDENTIAL_KEYWORD_LABEL_RE.search(text)
        or _CREDENTIAL_PREFIX_TOKEN_RE.search(text)
    ):
        return True
    return any(
        not _IDENTIFIER_SHAPED_RE.match(match.group(0))
        for match in _BASE64_BLOB_RE.finditer(text)
    )


def _reject_if_it_quotes_a_credential(
    *, config_path: Path, app_name: str, field: str, text: str
) -> None:
    """Fails loudly when `text` looks like it quotes a credential's value.

    Applied to every free-text field that reaches a dispatch contract -- the
    app-level `note` and each `localFiles[].note` -- so the check is where the
    fact is authored, not where it is rendered: a dispatch that refuses to be
    written is visible, a hazard note silently shortened at render time is
    not. The message never repeats the matched text, since that would defeat
    the check it is enforcing.
    """
    if _quotes_a_credential(text):
        raise ValueError(
            f"{config_path}: app {app_name!r} field {field!r} looks like it quotes a "
            "credential value -- rewrite it in apps.json to describe the risk, not the value"
        )


def resolve_app_hazards(repo_root: Path, app_name: str) -> AppHazards | None:
    """This app's `note` and `localFiles` hazards, for a dispatch contract.

    Returns `None` when apps.json doesn't exist, has no entry for this app, or
    the entry carries no hazard facts -- a dispatch must not fail just because
    hazard notes are absent. `localFiles[].note` is meant to be a risk
    description, not the file's actual contents, but `apps.json` is
    hand-maintained, so every free-text field is checked here, at read time,
    for a note that looks like it quotes a credential's value -- see
    `_reject_if_it_quotes_a_credential`. `dispatch.state.render_app_hazards_section`
    renders whatever this function returns faithfully; it does not sanitize.
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
    if note:
        _reject_if_it_quotes_a_credential(
            config_path=config.path, app_name=app_name, field="note", text=note
        )

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
            if risk:
                _reject_if_it_quotes_a_credential(
                    config_path=config.path,
                    app_name=app_name,
                    field=f"localFiles[{path!r}].note",
                    text=risk,
                )
            local_files.append(
                LocalFileHazard(
                    path=path,
                    sensitive=bool(entry.get("sensitive", False)),
                    risk=risk,
                )
            )

    hazards = AppHazards(note=note, local_files=tuple(local_files))
    return hazards if hazards else None
