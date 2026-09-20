#!/usr/bin/env python3
"""Opt-in candidate creation in a new directory, using explicit replay scores."""
from __future__ import annotations

import argparse
import json
import os
import hashlib
from pathlib import Path

from straw_boss.jev_codex import configuration, prune
from straw_boss.jev_codex_benchmark import benchmark_record
from straw_boss.jev_storage import criteria_version


def write_copy(path: Path, value: object) -> None:
    # The command owns a newly created private output directory. Exclusive
    # creation keeps repeated invocations from overwriting any prior evidence.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as file:
        json.dump(value, file, ensure_ascii=False)
        file.flush()
        os.fsync(file.fileno())


def main() -> int:
    if os.environ.get("STRAW_BOSS_JEV") != "1" or not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    criteria, policy = configuration()
    source_bytes = args.history.read_bytes()
    original = json.loads(source_bytes)
    score_file = json.loads(args.scores.read_text())
    failure = None
    try:
        if score_file["criteria_version"] != criteria_version(criteria):
            raise ValueError("criteria-version-mismatch")
        candidate, decisions = prune(original, score_file["scores"], policy)
    except (ValueError, KeyError, TypeError) as error:
        candidate, decisions = original, []
        failure = str(error) if isinstance(error, ValueError) else "invalid-replay-scores"
    args.output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_copy(args.output_dir / "candidate.json", candidate)
    record = benchmark_record(args.output_dir.name, criteria, policy, decisions,
        source={"history_path": str(args.history.resolve()),
                "history_sha256": hashlib.sha256(source_bytes).hexdigest()}, request_metrics=[])
    record["jev"]["score_source"] = "supplied-replay-scores; no Jev requests made by this command"
    if failure:
        record["fallback_reason"] = failure
    record["recovery_path"] = str((args.output_dir / "recovery.json").resolve())
    write_copy(args.output_dir / "recovery.json", {
        "original_history": original, "decisions": decisions,
        "criteria_version": criteria_version(criteria), "policy_version": criteria_version(policy),
        "application": {"status": "candidate-only", "live_application_supported": False},
        "qualitative_outcome": {"status": "not-assessed"},
        "record": record,
    })
    fd = os.open(args.output_dir / "benchmark.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
