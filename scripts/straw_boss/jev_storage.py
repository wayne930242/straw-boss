"""Private recovery snapshots and one benchmark row per compaction attempt."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager
from pathlib import Path

from .jev_private import private_file, private_read, private_replace, private_unlink, root


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def criteria_version(criteria: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(criteria)).hexdigest()


def pair_bytes(call: dict | None, result: dict | None) -> int:
    """UTF-8 compact JSON of one invocation and one visible result, each once."""
    if call is None and result is None:
        return 0
    pair = []
    if call is not None:
        pair.append({key: call[key] for key in ("tool_use_id", "tool", "input")})
    if result is not None:
        pair.append({"tool_use_id": result["tool_use_id"], "text": result["text"],
                     "isError": bool(result.get("isError"))})
    return len(canonical(pair))


def private_write(path: Path, data: dict) -> None:
    private_replace(path, json.dumps(data, ensure_ascii=False))


@contextmanager
def benchmark_lock():
    with private_file(root() / "benchmark.lock", os.O_WRONLY | os.O_CREAT, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def pending(session: str) -> dict | None:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", session):
        raise ValueError("invalid-session-id")
    path = root() / "pending" / f"{session}.json"
    try:
        return json.loads(private_read(path))
    except FileNotFoundError:
        return None


def observe(data: dict) -> dict:
    session = data["session_id"]
    outstanding = pending(session)
    if not outstanding or outstanding["run_id"] != data["run_id"]:
        return {"observed": False}
    with benchmark_lock():
        path = root() / "benchmark.jsonl"
        rows = [json.loads(line) for line in private_read(path).splitlines()]
        for record in rows:
            if record["run_id"] != data["run_id"]:
                continue
            measurement = record.setdefault("measurement", {})
            measurement["actual_session_tokens_after"] = data["actual_session_tokens_after"]
            before = measurement.get("live_input_tokens_before")
            after = data["actual_session_tokens_after"]
            ratio = 100 * (before - after) / before if before else None
            required = record.get("policy", {}).get("min_reduction_ratio", 0.1) * 100
            verified = ratio is not None and ratio >= required
            record["application"] = {"status": "verified" if verified else "unverified-no-net-reduction",
                                     "actual_reduction_pct": ratio, "observation": data}
            if record.get("decision") == "apply":
                record["outcome"] = "applied" if verified else None
            recovery = Path(record["recovery_path"])
            snapshot = json.loads(private_read(recovery))
            snapshot["record"] = record
            private_write(recovery, snapshot)
        private_replace(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    private_write(root() / "observations" / f"{session}.json", data)
    private_unlink(root() / "pending" / f"{session}.json")
    return {"observed": True}


def persist(data: dict) -> dict:
    record = data["record"]
    run = record["run_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", run):
        raise ValueError("invalid-run-id")
    directory = root()
    recovery = directory / "runs" / f"{run}.json"
    original = data["original_messages"]
    candidate = data.get("candidate_messages") or original
    calls = []
    results = {tool["tool_use_id"]: (index, tool)
               for index, message in enumerate(original) for tool in message.get("toolResults", [])}
    for index, message in enumerate(original):
        for tool in message.get("toolUses", []):
            if tool["tool_use_id"] in results:
                calls.append((index, tool, *results[tool["tool_use_id"]]))
    after_calls = {tool["tool_use_id"]: tool for message in candidate for tool in message.get("toolUses", [])}
    after_results = {tool["tool_use_id"]: tool for message in candidate for tool in message.get("toolResults", [])}
    for decision in record["decisions"]:
        index = int(decision["id"][1:]) - 1
        call_index, call, result_index, result = calls[index]
        call_id = call["tool_use_id"]
        pair = [call, result]
        decision.update(call_id=call_id, bytes_before=pair_bytes(call, result),
                        bytes_after=pair_bytes(after_calls.get(call_id), after_results.get(call_id)),
                        original_indices=[call_index, result_index])
        if decision.get("reason") in ("pinned", "governing_source"):
            decision["lock_reason"] = decision["reason"]
            decision["score_source"] = "locked-not-judged"
        else:
            decision["score_source"] = "jev"
        if decision["action"] != "keep":
            decision.update(original_content=pair, original_indices=[call_index, result_index])
    record["byte_measurement"] = "UTF-8 canonical JSON of invocation id/tool/input and one result id/text/isError; excludes duplicated host metadata."
    # Store whole originals as well as modified-pair data. This preserves
    # message order and handles for exact reconstruction and failure analysis.
    record["recovery_path"] = str(recovery)
    private_write(recovery, {"record": record, "original_messages": data["original_messages"],
                             "candidate_messages": data.get("candidate_messages")})
    benchmark = directory / "benchmark.jsonl"
    with benchmark_lock():
        with private_file(benchmark, os.O_WRONLY | os.O_CREAT | os.O_APPEND, "a") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
            file.flush()
            os.fsync(file.fileno())
    if session := record.get("session_id"):
        pending(session)  # Validate before using it as a path.
        private_write(directory / "pending" / f"{session}.json", {"run_id": run})
    return {"recovery_path": str(recovery), "benchmark_path": str(benchmark)}
