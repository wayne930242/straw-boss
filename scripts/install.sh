#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly REPO_ROOT
readonly PLUGIN_ID="straw-boss@straw-boss"
readonly MARKETPLACE_NAME="straw-boss"
readonly CLAUDE_REMOTE_SOURCE="https://github.com/wayne930242/straw-boss"
readonly CODEX_REMOTE_SOURCE="wayne930242/straw-boss"
INSTALL_SOURCE_MODE="remote"

usage() {
  cat <<'EOF'
Usage: bash scripts/install.sh [--local]

Install Straw Boss from its GitHub marketplace source by default.
Use --local only for development against this source checkout.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)
      INSTALL_SOURCE_MODE="local"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done
readonly INSTALL_SOURCE_MODE

manifest_version() {
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["version"])' "$1"
}

claude_marketplace_descriptor() {
  claude plugin marketplace list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload:
    if item.get("name") == "straw-boss":
        source = item.get("source") or "present"
        path = item.get("path") or item.get("url") or ""
        print(source + "\t" + path)
        break
'
}

configure_claude_marketplace() {
  local source descriptor marketplace_kind marketplace_path
  if [[ "${INSTALL_SOURCE_MODE}" == "local" ]]; then
    source="${REPO_ROOT}"
  else
    source="${CLAUDE_REMOTE_SOURCE}"
  fi

  descriptor="$(claude_marketplace_descriptor)"
  IFS=$'\t' read -r marketplace_kind marketplace_path <<<"${descriptor}"
  if [[ -z "${marketplace_kind}" ]]; then
    claude plugin marketplace add "${source}" --scope user
  elif [[ "${INSTALL_SOURCE_MODE}" == "remote" && "${marketplace_kind}" == "git" && ( "${marketplace_path}" == "${CLAUDE_REMOTE_SOURCE}" || "${marketplace_path}" == "${CLAUDE_REMOTE_SOURCE}.git" ) ]]; then
    claude plugin marketplace update "${MARKETPLACE_NAME}"
  elif [[ "${INSTALL_SOURCE_MODE}" == "local" && "${marketplace_kind}" == "directory" && "${marketplace_path}" == "${REPO_ROOT}" ]]; then
    return
  else
    claude plugin marketplace remove "${MARKETPLACE_NAME}"
    claude plugin marketplace add "${source}" --scope user
  fi
}

claude_plugin_version() {
  claude plugin list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload:
    if (
        item.get("id") == "straw-boss@straw-boss"
        and item.get("scope") == "user"
    ):
        print(item.get("version") or "")
        break
'
}

claude_plugin_state() {
  claude plugin list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print("present" if any(
    item.get("id") == "straw-boss@straw-boss"
    and item.get("scope") == "user"
    for item in payload
) else "absent")
'
}

codex_marketplace_descriptor() {
  codex plugin marketplace list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
for item in payload.get("marketplaces", []):
    if item.get("name") == "straw-boss":
        source = item.get("marketplaceSource", {})
        kind = source.get("sourceType") or "local"
        path = source.get("source") or ""
        print(kind + "\t" + path)
        break
'
}

configure_codex_marketplace() {
  local descriptor marketplace_kind marketplace_path
  descriptor="$(codex_marketplace_descriptor)"
  IFS=$'\t' read -r marketplace_kind marketplace_path <<<"${descriptor}"

  if [[ -z "${marketplace_kind}" ]]; then
    if [[ "${INSTALL_SOURCE_MODE}" == "local" ]]; then
      codex plugin marketplace add "${REPO_ROOT}" --json
    else
      codex plugin marketplace add "${CODEX_REMOTE_SOURCE}" --ref main --json
    fi
  elif [[ "${INSTALL_SOURCE_MODE}" == "remote" && "${marketplace_kind}" == "git" && ( "${marketplace_path}" == "${CODEX_REMOTE_SOURCE}" || "${marketplace_path}" == "${CLAUDE_REMOTE_SOURCE}" || "${marketplace_path}" == "${CLAUDE_REMOTE_SOURCE}.git" ) ]]; then
    codex plugin marketplace upgrade "${MARKETPLACE_NAME}" --json
  elif [[ "${INSTALL_SOURCE_MODE}" == "local" && "${marketplace_kind}" == "local" && "${marketplace_path}" == "${REPO_ROOT}" ]]; then
    return
  else
    codex plugin marketplace remove "${MARKETPLACE_NAME}" --json
    if [[ "${INSTALL_SOURCE_MODE}" == "local" ]]; then
      codex plugin marketplace add "${REPO_ROOT}" --json
    else
      codex plugin marketplace add "${CODEX_REMOTE_SOURCE}" --ref main --json
    fi
  fi
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

codex_plugin_state() {
  codex plugin list --json | python3 -c '
import json, sys
payload = json.load(sys.stdin)
print("present" if any(
    item.get("pluginId") == "straw-boss@straw-boss"
    for item in payload.get("installed", [])
) else "absent")
'
}

install_claude() {
  configure_claude_marketplace

  local installed_version plugin_state
  plugin_state="$(claude_plugin_state)"
  case "${plugin_state}" in
    present)
      claude plugin uninstall "${PLUGIN_ID}" --scope user --keep-data
      claude plugin install "${PLUGIN_ID}" --scope user
      ;;
    absent)
      claude plugin install "${PLUGIN_ID}" --scope user
      ;;
    *)
      echo "error: unexpected Claude plugin state: ${plugin_state}" >&2
      return 1
      ;;
  esac

  installed_version="$(claude_plugin_version)"
  if [[ "${installed_version}" != "${VERSION}" ]]; then
    echo "error: Claude reports Straw Boss ${installed_version:-<missing>}; expected ${VERSION}" >&2
    return 1
  fi
  echo "Installed straw-boss ${VERSION} for Claude Code."
}

install_codex() {
  local installed_version plugin_state
  configure_codex_marketplace

  plugin_state="$(codex_plugin_state)"
  case "${plugin_state}" in
    present)
      codex plugin remove "${PLUGIN_ID}" --json
      codex plugin add "${PLUGIN_ID}" --json
      ;;
    absent)
      codex plugin add "${PLUGIN_ID}" --json
      ;;
    *)
      echo "error: unexpected Codex plugin state: ${plugin_state}" >&2
      return 1
      ;;
  esac

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

if [[ "${INSTALL_SOURCE_MODE}" == "local" ]]; then
  echo "Using local marketplace source: ${REPO_ROOT}"
else
  echo "Using GitHub marketplace source: ${CLAUDE_REMOTE_SOURCE}"
fi

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
