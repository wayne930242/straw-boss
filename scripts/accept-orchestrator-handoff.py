#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Accept one orchestrator ownership handoff from its receiving Herdr pane."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dispatch_session import validate_current_process_in_pane
from dispatch_state import dump_json, load_json, straw_boss_root


VALID_COORDINATION_GRAPHS = {
    "single-loop",
    "sub-agent fan-out/fan-in",
    "orchestrator-worker",
}
MAX_OWNER_CHARS = 120
MAX_ANCHOR_CHARS = 800


def route_evidence(
    owner: str, coordination_graph: str, reality_anchor: str
) -> dict[str, str]:
    owner = owner.strip()
    reality_anchor = reality_anchor.strip()
    if not owner:
        raise ValueError("boss-say routing requires an owning skill")
    if len(owner) > MAX_OWNER_CHARS:
        raise ValueError(f"owning skill exceeds {MAX_OWNER_CHARS} characters")
    if coordination_graph not in VALID_COORDINATION_GRAPHS:
        raise ValueError(f"unsupported coordination graph {coordination_graph!r}")
    if not reality_anchor:
        raise ValueError("boss-say routing requires a reality anchor")
    if len(reality_anchor) > MAX_ANCHOR_CHARS:
        raise ValueError(f"reality anchor exceeds {MAX_ANCHOR_CHARS} characters")
    return {
        "routed_through": "boss-say",
        "owner": owner,
        "coordination_graph": coordination_graph,
        "reality_anchor": reality_anchor,
        "routed_at": datetime.now(timezone.utc).isoformat(),
    }


def accept(
    handoff_path: str,
    *,
    owner: str,
    coordination_graph: str,
    reality_anchor: str,
) -> dict[str, object]:
    path = Path(handoff_path).resolve()
    handoff_root = (straw_boss_root() / "handoffs").resolve()
    if not path.is_relative_to(handoff_root):
        raise ValueError(f"handoff path must be inside {handoff_root}")
    if not path.is_file():
        raise ValueError(f"no orchestrator handoff at {path}")
    payload = load_json(path)
    expected = payload.get("receiver_pane_id")
    if not isinstance(expected, str) or not expected:
        raise ValueError("handoff has no receiving pane")
    if not isinstance(payload.get("scope"), str) or not payload["scope"]:
        raise ValueError("handoff has no transferred scope")
    route = route_evidence(owner, coordination_graph, reality_anchor)
    current = os.environ.get("HERDR_PANE_ID")
    if not isinstance(current, str) or not current:
        raise ValueError("receiving orchestrator has no HERDR_PANE_ID")
    if current != expected:
        raise ValueError(
            f"handoff receiver is {expected!r}, not current pane {current!r}"
        )
    validate_current_process_in_pane(current)
    if payload.get("status") == "accepted":
        if payload.get("accepted_by_pane") != current:
            raise ValueError("handoff was accepted by a different pane")
        return payload
    if payload.get("status") != "offered":
        raise ValueError(f"handoff is {payload.get('status')!r}, not offered")
    payload["status"] = "accepted"
    payload["accepted_by_pane"] = current
    payload["accepted_at"] = datetime.now(timezone.utc).isoformat()
    payload["route"] = route
    dump_json(path, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--handoff-path", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument(
        "--coordination-graph",
        required=True,
        choices=sorted(VALID_COORDINATION_GRAPHS),
    )
    parser.add_argument("--reality-anchor", required=True)
    args = parser.parse_args()
    try:
        result = accept(
            args.handoff_path,
            owner=args.owner,
            coordination_graph=args.coordination_graph,
            reality_anchor=args.reality_anchor,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"accepted": True, "scope": result["scope"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
