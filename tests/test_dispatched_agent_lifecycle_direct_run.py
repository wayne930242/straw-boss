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

# A -k pattern no test name contains, so unittest.main() starts a run and
# selects nothing from it.
NO_TEST_MATCHES = "__no_test_matches_this_pattern__"


class DispatchedAgentLifecycleDirectRunTests(unittest.TestCase):
    """Each split lifecycle test file still carries `unittest.main()`
    boilerplate, so `python3 tests/<file>.py` from repo root must keep
    working -- the same invocation mode the pre-split file supported.

    Only that invocation mode is checked here. The tests inside those files
    are already exercised by this suite, so running them again cost 115s of
    the 297s suite to prove nothing the suite had not proven."""

    def test_each_split_lifecycle_file_runs_directly_from_repo_root(self) -> None:
        for name in DIRECT_RUN_FILES:
            with self.subTest(file=name):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "tests" / name), "-k", NO_TEST_MATCHES],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                # unittest.main() reports the run on stderr even when the
                # filter selects nothing. A file that fails to import from
                # repo root, or that lost its unittest.main() call, produces
                # no such line. The exit status carries less: unittest returns
                # 5 for an empty run on Python 3.12+ and 0 before it, and a
                # file with no unittest.main() at all also exits 0.
                self.assertIn(
                    "Ran 0 tests",
                    result.stderr,
                    f"direct run of {name} failed:\n{result.stdout}{result.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
