from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class DispatchWorktreeLifecycleTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repo_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.repo_dir.cleanup)
        self.repo = Path(self.repo_dir.name) / "repo"
        self.worktree = Path(self.repo_dir.name) / "worktree"
        self.repo.mkdir()
        self.run_git(self.repo, "init", "--quiet")
        self.run_git(self.repo, "config", "user.email", "test@example.com")
        self.run_git(self.repo, "config", "user.name", "Straw Boss Test")
        (self.repo / "README.md").write_text("fixture\n")
        self.run_git(self.repo, "add", ".")
        self.run_git(self.repo, "commit", "--quiet", "-m", "fixture")
        self.run_git(
            self.repo, "worktree", "add", "--quiet", "-b", "dispatch-demo", str(self.worktree)
        )

    def run_git(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
        )

    def write_worktree_dispatch(self, repo_root: Path, slug: str) -> Path:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            slug,
            "--task",
            "Implement the requested slice and verify it.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(repo_root),
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
            "--main-agent-pane-id",
            "main-pane",
            "--main-agent-session-id",
            "main-session",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["instruction_path"])

    def test_write_records_linked_worktree_path_and_branch(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.worktree, "worktree-demo")
        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(
            Path(instruction["worktree_path"]).resolve(), self.worktree.resolve()
        )
        self.assertEqual(instruction["worktree_branch"], "dispatch-demo")

    def test_write_leaves_worktree_fields_null_for_the_main_checkout(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.repo, "main-checkout")
        instruction = json.loads(instruction_path.read_text())
        self.assertIsNone(instruction["worktree_path"])
        self.assertIsNone(instruction["worktree_branch"])

    def test_wrap_up_names_pane_close_and_worktree_remove_as_remaining_steps(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.worktree, "worktree-wrap")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        status_path.write_text(json.dumps({"status": "done", "note": "shipped"}) + "\n")

        result = self.run_script("wrap-up-task.py", "--app", "api", "--slug", "worktree-wrap")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        archived_path = payload["archived_path"]
        steps = payload["remaining_steps"]

        self.assertTrue(
            any("close-worker-pane.py" in step and archived_path in step for step in steps)
        )
        self.assertIn(f"git worktree remove {self.worktree.resolve()}", steps)

    def test_wrap_up_omits_worktree_remove_for_the_main_checkout(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.repo, "main-checkout-wrap")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        status_path.write_text(json.dumps({"status": "done", "note": "shipped"}) + "\n")

        result = self.run_script(
            "wrap-up-task.py", "--app", "api", "--slug", "main-checkout-wrap"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        steps = json.loads(result.stdout)["remaining_steps"]

        self.assertTrue(any("close-worker-pane.py" in step for step in steps))
        self.assertFalse(any("git worktree remove" in step for step in steps))


if __name__ == "__main__":
    unittest.main()
