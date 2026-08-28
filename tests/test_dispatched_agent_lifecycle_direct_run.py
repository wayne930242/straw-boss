from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DIRECT_RUN_FILES = [
    "test_dispatched_agent_lifecycle_contract.py",
    "test_dispatched_agent_naming_and_coworker.py",
    "test_dispatched_agent_launch_and_delivery.py",
    "test_dispatched_agent_status_and_recovery.py",
]


class DispatchedAgentLifecycleDirectRunTests(unittest.TestCase):
    """Each split lifecycle test file still carries `unittest.main()`
    boilerplate, so `python3 tests/<file>.py` from repo root must keep
    working -- the same invocation mode the pre-split file supported."""

    def test_each_split_lifecycle_file_runs_directly_from_repo_root(self) -> None:
        for name in DIRECT_RUN_FILES:
            with self.subTest(file=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tests" / name)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"direct run of {name} failed:\n{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
