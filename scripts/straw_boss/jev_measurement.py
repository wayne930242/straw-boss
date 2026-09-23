"""Backend token counts for native Claude message blocks, never serialized logs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def native_messages(messages: list[dict]) -> list[dict]:
    # Claude Code stores one turn as several same-role entries, and streamed
    # tool execution can record a result between calls of one turn. Rebuild
    # API turns: merge same-role runs, then place each result in the user
    # message right after the call's turn, ahead of that message's text.
    turns: list[dict] = []
    results: list[dict] = []
    for message in messages:
        blocks = []
        if message.get("text"):
            blocks.append({"type": "text", "text": message["text"]})
        for tool in message.get("toolUses", []):
            blocks.append({"type": "tool_use", "id": tool["tool_use_id"],
                           "name": tool["tool"], "input": tool["input"]})
        results += [{"type": "tool_result", "tool_use_id": tool["tool_use_id"],
                     "content": tool["text"], "is_error": bool(tool.get("isError"))}
                    for tool in message.get("toolResults", [])]
        if not blocks and not message.get("toolResults"):
            continue
        if not turns or turns[-1]["role"] != message["role"]:
            turns.append({"role": message["role"], "content": [], "results": []})
        turns[-1]["content"] += blocks
    owner = {block["id"]: index for index, turn in enumerate(turns)
             for block in turn["content"] if block["type"] == "tool_use"}
    for block in results:
        if block["tool_use_id"] not in owner:
            raise ValueError("orphan-tool-result")
        turns[owner[block["tool_use_id"]] + 1]["results"].append(block)
    result = [{"role": turn["role"], "content": turn.pop("results") + turn["content"]}
              for turn in turns]
    result = [turn for turn in result if turn["content"]]
    if not result:
        raise ValueError("empty-countable-history")
    return result


def credential_headers() -> dict[str, str]:
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    if base_url and urlparse(base_url).hostname != "api.anthropic.com":
        raise ValueError("backend-count-custom-provider-unsupported")
    if any(os.environ.get(name) for name in (
        "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY")):
        raise ValueError("backend-count-custom-provider-unsupported")
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        return {**headers, "x-api-key": key}
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        config = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude")))
        path = config / ".credentials.json"
        data = None
        if path.is_file():
            data = json.loads(path.read_text())
        elif sys.platform == "darwin":
            found = subprocess.run(
                ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True, text=True, timeout=10,
            )
            if found.returncode == 0:
                data = json.loads(found.stdout)
        if isinstance(data, dict):
            token = (data.get("claudeAiOauth") or {}).get("accessToken")
    if not token:
        raise ValueError("backend-count-credential-unavailable")
    return {**headers, "authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"}


def count_tokens(model: str, messages: list[dict], headers: dict) -> int:
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps({"model": model.removesuffix("[1m]"), "messages": native_messages(messages)}).encode(),
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            value = json.load(response).get("input_tokens")
    except urllib.error.HTTPError as error:
        raise ValueError(f"backend-count-http-{error.code}") from None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("backend-count-invalid-input-tokens")
    return value


def measure(data: dict) -> dict:
    headers = credential_headers()
    with ThreadPoolExecutor(max_workers=2) as pool:
        before, after = list(pool.map(
            lambda messages: count_tokens(data["model"], messages, headers),
            [data["before"], data["after"]],
        ))
    # Use the larger observed input as the gate denominator, including the
    # session's system/tool prefix when its last backend response reports it.
    live = data.get("live_input_tokens")
    denominator = max(before, live if isinstance(live, int) and live > 0 else before)
    return {
        "tokens_before": before, "tokens_after": after,
        "reduction_pct": 100 * (before - after) / before,
        "gate_reduction_pct": 100 * (before - after) / denominator,
        "measurement": {
            "source": "anthropic-messages-count-tokens",
            "scope": "native-text-and-tool-blocks",
            "model": data["model"], "live_input_tokens_before": live,
            "gate_denominator_tokens": denominator,
            "tokens_after_semantics": "candidate-history-backend-count",
            "actual_session_tokens_after": None,
            "limitations": "Hidden reasoning, images, and fixed system/tool schemas are outside the counted message view; live session input is the conservative gate denominator.",
        },
    }
