#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly REPO_ROOT
readonly PLUGIN_ID="straw-boss@straw-boss"
readonly MARKETPLACE_NAME="straw-boss"

manifest_version() {
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$1"
}

claude_marketplace_present() {
  claude plugin marketplace list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
raise SystemExit(0 if any(item.get("name") == "straw-boss" for item in payload) else 1)
'
}

claude_plugin_version() {
  claude plugin list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload:
    if item.get("id") == "straw-boss@straw-boss":
        print(item.get("version") or "")
        break
'
}

codex_marketplace_kind() {
  codex plugin marketplace list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload.get("marketplaces", []):
    if item.get("name") == "straw-boss":
        print(item.get("marketplaceSource", {}).get("sourceType") or "local")
        break
'
}

codex_plugin_version() {
  codex plugin list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload.get("installed", []):
    if item.get("pluginId") == "straw-boss@straw-boss":
        print(item.get("version") or "")
        break
'
}

install_claude() {
  if claude_marketplace_present; then
    claude plugin marketplace update "${MARKETPLACE_NAME}"
  else
    claude plugin marketplace add "${REPO_ROOT}" --scope user
  fi

  local installed_version
  installed_version="$(claude_plugin_version)"
  if [[ -n "${installed_version}" ]]; then
    claude plugin update "${PLUGIN_ID}" --scope user
  else
    claude plugin install "${PLUGIN_ID}" --scope user
  fi

  installed_version="$(claude_plugin_version)"
  if [[ "${installed_version}" != "${VERSION}" ]]; then
    echo "error: Claude reports Straw Boss ${installed_version:-<missing>}; expected ${VERSION}" >&2
    return 1
  fi
  echo "Installed straw-boss ${VERSION} for Claude Code."
}

install_codex() {
  local marketplace_kind installed_version
  marketplace_kind="$(codex_marketplace_kind)"
  if [[ -z "${marketplace_kind}" ]]; then
    codex plugin marketplace add "${REPO_ROOT}" --json
  elif [[ "${marketplace_kind}" == "git" ]]; then
    codex plugin marketplace upgrade "${MARKETPLACE_NAME}" --json
  fi

  installed_version="$(codex_plugin_version)"
  if [[ -z "${installed_version}" ]]; then
    codex plugin add "${PLUGIN_ID}" --json
  elif [[ "${installed_version}" != "${VERSION}" ]]; then
    codex plugin remove "${PLUGIN_ID}" --json
    codex plugin add "${PLUGIN_ID}" --json
  fi

  installed_version="$(codex_plugin_version)"
  if [[ "${installed_version}" != "${VERSION}" ]]; then
    echo "error: Codex reports Straw Boss ${installed_version:-<missing>}; expected ${VERSION}" >&2
    return 1
  fi
  echo "Installed straw-boss ${VERSION} for Codex CLI."
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required to validate plugin metadata" >&2
  exit 1
fi

CLAUDE_VERSION="$(manifest_version "${REPO_ROOT}/.claude-plugin/plugin.json")"
readonly CLAUDE_VERSION
CODEX_VERSION="$(manifest_version "${REPO_ROOT}/.codex-plugin/plugin.json")"
readonly CODEX_VERSION
if [[ "${CLAUDE_VERSION}" != "${CODEX_VERSION}" ]]; then
  echo "error: plugin manifest versions differ: Claude ${CLAUDE_VERSION}, Codex ${CODEX_VERSION}" >&2
  exit 1
fi
readonly VERSION="${CLAUDE_VERSION}"

installed_any=0
if command -v claude >/dev/null 2>&1; then
  install_claude
  installed_any=1
else
  echo "Skipping Claude Code: claude was not found."
fi

if command -v codex >/dev/null 2>&1; then
  install_codex
  installed_any=1
else
  echo "Skipping Codex CLI: codex was not found."
fi

if [[ "${installed_any}" -eq 0 ]]; then
  echo "error: neither claude nor codex was found" >&2
  exit 1
fi

echo "Restart active agent sessions to load the updated plugin."
