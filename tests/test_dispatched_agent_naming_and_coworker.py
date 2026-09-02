from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import (
    ROOT,
    DispatchedAgentLifecycleFixture,
)


class DispatchedAgentNamingAndCoworkerTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def test_launcher_names_the_coordinator_tab_before_splitting_a_worker_pane(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        rename = ["tab", "rename", "tab-1", "api-coordinator"]
        self.assertIn(rename, calls)
        self.assertLess(
            calls.index(rename),
            next(i for i, call in enumerate(calls) if call[:2] == ["pane", "split"]),
        )

    def test_coordinator_tab_naming_failure_warns_and_still_dispatches(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_FAIL_TAB_RENAME": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["launched"])
        self.assertIn("coordinator tab", output["warning"])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(
            len([call for call in calls if call[:2] == ["tab", "rename"]]),
            2,
        )
        self.assertTrue(any(call[:2] == ["agent", "prompt"] for call in calls))

    def test_launcher_derives_a_worker_name_from_app_when_name_is_omitted(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertEqual(start[2], "api-worker")
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["name"], "api-worker")
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        rename = next(call for call in calls if call[:2] == ["pane", "rename"])
        prompt_index = next(i for i, call in enumerate(calls) if call[:2] == ["agent", "prompt"])
        rename_index = calls.index(rename)
        self.assertEqual(rename, ["pane", "rename", "worker-pane", "api-worker"])
        self.assertLess(rename_index, prompt_index)

    def test_launcher_avoids_a_derived_name_collision_with_a_live_agent(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_AGENT_LIST": json.dumps([{"name": "api-worker"}]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertEqual(start[2], "api-worker-2")

    def test_launcher_retries_a_derived_name_that_a_concurrent_sibling_just_claimed(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_NAME_TAKEN": json.dumps(["api-worker"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual([call[2] for call in starts], ["api-worker", "api-worker-2"])
        self.assertIn(
            ["pane", "rename", "worker-pane", "api-worker-2"], calls
        )
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["name"], "api-worker-2")

    def test_launcher_retries_past_two_concurrent_siblings_without_double_suffixing(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_NAME_TAKEN": json.dumps(["api-worker", "api-worker-2"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual(
            [call[2] for call in starts], ["api-worker", "api-worker-2", "api-worker-3"]
        )

    def test_launcher_retries_forward_past_a_populated_snapshot_after_a_race(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_AGENT_LIST": json.dumps(
                    [
                        {"name": "api-worker"},
                        {"name": "api-worker-2"},
                        {"name": "api-worker-3"},
                        {"name": "api-worker-4"},
                    ]
                ),
                "HERDR_NAME_TAKEN": json.dumps(["api-worker-5"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual([call[2] for call in starts], ["api-worker-5", "api-worker-6"])

    def test_launcher_does_not_retry_a_name_taken_error_for_an_explicit_name(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_NAME_TAKEN": json.dumps(["api-worker"]),
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent_name_taken", result.stderr)

    def test_worker_pane_naming_failure_warns_and_still_delivers(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_FAIL_PANE_RENAME": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["launched"])
        self.assertIn("could not be named", output["warning"])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        renames = [call for call in calls if call[:2] == ["pane", "rename"]]
        self.assertEqual(len(renames), 2)
        self.assertTrue(any(call[:2] == ["agent", "prompt"] for call in calls))

    def test_launcher_prefers_an_explicit_role_over_app_for_the_worker_name(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", role="database")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertEqual(start[2], "database-worker")

    def test_multiple_plan_tasks_sharing_an_app_get_distinct_role_names(self) -> None:
        fake_bin, capture = self.install_fake_herdr()
        expected = {
            "plan-db": ("database", "database-worker"),
            "plan-fe": ("frontend", "frontend-worker"),
            "plan-api": ("api", "api-worker"),
        }
        started_names = []
        for slug, (role, _expected_name) in expected.items():
            instruction_path, _ = self.write_dispatch("claude", slug=slug, role=role)
            instruction = json.loads(instruction_path.read_text())
            capture.write_text("")
            result = self.run_script(
                "launch-dispatched-agent.py",
                "--instruction-path",
                str(instruction_path),
                extra_env={
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                    "HERDR_CAPTURE": str(capture),
                    "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in capture.read_text().splitlines()]
            start = next(call for call in calls if call[:2] == ["agent", "start"])
            started_names.append(start[2])

        self.assertEqual(
            started_names, [expected_name for _role, expected_name in expected.values()]
        )
        self.assertEqual(len(set(started_names)), len(started_names))

    def test_launcher_names_a_still_unnamed_coordinator_pane_on_first_dispatch(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_UNNAMED_PANES": json.dumps(["main-pane"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertIn(["agent", "rename", "main-pane", "api-coordinator"], calls)

    def test_launcher_does_not_rename_an_already_named_coordinator_pane(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["agent", "rename"] for call in calls))

    def test_launcher_still_reports_success_when_coordinator_naming_fails(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_AGENT_GET_ERROR_CODES": json.dumps({"main-pane": "agent_not_found"}),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["agent", "rename"] for call in calls))
        receipt_path = instruction_path.with_name("api--contract-claude.launch.json")
        self.assertTrue(receipt_path.is_file())

    def test_launcher_names_the_coordinator_after_the_worker_is_confirmed(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(instruction_path),
            "--name",
            "api-worker",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_LIVE_SESSION": str(instruction["session_id"]),
                "HERDR_UNNAMED_PANES": json.dumps(["main-pane"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        rename_index = next(
            i for i, call in enumerate(calls) if call[:2] == ["agent", "rename"]
        )
        prompt_index = next(
            i for i, call in enumerate(calls) if call[:2] == ["agent", "prompt"]
        )
        self.assertGreater(rename_index, prompt_index)
        self.assertEqual(calls[rename_index], ["agent", "rename", "main-pane", "api-coordinator"])

    def test_launcher_derives_a_coworker_name_and_never_renames_its_parent(self) -> None:
        parent_path, _ = self.write_dispatch("claude", main_agent_kind="codex")
        self.set_worker_endpoint(parent_path)
        written = self.write_coworker(parent_path)
        self.assertEqual(written.returncode, 0, written.stderr)
        child_path = Path(json.loads(written.stdout)["instruction_path"])
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "launch-dispatched-agent.py",
            "--instruction-path",
            str(child_path),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_WORKER_PANE_ID": "coworker-pane",
                "HERDR_UNNAMED_PANES": json.dumps(["worker-pane"]),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        start = next(call for call in calls if call[:2] == ["agent", "start"])
        self.assertEqual(start[2], "api-coworker")
        self.assertFalse(any(call[:2] == ["agent", "rename"] for call in calls))

    def test_worker_can_launch_one_review_only_coworker_in_its_worktree(self) -> None:
        parent_path, _ = self.write_dispatch("claude", main_agent_kind="codex")
        parent = self.set_worker_endpoint(parent_path)

        result = self.write_coworker(parent_path)

        self.assertEqual(result.returncode, 0, result.stderr)
        child_path = Path(json.loads(result.stdout)["instruction_path"])
        child = json.loads(child_path.read_text())
        contract = Path(str(child["contract_path"])).read_text()
        self.assertEqual(child["parent_instruction_path"], str(parent_path.resolve()))
        self.assertEqual(child["repo_root"], parent["repo_root"])
        self.assertEqual(child["main_agent_herdr_pane_id"], "worker-pane")
        self.assertEqual(child["main_agent_session_id"], "worker-session")
        self.assertEqual(child["main_agent_kind"], "claude")
        self.assertEqual(child["root_main_agent_herdr_pane_id"], "main-pane")
        self.assertIsNone(child["root_main_agent_session_id"])
        self.assertEqual(
            child["root_main_agent_herdr_terminal_id"], "terminal-main-pane"
        )
        self.assertEqual(child["root_main_agent_kind"], "codex")
        self.assertEqual(child["coworker_writable_paths"], [])
        self.assertIn("review-only", contract)
        self.assertIn("one direct coworker", contract)

        second = self.write_coworker(parent_path, slug="coworker-second")
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("already has coworker instruction", second.stderr)

    def test_coworker_contract_names_normalized_writable_paths(self) -> None:
        parent_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(parent_path)

        result = self.write_coworker(
            parent_path,
            slug="coworker-writing",
            writable_paths=("docs/review.md", "docs/review.md"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        child_path = Path(json.loads(result.stdout)["instruction_path"])
        child = json.loads(child_path.read_text())
        contract = Path(str(child["contract_path"])).read_text()
        self.assertEqual(child["coworker_writable_paths"], ["docs/review.md"])
        self.assertIn("`docs/review.md`", contract)
        self.assertNotIn("review-only", contract)

    def test_coworker_rejects_an_escaping_writable_path_and_nested_parent(self) -> None:
        parent_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(parent_path)

        escaping = self.write_coworker(
            parent_path, slug="coworker-escape", writable_paths=("../outside",)
        )
        self.assertNotEqual(escaping.returncode, 0)
        self.assertIn("writable path", escaping.stderr)
        self.assertFalse(
            parent_path.with_name("api--coworker-escape.json").exists()
        )

        parent = json.loads(parent_path.read_text())
        parent["parent_instruction_path"] = "/already/a/coworker.json"
        parent_path.write_text(json.dumps(parent, indent=2) + "\n")
        nested = self.write_coworker(parent_path, slug="coworker-nested")
        self.assertNotEqual(nested.returncode, 0)
        self.assertIn("cannot launch another coworker", nested.stderr)

    def test_coworker_terminal_status_notifies_parent_and_root_coordinator(self) -> None:
        parent_path, _ = self.write_dispatch("claude", main_agent_kind="codex")
        self.set_worker_endpoint(parent_path)
        written = self.write_coworker(parent_path)
        self.assertEqual(written.returncode, 0, written.stderr)
        child_path = Path(json.loads(written.stdout)["instruction_path"])
        self.set_worker_endpoint(child_path, pane="coworker-pane", session="coworker-session")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(child_path),
            "--status",
            "done",
            "--note",
            "Review complete",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_ID": "coworker-pane",
                "HERDR_SESSIONS": json.dumps(
                    {
                        "coworker-pane": "coworker-session",
                        "worker-pane": "worker-session",
                    }
                ),
                "HERDR_AGENT_KINDS": json.dumps(
                    {
                        "coworker-pane": "codex",
                        "worker-pane": "claude",
                        "main-pane": "codex",
                    }
                ),
                "HERDR_TERMINAL_IDS": json.dumps(
                    {
                        "coworker-pane": "terminal-coworker-pane",
                        "worker-pane": "terminal-worker-pane",
                        "main-pane": "terminal-main-pane",
                    }
                ),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual([call[2] for call in prompts], ["worker-pane", "main-pane"])
        self.assertIn("done — Review complete", prompts[0][3])
        self.assertIn("done — Review complete", prompts[1][3])

    def test_coworker_terminal_status_still_attempts_root_after_parent_failure(self) -> None:
        parent_path, _ = self.write_dispatch("claude", main_agent_kind="codex")
        self.set_worker_endpoint(parent_path)
        written = self.write_coworker(parent_path)
        self.assertEqual(written.returncode, 0, written.stderr)
        child_path = Path(json.loads(written.stdout)["instruction_path"])
        self.set_worker_endpoint(child_path, pane="coworker-pane", session="coworker-session")
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(child_path),
            "--status",
            "failed",
            "--note",
            "Review failed",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_ID": "coworker-pane",
                "HERDR_FAIL_PROMPT_PANE": "worker-pane",
                "HERDR_SESSIONS": json.dumps(
                    {
                        "coworker-pane": "coworker-session",
                        "worker-pane": "worker-session",
                    }
                ),
                "HERDR_AGENT_KINDS": json.dumps(
                    {
                        "coworker-pane": "codex",
                        "worker-pane": "claude",
                        "main-pane": "codex",
                    }
                ),
                "HERDR_TERMINAL_IDS": json.dumps(
                    {
                        "coworker-pane": "terminal-coworker-pane",
                        "worker-pane": "terminal-worker-pane",
                        "main-pane": "terminal-main-pane",
                    }
                ),
            },
        )

        self.assertNotEqual(result.returncode, 0)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual([call[2] for call in prompts], ["worker-pane", "main-pane"])
        status = json.loads(child_path.with_suffix(".status.json").read_text())
        self.assertEqual(status["status"], "failed")

    def test_coworker_facade_runs_write_launch_and_confirm(self) -> None:
        parent_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(parent_path)
        fake_bin, capture = self.install_fake_herdr()
        result = self.run_script(
            "dispatch-coworker.py",
            "--parent-instruction-path",
            str(parent_path),
            "--slug",
            "second-opinion",
            "--task",
            "Review the interface with the user.",
            "--name",
            "second-opinion",
            "--agent-kind",
            "codex",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_ID": "worker-pane",
                "HERDR_WORKER_PANE_ID": "coworker-pane",
                "HERDR_SESSIONS": json.dumps(
                    {
                        "worker-pane": "worker-session",
                        "coworker-pane": "coworker-session",
                        "main-pane": "main-session",
                    }
                ),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["pane_id"], "coworker-pane")
        self.assertEqual(output["tab_id"], "tab-1")
        self.assertNotIn("session_id", output)
        instruction = json.loads(Path(output["instruction_path"]).read_text())
        self.assertEqual(instruction["status"], "in-progress")

    def test_coworker_facade_does_not_cut_off_the_bounded_launcher(self) -> None:
        scripts_dir = str(ROOT / "scripts")
        with mock.patch.object(sys, "path", [scripts_dir, *sys.path]):
            namespace = runpy.run_path(
                str(ROOT / "scripts" / "dispatch-coworker.py")
            )

        def finish_only_without_outer_timeout(
            command: list[str], **kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            timeout = kwargs.get("timeout")
            if timeout is not None:
                raise subprocess.TimeoutExpired(command, timeout)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout='{"launched": true}\n',
                stderr="",
            )

        with mock.patch.object(
            namespace["subprocess"],
            "run",
            side_effect=finish_only_without_outer_timeout,
        ):
            result = namespace["run_public_script"](
                "launch-dispatched-agent.py", []
            )

        self.assertTrue(result["launched"])

    def test_bringing_coworker_skill_stays_short_and_uses_the_facade(self) -> None:
        skill = (ROOT / "skills" / "bringing-coworker" / "SKILL.md").read_text()

        self.assertLessEqual(len(skill.splitlines()), 55)
        self.assertIn("dispatch-coworker.py", skill)
        self.assertIn("review-only", skill)
        self.assertIn("user", skill.lower())
        self.assertNotIn("herdr tab create", skill)


if __name__ == "__main__":
    unittest.main()
