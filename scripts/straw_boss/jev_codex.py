"""Codex copied-history adapter for the shared Jev policy.

This is a replay boundary, not a live PreCompact history-replacement API.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from straw_boss.jev_storage import pair_bytes

CALLS = {"custom_tool_call", "function_call"}
RESULTS = {"custom_tool_call_output", "function_call_output"}


def configuration() -> tuple[dict, dict]:
    base = Path(__file__).resolve().parents[2] / "config"
    return tuple(json.loads((base / name).read_text()) for name in (
        "jev-criteria.json", "jev-policy.json"))


def history_from_rows(rows: list[dict]) -> list[dict]:
    history = []
    for row in rows:
        if row["type"] == "compacted" and row["payload"].get("replacement_history") is not None:
            history = copy.deepcopy(row["payload"]["replacement_history"])
        elif row["type"] == "response_item":
            history.append(copy.deepcopy(row["payload"]))
    return history


def result_text(output: object) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and all(
        isinstance(part, dict) and part.get("type") in {"input_text", "input_image"} for part in output
    ):
        return "".join(part.get("text", "") for part in output if part["type"] == "input_text")
    raise ValueError("unsupported-result-content")


def normalized_pair(call: dict, result: dict) -> tuple[dict, dict]:
    raw = call.get("arguments", call.get("input", ""))
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        value = {"input": raw}
    if not isinstance(value, dict):
        value = {"input": value}
    return ({"tool_use_id": call["call_id"], "tool": call["name"], "input": value},
            {"tool_use_id": result["call_id"], "text": result_text(result["output"]),
             "isError": bool(result.get("is_error", False))})


def collect_pairs(history: list[dict]) -> list[tuple[int, int]]:
    calls, results = {}, {}
    for index, item in enumerate(history):
        target = calls if item["type"] in CALLS else results if item["type"] in RESULTS else None
        if target is not None:
            if item["call_id"] in target:
                raise ValueError("duplicate-call-id")
            target[item["call_id"]] = index
    if results.keys() - calls.keys():
        raise ValueError("orphan-result")
    pairs = [(index, results[key]) for key, index in calls.items() if key in results]
    if any(a >= b for a, b in pairs):
        raise ValueError("result-before-call")
    return pairs


def locked_indices(history: list[dict], recent: int) -> set[int]:
    # A Codex logical message includes the following tool exchange until the
    # next text message. Preserve the first message and latest six messages.
    messages = [i for i, item in enumerate(history) if item["type"] == "message"]
    locked = {0} if history else set()
    if messages:
        locked.add(messages[0])
        if recent:
            locked.update(range(messages[-min(recent, len(messages))], len(history)))
    if recent:
        locked.update(range(max(0, len(history) - recent), len(history)))
    return locked


def lock_reason(call: dict, a: int, b: int, locked: set[int], policy: dict) -> str | None:
    raw = call.get("arguments", call.get("input", ""))
    try:
        raw = json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        pass
    encoded = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))
    if any(re.search(pattern, encoded, re.ASCII) for pattern in policy["protected_input_patterns"]):
        return "governing_source"
    return "pinned" if a in locked or b in locked else None


def prune(history: list[dict], scores: dict[str, dict], policy: dict) -> tuple[list[dict], list[dict]]:
    """Apply validated pair scores; rule-locked pairs require no score."""
    if not isinstance(scores, dict):
        raise ValueError("missing-or-invalid-jev-score")
    candidate = copy.deepcopy(history)
    locked = locked_indices(history, policy["preserve_recent_messages"])
    removed, decisions = set(), []
    for number, (a, b) in enumerate(collect_pairs(history), 1):
        call, result = history[a], history[b]
        reason = lock_reason(call, a, b, locked, policy)
        score = None if reason else scores.get(call["call_id"])
        if not reason and (not isinstance(score, dict) or any(
            isinstance(score.get(key), bool) or not isinstance(score.get(key), (int, float))
            or not 0 <= score[key] <= 1
            for key in ("keepCall", "keepResult")
        )):
            raise ValueError("missing-or-invalid-jev-score")
        action = "keep"
        if not reason and score["keepResult"] < policy["keep_threshold"]:
            action = "drop_result" if score["keepCall"] >= policy["keep_threshold"] else "drop_call"
        before_call, before_result = normalized_pair(call, result)
        if action == "drop_call":
            removed.update((a, b))
        elif action == "drop_result":
            text = before_result["text"]
            head = policy["truncate_head_chars"]
            if len(text) > head:
                note = f"\n[fast-jev-compaction truncated {len(text) - head} chars of this tool result; original saved in the recovery record]"
                short = text[:head] + note
                if isinstance(result["output"], str):
                    candidate[b]["output"] = short
                else:
                    blocks, remaining, inserted = [], head, False
                    for block in result["output"]:
                        if block["type"] != "input_text":
                            blocks.append(copy.deepcopy(block))
                        elif remaining:
                            prefix = block.get("text", "")[:remaining]
                            remaining -= len(prefix)
                            blocks.append({"type": "input_text", "text": prefix})
                            if remaining == 0:
                                blocks[-1]["text"] += note
                                inserted = True
                    if not inserted:
                        blocks.append({"type": "input_text", "text": note})
                    candidate[b]["output"] = blocks
        after = normalized_pair(candidate[a], candidate[b])
        decisions.append({
            "id": f"t{number}", "call_id": call["call_id"], "tool": call["name"],
            "keepCall": score["keepCall"] if score else None,
            "keepResult": score["keepResult"] if score else None,
            "action": action, "reason": reason or {"keep": "kept", "drop_call": "call_dropped", "drop_result": "result_dropped"}[action],
            "lock_reason": reason, "score_source": "locked-not-judged" if reason else "jev",
            "bytes_before": pair_bytes(before_call, before_result),
            "bytes_after": 0 if action == "drop_call" else pair_bytes(*after),
            "original_indices": [a, b],
            "original_content": [call, result] if action != "keep" else None,
        })
    return [item for i, item in enumerate(candidate) if i not in removed], decisions


def measurement(before: dict, after: dict, policy: dict) -> dict:
    """Only backend input counts with explicit zero-cache evidence pass."""
    for usage in (before, after):
        if (type(usage.get("input_tokens")) is not int or usage["input_tokens"] <= 0
                or type(usage.get("cached_input_tokens")) is not int
                or usage["cached_input_tokens"] != 0):
            raise ValueError("backend-zero-cache-measurement-required")
    ratio = (before["input_tokens"] - after["input_tokens"]) / before["input_tokens"]
    return {"tokens_before": before["input_tokens"], "tokens_after": after["input_tokens"],
            "reduction_pct": ratio * 100, "gate_reduction_pct": ratio * 100,
            "decision": "apply" if ratio >= policy["min_reduction_ratio"] else "fallback",
            "fallback_reason": None if ratio >= policy["min_reduction_ratio"] else "under-reduction-gate"}


def replacement_rows(rows: list[dict], history: list[dict]) -> list[dict]:
    """Fresh serialized items; no host handles or old-parent references added."""
    result = copy.deepcopy(rows)
    result.append({"timestamp": rows[-1]["timestamp"], "type": "compacted",
                   "payload": {"message": "", "replacement_history": copy.deepcopy(history)}})
    for i, row in enumerate(result):
        row["ordinal"] = i
    return result
