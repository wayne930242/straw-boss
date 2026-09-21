from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class ReportProgressRefTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def progress_log_path(self, instruction_path: Path) -> Path:
        stem = instruction_path.name.removesuffix(".json")
        return instruction_path.with_name(f"{stem}.progress.jsonl")

    def test_progress_accepts_repeatable_ref_and_records_it(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")

        result = self.run_script(
            "report-progress.py",
            "--instruction-path",
            str(instruction_path),
            "--note",
            "made progress",
            "--ref",
            "artifact://one",
            "--ref",
            "artifact://two",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.progress_log_path(instruction_path).read_text().splitlines()
        entry = json.loads(lines[-1])
        self.assertEqual(entry["note"], "made progress")
        self.assertEqual(entry["refs"], ["artifact://one", "artifact://two"])

    def test_progress_without_ref_omits_refs_key(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")

        result = self.run_script(
            "report-progress.py",
            "--instruction-path",
            str(instruction_path),
            "--note",
            "no evidence yet",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.progress_log_path(instruction_path).read_text().splitlines()
        entry = json.loads(lines[-1])
        self.assertNotIn("refs", entry)

    def test_progress_rejects_empty_ref(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")

        result = self.run_script(
            "report-progress.py",
            "--instruction-path",
            str(instruction_path),
            "--note",
            "made progress",
            "--ref",
            "   ",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-empty", result.stderr)

    def test_progress_records_what_a_wait_is_waiting_on(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")

        result = self.run_script(
            "report-progress.py",
            "--instruction-path",
            str(instruction_path),
            "--note",
            "CI running",
            "--waiting-on",
            "Monitor on pipeline #1",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads(self.progress_log_path(instruction_path).read_text().splitlines()[-1])
        self.assertEqual(entry["waiting_on"], "Monitor on pipeline #1")

        empty = self.run_script(
            "report-progress.py",
            "--instruction-path",
            str(instruction_path),
            "--note",
            "CI running",
            "--waiting-on",
            "  ",
        )
        self.assertNotEqual(empty.returncode, 0)
        self.assertIn("non-empty", empty.stderr)


if __name__ == "__main__":
    unittest.main()
