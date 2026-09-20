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
from straw_boss.jev_private import private_copy_directory, private_new_file
from straw_boss.jev_storage import criteria_version


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
    record = benchmark_record(args.output_dir.name, criteria, policy, decisions,
        source={"history_path": str(args.history.resolve()),
                "history_sha256": hashlib.sha256(source_bytes).hexdigest()}, request_metrics=[])
    record["jev"]["score_source"] = "supplied-replay-scores; no Jev requests made by this command"
    if failure:
        record["fallback_reason"] = failure
    record["recovery_path"] = str(args.output_dir.absolute() / "recovery.json")
    recovery = {
        "original_history": original, "decisions": decisions,
        "criteria_version": criteria_version(criteria), "policy_version": criteria_version(policy),
        "application": {"status": "candidate-only", "live_application_supported": False},
        "qualitative_outcome": {"status": "not-assessed"},
        "record": record,
    }
    with private_copy_directory(args.output_dir) as directory:
        for name, value in (("candidate.json", candidate), ("recovery.json", recovery),
                            ("benchmark.jsonl", record)):
            with private_new_file(directory, name) as file:
                json.dump(value, file, ensure_ascii=False)
                if name.endswith(".jsonl"):
                    file.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
