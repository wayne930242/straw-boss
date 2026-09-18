from __future__ import annotations

import json
import os
import runpy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import (
    ROOT,
    DispatchedAgentLifecycleFixture,
)


class OrchestratorHandoffTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    ROUTE_ARGS = (
        "--owner",
        "shipping-task",
        "--coordination-graph",
        "single-loop",
        "--reality-anchor",
        "testing at the executable lifecycle boundary",
    )

    def test_durable_json_write_replaces_a_complete_temporary_file(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            from straw_boss.dispatch import state as dispatch_state
        finally:
            sys.path.pop(0)
        target = self.home / "record.json"
        with (
            mock.patch.object(Path, "write_text", autospec=True) as write_text,
            mock.patch.object(Path, "replace", autospec=True) as replace,
        ):
            dispatch_state.dump_json(target, {"status": "offered"})

        temporary = write_text.call_args.args[0]
        self.assertNotEqual(temporary, target)
        replace.assert_called_once_with(temporary, target)

    def test_continuity_omits_empty_fields_and_maps_retained_scope_to_exclusions(
        self,
    ) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            module = runpy.run_path(str(ROOT / "scripts" / "handoff-orchestrator.py"))
        finally:
            sys.path.pop(0)
        continuity_payload = module["continuity_payload"]
        payload = continuity_payload(
            SimpleNamespace(
                goal="Goal",
                scope="Transferred scope",
                state="Confirmed state",
                next_action="Start",
                decision=[],
                term=[],
                evidence=[],
                exclude=[],
                retains=["Release coordination"],
            )
        )

        self.assertEqual(
            payload,
            {
                "goal": "Goal",
                "scope": "Transferred scope",
                "state": "Confirmed state",
                "next": "Start",
                "exclusions": ["Release coordination"],
            },
        )
        with self.assertRaisesRegex(ValueError, "compact it to 1600"):
            continuity_payload(
                SimpleNamespace(
                    goal="x" * 1600,
                    scope="Transferred scope",
                    state="Confirmed state",
                    next_action="Start",
                    decision=[],
                    term=[],
                    evidence=[],
                    exclude=[],
                    retains=[],
                )
            )

    def handoff_args(self, *, approved: bool = True, retains: tuple[str, ...] = ()) -> list[str]:
        args = [
            "--source-pane-id",
            "main-pane",
            "--cwd",
            str(ROOT),
            "--slug",
            "api",
            "--agent-kind",
            "claude",
            "--goal",
            "Deliver the approved API outcome.",
            "--scope",
            "API implementation and verification",
            "--decision",
            "Keep user-facing reports compact.",
            "--term",
            "Use orchestrator handoff for ownership transfer.",
            "--state",
            "Requirements are confirmed; implementation has not started.",
            "--evidence",
            "docs/specs/api/spec.md",
            "--next",
            "Invoke boss-say and begin the approved work.",
            "--exclude",
            "Frontend work remains outside this scope.",
        ]
        if approved:
            args.insert(0, "--user-approved")
        for retained in retains:
            args.extend(["--retains", retained])
        return args

    def test_handoff_refuses_to_create_a_window_without_user_approval(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(approved=False),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("explicit user approval", result.stderr)
        self.assertFalse(capture.exists())

    def test_handoff_refuses_a_source_pane_other_than_the_current_orchestrator(
        self,
    ) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_PANE_ID": "another-pane",
                "HERDR_WORKSPACE_ID": "workspace-1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("caller pane mismatch", result.stderr)
        self.assertFalse(capture.exists())

    def test_accepted_handoff_names_a_new_tab_invokes_boss_say_and_closes_source(
        self,
    ) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AUTO_ACCEPT_HANDOFF": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["accepted"])
        self.assertEqual(output["receiver_name"], "api-orchestrator")
        self.assertEqual(output["receiver_tab_id"], "new-tab")
        self.assertTrue(output["close_source_pane"])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertIn(
            [
                "tab",
                "create",
                "--workspace",
                "workspace-1",
                "--cwd",
                str(ROOT),
                "--label",
                "api-orchestrator",
                "--no-focus",
            ],
            calls,
        )
        self.assertIn(["tab", "rename", "new-tab", "api"], calls)
        prompt_call = next(call for call in calls if call[:2] == ["agent", "prompt"])
        prompt = prompt_call[3]
        self.assertNotIn("--wait", prompt_call)
        self.assertIn("Invoke `boss-say`", prompt)
        self.assertIn("Orchestrator handoff file:", prompt)
        self.assertIn("records acceptance after it establishes the work route", prompt)
        self.assertNotIn("accept-orchestrator-handoff.py", prompt)
        self.assertNotIn("--boss-say-routed", prompt)
        self.assertIn("Confirmed decisions:", prompt)
        self.assertIn("User terms:", prompt)
        self.assertNotIn("conversation", prompt.lower())
        self.assertLessEqual(len(prompt), 3000)
        self.assertEqual(calls[-1], ["pane", "close", "main-pane"])

    def test_handoff_waits_for_new_tab_shell_before_starting_receiver(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(retains=("Live verification",)),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AUTO_ACCEPT_HANDOFF": "1",
                "HERDR_PANE_BUSY_ATTEMPTS": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        starts = [call for call in calls if call[:2] == ["agent", "start"]]
        self.assertEqual(len(starts), 2)
        self.assertEqual(starts[0], starts[1])
        self.assertNotIn(["tab", "close", "new-tab"], calls)

    def test_tab_rename_failure_warns_but_still_transfers_the_scope(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(retains=("Release coordination",)),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AUTO_ACCEPT_HANDOFF": "1",
                "HERDR_FAIL_TAB_RENAME": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["accepted"])
        self.assertIn("tab naming failed after two attempts", output["warning"])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(
            len([call for call in calls if call[:2] == ["tab", "rename"]]),
            2,
        )
        self.assertNotIn(["tab", "close", "new-tab"], calls)

    def test_retained_work_keeps_the_source_pane_open(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(retains=("Release coordination",)),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AUTO_ACCEPT_HANDOFF": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["close_source_pane"])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertNotIn(["pane", "close", "main-pane"], calls)

    def test_accepted_handoff_retries_a_failed_source_pane_close(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AUTO_ACCEPT_HANDOFF": "1",
                "HERDR_FAIL_PANE_CLOSE": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertEqual(result.returncode, 2)
        self.assertTrue(json.loads(result.stdout)["accepted"])
        self.assertIn("source pane stayed open", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(
            len(
                [
                    call
                    for call in calls
                    if call == ["pane", "close", "main-pane"]
                ]
            ),
            2,
        )

    def test_unaccepted_handoff_retries_then_closes_only_the_new_tab(self) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            "--accept-timeout-seconds",
            "0",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("after two attempts", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call for call in calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual(len(prompts), 2)
        self.assertIn(["tab", "close", "new-tab"], calls)
        self.assertNotIn(["pane", "close", "main-pane"], calls)
        handoff_dir = self.home / ".straw-boss" / "handoffs"
        self.assertEqual(list(handoff_dir.glob("*.json")), [])

    def test_failed_receiver_cleanup_error_is_reported_and_source_stays_open(
        self,
    ) -> None:
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            "--accept-timeout-seconds",
            "0",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_FAIL_TAB_CLOSE": "1",
                "HERDR_FAIL_PANE_CLOSE": "1",
                "HERDR_WORKSPACE_ID": "workspace-1",
                "HERDR_PANE_ID": "main-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to close the new orchestrator tab", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(
            len([call for call in calls if call[:2] == ["tab", "close"]]),
            2,
        )
        self.assertIn(["agent", "send-keys", "new-pane", "esc"], calls)
        self.assertIn(["pane", "close", "new-pane"], calls)
        self.assertNotIn(["pane", "close", "main-pane"], calls)
        recovery_paths = list((self.home / ".straw-boss" / "handoffs").glob("*.json"))
        self.assertEqual(len(recovery_paths), 1)
        self.assertEqual(json.loads(recovery_paths[0].read_text())["status"], "cleanup-failed")

    def test_malformed_tab_create_response_still_closes_the_created_tab(self) -> None:
        for malformed_shape in ("missing-root", "missing-tab"):
            with self.subTest(malformed_shape=malformed_shape):
                fake_bin, capture = self.install_fake_herdr()
                capture.unlink(missing_ok=True)
                result = self.run_script(
                    "handoff-orchestrator.py",
                    *self.handoff_args(),
                    extra_env={
                        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                        "HERDR_CAPTURE": str(capture),
                        "HERDR_MALFORMED_TAB_CREATE": malformed_shape,
                        "HERDR_WORKSPACE_ID": "workspace-1",
                        "HERDR_PANE_ID": "main-pane",
                        "HERDR_PROCESS_INFO_CALLER": "1",
                    },
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("did not return tab and root_pane", result.stderr)
                calls = [json.loads(line) for line in capture.read_text().splitlines()]
                self.assertIn(["tab", "close", "new-tab"], calls)

    def test_receiver_acceptance_is_bound_to_the_new_pane(self) -> None:
        fake_bin, capture = self.install_fake_herdr()
        herdr_env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
        }
        path = self.home / ".straw-boss" / "handoffs" / "one.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "status": "offered",
                    "scope": "API",
                    "receiver_pane_id": "new-pane",
                }
            )
        )

        wrong = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env={
                **herdr_env,
                "HERDR_PANE_ID": "other-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )
        self.assertNotEqual(wrong.returncode, 0)

        unrouted = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            extra_env={
                **herdr_env,
                "HERDR_PANE_ID": "new-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )
        self.assertNotEqual(unrouted.returncode, 0)
        self.assertIn("required", unrouted.stderr)

        spoofed = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env={**herdr_env, "HERDR_PANE_ID": "new-pane"},
        )
        self.assertNotEqual(spoofed.returncode, 0)
        self.assertIn("not running inside Herdr pane", spoofed.stderr)

        accepted = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env={
                **herdr_env,
                "HERDR_PANE_ID": "new-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        payload = json.loads(path.read_text())
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(
            payload["route"],
            {
                "routed_through": "boss-say",
                "owner": "shipping-task",
                "coordination_graph": "single-loop",
                "reality_anchor": "testing at the executable lifecycle boundary",
                "routed_at": payload["route"]["routed_at"],
            },
        )

    def test_source_rejects_acceptance_without_structured_route_facts(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            module = runpy.run_path(str(ROOT / "scripts" / "handoff-orchestrator.py"))
        finally:
            sys.path.pop(0)
        path = self.home / "legacy-acceptance.json"
        path.write_text(
            json.dumps(
                {
                    "status": "accepted",
                    "receiver_pane_id": "new-pane",
                    "accepted_by_pane": "new-pane",
                    "accepted_at": "2026-09-02T00:00:00+00:00",
                    "routed_through": "boss-say",
                }
            )
        )

        self.assertIsNone(module["wait_for_acceptance"](path, 0))

    def test_receiver_cannot_accept_an_arbitrary_json_path(self) -> None:
        path = self.home / "unrelated.json"
        original = {
            "status": "offered",
            "scope": "API",
            "receiver_pane_id": "new-pane",
        }
        path.write_text(json.dumps(original))

        result = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env={
                "HERDR_PANE_ID": "new-pane",
                "HERDR_PROCESS_INFO_CALLER": "1",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("handoff path must be inside", result.stderr)
        self.assertEqual(json.loads(path.read_text()), original)


    RECEIVER_AGENT = {
        "agent": "claude",
        "agent_session": {"value": "receiver-session"},
        "agent_status": "idle",
        "pane_id": "new-pane",
        "terminal_id": "terminal-new-pane",
        "name": "receiver",
    }

    def transfer_env(self, fake_bin: Path, capture: Path, pane: str) -> dict[str, str]:
        return {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": pane,
            "HERDR_PROCESS_INFO_CALLER": "1",
            "HERDR_WORKSPACE_ID": "workspace-1",
            "HERDR_SESSIONS": json.dumps(
                {
                    "main-pane": "main-session",
                    "new-pane": "receiver-session",
                    "worker-pane": "worker-session",
                }
            ),
            "HERDR_AGENT_LIST": json.dumps([self.RECEIVER_AGENT]),
        }

    def live_dispatch_with_coworker(self) -> tuple[Path, Path]:
        parent, _ = self.write_dispatch("claude", main_agent_kind="claude")
        self.set_worker_endpoint(parent)
        written = self.write_coworker(parent)
        self.assertEqual(written.returncode, 0, written.stderr)
        child = Path(json.loads(written.stdout)["instruction_path"])
        self.set_worker_endpoint(child, pane="coworker-pane", session="coworker-session")
        return parent, child

    def offered_handoff(self, dispatches: list[dict[str, object]]) -> Path:
        path = self.home / ".straw-boss" / "handoffs" / "offer.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "status": "offered",
                    "scope": "API",
                    "source_pane_id": "main-pane",
                    "receiver_pane_id": "new-pane",
                    "dispatches": dispatches,
                }
            )
        )
        return path

    @staticmethod
    def main_route(instruction_path: Path) -> dict[str, object]:
        instruction = json.loads(instruction_path.read_text())
        return {
            field: instruction.get(f"main_agent_{field}")
            for field in ("herdr_pane_id", "session_id", "herdr_terminal_id", "kind")
        }

    def test_handoff_refuses_to_close_the_source_over_an_unlisted_dispatch(self) -> None:
        parent, _ = self.live_dispatch_with_coworker()
        fake_bin, capture = self.install_fake_herdr()
        capture.unlink(missing_ok=True)

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            extra_env=self.transfer_env(fake_bin, capture, "main-pane"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not list", result.stderr)
        self.assertIn(str(parent.resolve()), result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["tab", "create"] for call in calls))

    def test_retained_handoff_leaves_unlisted_dispatches_with_the_source(self) -> None:
        parent, _ = self.live_dispatch_with_coworker()
        before = parent.read_text()
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(retains=("API verification",)),
            extra_env={
                **self.transfer_env(fake_bin, capture, "main-pane"),
                "HERDR_ACCEPT_HANDOFF_SCRIPT": str(ROOT / "scripts" / "accept-orchestrator-handoff.py"),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(parent.read_text(), before)

    def test_accepted_handoff_moves_listed_dispatches_to_the_receiver(self) -> None:
        parent, child = self.live_dispatch_with_coworker()
        fake_bin, capture = self.install_fake_herdr()
        capture.unlink(missing_ok=True)
        base = self.transfer_env(fake_bin, capture, "main-pane")

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(),
            "--dispatch",
            str(parent),
            extra_env={
                **base,
                "HERDR_ACCEPT_HANDOFF_SCRIPT": str(ROOT / "scripts" / "accept-orchestrator-handoff.py"),
            },
        )

        accept_log = Path(f"{capture}.accept")
        self.assertEqual(
            result.returncode,
            0,
            result.stderr + (accept_log.read_text() if accept_log.exists() else ""),
        )
        output = json.loads(result.stdout)
        self.assertEqual(output["transferred_dispatches"], [str(parent.resolve())])
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[-1], ["pane", "close", "main-pane"])
        self.assertEqual(
            self.main_route(parent),
            {
                "herdr_pane_id": "new-pane",
                "session_id": "receiver-session",
                "herdr_terminal_id": "terminal-new-pane",
                "kind": "claude",
            },
        )
        moved = json.loads(parent.read_text())
        transfer = moved["main_agent_transfers"][-1]
        self.assertEqual(transfer["reason"], "orchestrator-handoff")
        self.assertEqual(transfer["before"]["herdr_pane_id"], "main-pane")
        self.assertEqual(transfer["before"]["session_id"], "main-session")
        self.assertEqual(transfer["evidence"]["source_pane_id"], "main-pane")
        self.assertEqual(moved["session_id"], "worker-session")
        coworker = json.loads(child.read_text())
        self.assertEqual(coworker["root_main_agent_herdr_pane_id"], "new-pane")
        self.assertEqual(coworker["root_main_agent_session_id"], "receiver-session")
        self.assertEqual(coworker["root_main_agent_transfers"][-1]["reason"], "orchestrator-handoff")
        self.assertEqual(coworker["main_agent_herdr_pane_id"], "worker-pane")

        capture.unlink()
        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(parent),
            "--status",
            "awaiting-main-agent",
            "--note",
            "Need the API contract decision.",
            extra_env={**base, "HERDR_PANE_ID": "worker-pane"},
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        prompts = [call[2] for call in calls if call[:2] == ["agent", "prompt"]]
        self.assertEqual(prompts, ["new-pane"])

        closed_worker = {"HERDR_MISSING_PANES": json.dumps(["worker-pane"])}
        source = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(parent),
            "--status",
            "failed",
            "--note",
            "Worker pane closed after the handoff.",
            extra_env={**base, **closed_worker},
        )
        self.assertNotEqual(source.returncode, 0)
        self.assertIn("sender pane mismatch", source.stderr)
        receiver = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(parent),
            "--status",
            "failed",
            "--note",
            "Worker pane closed after the handoff.",
            extra_env={**base, **closed_worker, "HERDR_PANE_ID": "new-pane"},
        )
        self.assertEqual(receiver.returncode, 0, receiver.stderr)

    def test_acceptance_refuses_a_dispatch_whose_route_changed_after_the_offer(self) -> None:
        parent, child = self.live_dispatch_with_coworker()
        offered = {**self.main_route(parent), "session_id": "earlier-session"}
        path = self.offered_handoff([{"instruction_path": str(parent.resolve()), "route": offered}])
        before = (parent.read_text(), child.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env=self.transfer_env(fake_bin, capture, "new-pane"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer carries the route the handoff offered", result.stderr)
        self.assertEqual(json.loads(path.read_text())["status"], "offered")
        self.assertEqual((parent.read_text(), child.read_text()), before)

    def test_acceptance_skips_a_wrapped_dispatch_and_completes_an_interrupted_move(
        self,
    ) -> None:
        parent, _ = self.live_dispatch_with_coworker()
        offered = self.main_route(parent)
        instruction = json.loads(parent.read_text())
        instruction.update(
            main_agent_herdr_pane_id="new-pane",
            main_agent_session_id="receiver-session",
            main_agent_herdr_terminal_id="terminal-new-pane",
        )
        parent.write_text(json.dumps(instruction, indent=2) + "\n")
        wrapped = self.home / ".straw-boss" / "dispatch" / "api--wrapped.json"
        path = self.offered_handoff(
            [
                {"instruction_path": str(parent.resolve()), "route": offered},
                {"instruction_path": str(wrapped), "route": offered},
            ]
        )
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env=self.transfer_env(fake_bin, capture, "new-pane"),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["transferred_dispatches"], [str(parent.resolve())])
        self.assertEqual(output["skipped_dispatches"], [str(wrapped)])
        self.assertNotIn("main_agent_transfers", json.loads(parent.read_text()))
        self.assertEqual(json.loads(path.read_text())["status"], "accepted")


    def test_handoff_refuses_a_listed_dispatch_this_pane_does_not_coordinate(self) -> None:
        parent, _ = self.live_dispatch_with_coworker()
        instruction = json.loads(parent.read_text())
        instruction["main_agent_session_id"] = "another-coordinator"
        parent.write_text(json.dumps(instruction, indent=2) + "\n")
        fake_bin, capture = self.install_fake_herdr()
        capture.unlink(missing_ok=True)

        result = self.run_script(
            "handoff-orchestrator.py",
            *self.handoff_args(retains=("API verification",)),
            "--dispatch",
            str(parent),
            extra_env=self.transfer_env(fake_bin, capture, "main-pane"),
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("session mismatch", result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ["tab", "create"] for call in calls))

    def test_acceptance_refuses_a_receiver_herdr_cannot_identify(self) -> None:
        parent, child = self.live_dispatch_with_coworker()
        path = self.offered_handoff(
            [{"instruction_path": str(parent.resolve()), "route": self.main_route(parent)}]
        )
        before = (parent.read_text(), child.read_text())
        fake_bin, capture = self.install_fake_herdr()

        result = self.run_script(
            "accept-orchestrator-handoff.py",
            "--handoff-path",
            str(path),
            *self.ROUTE_ARGS,
            extra_env={
                **self.transfer_env(fake_bin, capture, "new-pane"),
                "HERDR_AGENT_LIST": "[]",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no live agent in pane 'new-pane'", result.stderr)
        self.assertEqual(json.loads(path.read_text())["status"], "offered")
        self.assertEqual((parent.read_text(), child.read_text()), before)


if __name__ == "__main__":
    unittest.main()
