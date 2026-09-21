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

    def write_worktree_dispatch(
        self, repo_root: Path, slug: str, *extra_args: str
    ) -> Path:
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
            *extra_args,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["instruction_path"])

    def wrap_up_steps(self, instruction_path: Path) -> tuple[str, list[str]]:
        stem = instruction_path.name.removesuffix(".json")
        instruction_path.with_name(f"{stem}.status.json").write_text(
            json.dumps({"status": "done", "note": "shipped"}) + "\n"
        )
        result = self.run_script(
            "wrap-up-task.py", "--app", "api", "--slug", stem.removeprefix("api--")
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        return payload["archived_path"], payload["remaining_steps"]

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
        instruction_path = self.write_worktree_dispatch(
            self.worktree, "worktree-wrap", "--owns-worktree"
        )
        self.assertIs(json.loads(instruction_path.read_text())["worktree_owned"], True)
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        archived_path, steps = self.wrap_up_steps(instruction_path)

        self.assertTrue(
            any("close-worker-pane.py" in step and archived_path in step for step in steps)
        )
        self.assertIn(f"git worktree remove {self.worktree.resolve()}", steps)

    def test_wrap_up_keeps_a_linked_worktree_the_dispatch_only_ran_in(self) -> None:
        # A permanent linked worktree (a long-lived branch checkout next to the
        # main one) is where the app lives, not something created for this
        # task -- recording where the dispatch ran must not turn into advice
        # to delete it.
        instruction_path = self.write_worktree_dispatch(self.worktree, "worktree-resident")
        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(
            Path(instruction["worktree_path"]).resolve(), self.worktree.resolve()
        )
        self.assertIs(instruction["worktree_owned"], False)
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        _, steps = self.wrap_up_steps(instruction_path)

        self.assertFalse(any("git worktree remove" in step for step in steps))

    def test_wrap_up_keeps_the_worktree_of_a_record_without_an_ownership_claim(self) -> None:
        # Instructions written before ownership was recorded carry only
        # worktree_path, which never distinguished a task worktree from a
        # permanent one.
        instruction_path = self.write_worktree_dispatch(self.worktree, "worktree-legacy")
        instruction = json.loads(instruction_path.read_text())
        del instruction["worktree_owned"]
        instruction_path.write_text(json.dumps(instruction))
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        _, steps = self.wrap_up_steps(instruction_path)

        self.assertFalse(any("git worktree remove" in step for step in steps))

    def test_owning_a_worktree_requires_repo_root_to_be_a_linked_worktree(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            "not-a-worktree",
            "--task",
            "Implement the requested slice and verify it.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(self.repo),
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
            "--main-agent-pane-id",
            "main-pane",
            "--main-agent-session-id",
            "main-session",
            "--owns-worktree",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--owns-worktree needs --repo-root to be a linked git worktree", result.stderr)
        dispatch_dir = self.home / ".straw-boss" / "dispatch"
        self.assertEqual(list(dispatch_dir.iterdir()), [])
        self.assertEqual(
            sorted(path.name for path in (self.home / ".straw-boss").iterdir()), ["dispatch"]
        )

    def test_wrap_up_omits_the_pane_close_once_close_worker_pane_recorded_it(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.repo, "pane-closed")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")
        instruction = json.loads(instruction_path.read_text())
        instruction["herdr_pane_closed_at"] = "2026-09-21T13:00:00+00:00"
        instruction_path.write_text(json.dumps(instruction))

        _, steps = self.wrap_up_steps(instruction_path)

        self.assertFalse(any("close-worker-pane.py" in step for step in steps))

    def test_coworker_sharing_parents_worktree_records_no_worktree_fields(self) -> None:
        parent_path = self.write_worktree_dispatch(self.worktree, "worktree-parent")
        self.set_worker_endpoint(parent_path, pane="worker-pane", session="worker-session")

        result = self.write_coworker(parent_path, repo_root=self.worktree)

        self.assertEqual(result.returncode, 0, result.stderr)
        child = json.loads(Path(json.loads(result.stdout)["instruction_path"]).read_text())
        self.assertIsNone(child["worktree_path"])
        self.assertIsNone(child["worktree_branch"])

    def test_a_coworker_cannot_claim_its_parents_worktree(self) -> None:
        parent_path = self.write_worktree_dispatch(
            self.worktree, "worktree-owner", "--owns-worktree"
        )
        self.set_worker_endpoint(parent_path, pane="worker-pane", session="worker-session")

        result = self.write_coworker(
            parent_path, repo_root=self.worktree, extra_args=("--owns-worktree",)
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("a coworker shares its parent's worktree", result.stderr)

    def test_detached_head_worktree_records_path_without_a_branch(self) -> None:
        self.run_git(self.repo, "worktree", "add", "--quiet", "--detach", str(self.worktree) + "-detached")
        instruction_path = self.write_worktree_dispatch(
            Path(str(self.worktree) + "-detached"), "worktree-detached"
        )
        instruction = json.loads(instruction_path.read_text())
        self.assertIsNotNone(instruction["worktree_path"])
        self.assertIsNone(instruction["worktree_branch"])

    def test_wrap_up_omits_worktree_remove_for_the_main_checkout(self) -> None:
        instruction_path = self.write_worktree_dispatch(self.repo, "main-checkout-wrap")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        _, steps = self.wrap_up_steps(instruction_path)

        self.assertTrue(any("close-worker-pane.py" in step for step in steps))
        self.assertFalse(any("git worktree remove" in step for step in steps))


if __name__ == "__main__":
    unittest.main()
