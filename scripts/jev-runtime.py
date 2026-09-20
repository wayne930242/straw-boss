#!/usr/bin/env python3
"""Host operations for the opt-in Claude function hook; secrets stay in process."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from straw_boss.jev_measurement import measure
from straw_boss.jev_storage import criteria_version, observe, pending, persist


def main() -> int:
    # Missing key is normal and has no output or filesystem effects.
    if os.environ.get("STRAW_BOSS_JEV") != "1" or not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return 0
    try:
        command = sys.argv[1]
        data = json.load(sys.stdin)
        if command == "config":
            base = Path(__file__).resolve().parents[1] / "config"
            criteria = json.loads((base / "jev-criteria.json").read_text())
            policy = json.loads((base / "jev-policy.json").read_text())
            answer = {"pending": pending(data["session_id"]) if data.get("session_id") else None,
                      "policy_version": criteria_version(policy), "criteria": criteria, "criteria_version": criteria_version(criteria),
                      "policy": policy}
        elif command == "measure":
            answer = measure(data)
        elif command == "persist":
            answer = persist(data)
        elif command == "observe":
            answer = observe(data)
        else:
            raise ValueError("unknown-operation")
        print(json.dumps(answer, ensure_ascii=False))
        return 0
    except Exception as error:
        # Error classes/codes suffice; HTTP bodies and credentials stay private.
        reason = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(json.dumps({"error": reason}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
