#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""提供技能使用的 apps 設定讀取介面。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from straw_boss.apps import AppsConfigMissing, read_apps_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Read project apps configuration.")
    parser.add_argument("--repo-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = read_apps_config(args.repo_root)
    except AppsConfigMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "path": str(result.path), "legacy": result.legacy, "config": result.payload,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
