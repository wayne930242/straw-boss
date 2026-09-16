from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class MainAgentAdoptionTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    """A coordinator that restarts in its own pane keeps the pane and loses the
    conversation id, so every dispatch it made before the restart records a main
    identity that no live session can satisfy."""

    def restarted_coordinator_env(
        self,
        fake_bin: Path,
        capture: Path,
        *,
        registry_session: str = "successor-session",
        caller_inside_pane: bool = True,
    ) -> dict[str, str]:
        claude_sessions = self.home / ".claude" / "sessions"
        claude_sessions.mkdir(parents=True, exist_ok=True)
        (claude_sessions / "4242.json").write_text(
            json.dumps(
                {
                    "pid": 4242,
                    "sessionId": registry_session,
                    "kind": "interactive",
                    "entrypoint": "cli",
                }
            )
            + "\n"
        )
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": "main-pane",
            # herdr routinely reports no agent_session for a live Claude pane,
            # which is why the registry is the identity of record here.
            "HERDR_OMIT_AGENT_SESSION": "1",
            "HERDR_MISSING_PANES": json.dumps(["worker-pane"]),
            "HERDR_PROCESS_INFOS": json.dumps(
                {
                    "main-pane": {
                        "pane_id": "main-pane",
                        "foreground_process_group_id": 4242,
                        "foreground_processes": [
                            {"pid": 4242, "argv0": "claude", "argv": ["claude"]}
                        ],
                    }
                }
            ),
        }
        if caller_inside_pane:
            env["HERDR_PROCESS_INFO_CALLER"] = "1"
        return env

    def orphaned_dispatch(self) -> Path:
        instruction_path, _ = self.write_dispatch("claude", main_agent_kind="claude")
        self.set_worker_endpoint(instruction_path)
        return instruction_path

    def test_restarted_coordinator_can_close_its_own_orphaned_dispatch(self) -> None:
        instruction_path = self.orphaned_dispatch()
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture)

        blocked = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "派工 pane 已關閉，協調者重啟後承接收尾。",
            extra_env=env,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("session mismatch", blocked.stderr)
        self.assertFalse(status_path.exists())

        adopt = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "successor-session",
            extra_env=env,
        )
        self.assertEqual(adopt.returncode, 0, adopt.stderr)
        adopted = json.loads(adopt.stdout)
        self.assertEqual(adopted["previous_main_session_id"], "main-session")
        self.assertEqual(adopted["main_session_id"], "successor-session")

        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["main_agent_session_id"], "successor-session")
        self.assertEqual(instruction["status"], "in-progress")
        record = instruction["main_agent_adoptions"][-1]
        self.assertEqual(record["before"]["main_agent_session_id"], "main-session")
        self.assertEqual(record["after"]["main_agent_session_id"], "successor-session")

        recovered = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "派工 pane 已關閉，協調者重啟後承接收尾。",
            extra_env=env,
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(json.loads(status_path.read_text())["status"], "failed")

        wrap = self.run_script("wrap-up-task.py", "--app", "api", "--slug", "contract-claude")
        self.assertEqual(wrap.returncode, 0, wrap.stderr)

    def test_adoption_refuses_a_caller_that_is_not_running_inside_the_recorded_pane(
        self,
    ) -> None:
        """Knowing the instruction path is not ownership; the process tree is."""
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture, caller_inside_pane=False)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "successor-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not running inside Herdr pane", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def moved_coordinator_env(
        self,
        fake_bin: Path,
        capture: Path,
        *,
        registry_session: str = "main-session",
        caller_inside_pane: bool = True,
        recorded_pane_gone: bool = True,
    ) -> dict[str, str]:
        """The same conversation, resumed in a new pane after its old one closed.

        The Claude registry keyed on the new pane's foreground process places the
        recorded main session there; the recorded pane is gone unless a test
        says otherwise.
        """
        claude_sessions = self.home / ".claude" / "sessions"
        claude_sessions.mkdir(parents=True, exist_ok=True)
        for pid, session in ((4242, "main-session"), (4343, registry_session)):
            (claude_sessions / f"{pid}.json").write_text(
                json.dumps(
                    {
                        "pid": pid,
                        "sessionId": session,
                        "kind": "interactive",
                        "entrypoint": "cli",
                    }
                )
                + "\n"
            )
        missing = ["worker-pane"]
        if recorded_pane_gone:
            missing.append("main-pane")
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": "new-pane",
            "HERDR_OMIT_AGENT_SESSION": "1",
            "HERDR_MISSING_PANES": json.dumps(missing),
            "HERDR_PROCESS_INFOS": json.dumps(
                {
                    "main-pane": {
                        "pane_id": "main-pane",
                        "foreground_process_group_id": 4242,
                        "foreground_processes": [
                            {"pid": 4242, "argv0": "claude", "argv": ["claude"]}
                        ],
                    },
                    "new-pane": {
                        "pane_id": "new-pane",
                        "foreground_process_group_id": 4343,
                        "foreground_processes": [
                            {"pid": 4343, "argv0": "claude", "argv": ["claude"]}
                        ],
                    },
                }
            ),
        }
        if caller_inside_pane:
            env["HERDR_PROCESS_INFO_CALLER"] = "1"
        return env

    def test_the_same_session_in_a_new_pane_moves_its_dispatch_route(self) -> None:
        """A coordinator whose conversation resumed in another pane keeps its
        session id, so its dispatches still name it -- at a pane that is gone."""
        instruction_path = self.orphaned_dispatch()
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture)

        blocked = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "派工 pane 已關閉，協調者換 pane 後承接收尾。",
            extra_env=env,
        )
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("sender pane mismatch", blocked.stderr)
        self.assertFalse(status_path.exists())

        adopt = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )
        self.assertEqual(adopt.returncode, 0, adopt.stderr)
        adopted = json.loads(adopt.stdout)
        self.assertEqual(adopted["previous_pane_id"], "main-pane")
        self.assertEqual(adopted["pane_id"], "new-pane")
        self.assertEqual(adopted["main_session_id"], "main-session")

        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["main_agent_herdr_pane_id"], "new-pane")
        self.assertEqual(instruction["main_agent_session_id"], "main-session")
        self.assertEqual(instruction["status"], "in-progress")
        record = instruction["main_agent_adoptions"][-1]
        self.assertEqual(record["before"], {"main_agent_herdr_pane_id": "main-pane"})
        self.assertEqual(record["after"], {"main_agent_herdr_pane_id": "new-pane"})

        recovered = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "failed",
            "--note",
            "派工 pane 已關閉，協調者換 pane 後承接收尾。",
            extra_env=env,
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(json.loads(status_path.read_text())["status"], "failed")

    def test_a_worker_report_reaches_the_pane_the_coordinator_moved_to(self) -> None:
        instruction_path = self.orphaned_dispatch()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture)

        adopt = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )
        self.assertEqual(adopt.returncode, 0, adopt.stderr)

        worker_env = {
            "PATH": env["PATH"],
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": "worker-pane",
            "HERDR_MISSING_PANES": json.dumps(["main-pane"]),
            "HERDR_PROCESS_INFOS": env["HERDR_PROCESS_INFOS"],
            "HERDR_SESSIONS": json.dumps(
                {"worker-pane": "worker-session", "new-pane": "main-session"}
            ),
        }
        report = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "Finished; evidence in the referenced commit.",
            extra_env=worker_env,
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("notified main agent", report.stdout)

        prompts = [
            json.loads(line)
            for line in capture.read_text().splitlines()
            if json.loads(line)[:2] == ["agent", "prompt"]
        ]
        self.assertEqual([call[2] for call in prompts], ["new-pane"])

    def test_a_pane_move_refuses_a_session_that_is_not_the_recorded_one(self) -> None:
        """Ownership follows the session here: another conversation in another
        pane is exactly the stray caller the guard exists to keep out."""
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture, registry_session="other-session")

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "other-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not the recorded main session", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_a_pane_move_refuses_a_caller_outside_its_own_pane(self) -> None:
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture, caller_inside_pane=False)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not running inside Herdr pane", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_a_pane_move_refuses_while_the_recorded_pane_still_hosts_the_session(
        self,
    ) -> None:
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture, recorded_pane_gone=False)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("still hosts", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_a_pane_move_refuses_when_herdr_cannot_answer_for_the_recorded_pane(
        self,
    ) -> None:
        """A transport failure against the old pane is no answer about who holds
        it, so it refuses the move instead of reading as "the session left"."""
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture, recorded_pane_gone=False)
        env["HERDR_GARBLED_PANES"] = json.dumps(["main-pane"])

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-JSON", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_main_side_commands_follow_the_coordinator_to_its_new_pane(self) -> None:
        """Every main-side command shares the sender guard, so the move has to
        carry replies, messages, and pane closure -- not only status recovery."""
        instruction_path = self.orphaned_dispatch()
        fake_bin, capture = self.install_fake_herdr()
        env = self.moved_coordinator_env(fake_bin, capture)
        # The worker pane is live here, and Herdr exposes both sessions.
        del env["HERDR_OMIT_AGENT_SESSION"]
        env["HERDR_MISSING_PANES"] = json.dumps(["main-pane"])
        env["HERDR_SESSIONS"] = json.dumps(
            {"worker-pane": "worker-session", "new-pane": "main-session"}
        )
        worker_env = {**env, "HERDR_PANE_ID": "worker-pane"}
        worker_env.pop("HERDR_PROCESS_INFO_CALLER")
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")

        def main_side_commands() -> list[list[str]]:
            return [
                [
                    "send-dispatch-message.py",
                    "--instruction-path",
                    str(instruction_path),
                    "--to",
                    "worker",
                    "--intent",
                    "inform",
                    "--message",
                    "The fix branch is main.",
                ],
                [
                    "reply-to-worker.py",
                    "--worker-instruction-path",
                    str(instruction_path),
                    "--reply",
                    "Proceed with option B.",
                ],
                ["close-worker-pane.py", "--instruction-path", str(instruction_path)],
            ]

        checkpoint = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "awaiting-main-agent",
            "--note",
            "Option A or B?",
            extra_env=worker_env,
        )
        # The recorded main pane is gone, so the report is written but lands
        # in the delivery ledger -- the situation adoption exists to repair.
        self.assertNotEqual(checkpoint.returncode, 0)
        self.assertIn("recorded undelivered", checkpoint.stderr)
        self.assertEqual(json.loads(status_path.read_text())["status"], "awaiting-main-agent")

        for command in main_side_commands():
            blocked = self.run_script(*command, extra_env=env)
            self.assertNotEqual(blocked.returncode, 0, command[0])
            self.assertIn("sender pane mismatch", blocked.stderr, command[0])

        adopt = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )
        self.assertEqual(adopt.returncode, 0, adopt.stderr)
        message, reply, close = main_side_commands()

        sent = self.run_script(*message, extra_env=env)
        self.assertEqual(sent.returncode, 0, sent.stderr)
        self.assertTrue(json.loads(sent.stdout)["submitted"])

        replied = self.run_script(*reply, extra_env=env)
        self.assertEqual(replied.returncode, 0, replied.stderr)

        finished = self.run_script(
            "report-task-status.py",
            "--instruction-path",
            str(instruction_path),
            "--status",
            "done",
            "--note",
            "Done with option B.",
            extra_env=worker_env,
        )
        self.assertEqual(finished.returncode, 0, finished.stderr)
        closed = self.run_script(*close, extra_env=env)
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertEqual(json.loads(closed.stdout)["closed_pane_id"], "worker-pane")

        prompts = [
            json.loads(line)
            for line in capture.read_text().splitlines()
            if json.loads(line)[:2] == ["agent", "prompt"]
        ]
        self.assertEqual(
            sorted({call[2] for call in prompts}), ["new-pane", "worker-pane"]
        )

    def test_adoption_refuses_when_the_recorded_session_is_already_the_live_one(self) -> None:
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture, registry_session="main-session")

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "main-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("nothing to adopt", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_adoption_refuses_a_session_the_pane_cannot_corroborate(self) -> None:
        """The caller states which session it is; the pane decides whether that is true."""
        instruction_path = self.orphaned_dispatch()
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "a-session-that-is-somewhere-else",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot corroborate", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_adoption_refuses_a_codex_main_agent(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", main_agent_kind="codex")
        self.set_worker_endpoint(instruction_path)
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "successor-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rebind-dispatch.py", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)

    def test_adoption_refuses_an_antigravity_main_agent_without_a_codex_hint(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", main_agent_kind="agy")
        self.set_worker_endpoint(instruction_path)
        before = instruction_path.read_text()
        fake_bin, capture = self.install_fake_herdr()
        env = self.restarted_coordinator_env(fake_bin, capture)

        result = self.run_script(
            "adopt-dispatch.py",
            "--instruction-path",
            str(instruction_path),
            "--main-session-id",
            "successor-session",
            extra_env=env,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no adoption command exists for main agent kind 'agy'", result.stderr)
        self.assertNotIn("rebind-dispatch.py", result.stderr)
        self.assertEqual(instruction_path.read_text(), before)


if __name__ == "__main__":
    unittest.main()
