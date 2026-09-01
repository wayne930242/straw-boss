from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


def agent(
    pane_id: str,
    session: str,
    *,
    status: str = "idle",
    name: str | None = None,
    title: str = "weihung@host: ~/projects",
) -> dict[str, object]:
    record: dict[str, object] = {
        "agent": "claude",
        "agent_session": {"value": session},
        "agent_status": status,
        "pane_id": pane_id,
        "terminal_id": f"terminal-{pane_id}",
        "terminal_title": title,
        "terminal_title_stripped": title,
        "cwd": "/repo",
    }
    if name is not None:
        record["name"] = name
    return record


class RollCallTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def roll_call(
        self,
        agents: list[dict[str, object]],
        *args: str,
        panes: list[dict[str, object]] | None = None,
        pane_id: str | None = None,
    ) -> dict[str, object]:
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_AGENT_LIST": json.dumps(agents),
            "HERDR_PANE_LIST": json.dumps(
                panes if panes is not None else [{"pane_id": a["pane_id"]} for a in agents]
            ),
        }
        if pane_id is not None:
            env["HERDR_PANE_ID"] = pane_id
        result = self.run_script("roll-call.py", "--json", *args, extra_env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def row(self, report: dict[str, object], dispatch: str) -> dict[str, object]:
        rows = [r for r in report["dispatches"] if r["dispatch"] == dispatch]
        self.assertEqual(len(rows), 1, report["dispatches"])
        return rows[0]

    def test_an_idle_worker_whose_pane_title_fell_back_to_a_shell_prompt_is_running(
        self,
    ) -> None:
        # The duplicate-dispatch incident in one line: the worker was alive the
        # whole time and merely idle, so its pane title had gone back to
        # looking like a bare shell. Only agent_session.value plus agent_status
        # may decide this.
        instruction_path, _ = self.write_dispatch(slug="live-worker")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        report = self.roll_call(
            [agent("wF:p9", "worker-session", status="idle", title="weihung@host: ~/repo")]
        )

        row = self.row(report, "api--live-worker")
        self.assertEqual(row["verdict"], "running")
        self.assertEqual(row["worker_agent_status"], "idle")

    def test_an_instruction_whose_session_has_no_live_agent_is_orphaned(self) -> None:
        instruction_path, _ = self.write_dispatch(slug="gone-worker")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        report = self.roll_call([agent("wF:p9", "somebody-elses-session")])

        row = self.row(report, "api--gone-worker")
        self.assertEqual(row["verdict"], "orphaned")
        self.assertIsNone(row["worker_agent_status"])

    def test_a_terminal_status_with_a_live_pane_is_awaiting_collection(self) -> None:
        instruction_path, _ = self.write_dispatch(slug="finished-worker")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")
        instruction_path.with_name("api--finished-worker.status.json").write_text(
            json.dumps({"status": "done"})
        )

        report = self.roll_call([agent("wF:p9", "worker-session")])

        row = self.row(report, "api--finished-worker")
        self.assertEqual(row["verdict"], "awaiting-collection")

    def test_a_pending_instruction_reports_why_its_launch_failed(self) -> None:
        instruction_path, _ = self.write_dispatch(slug="never-started")
        instruction_path.with_name("api--never-started.launch-failure.json").write_text(
            json.dumps(
                {
                    "attempts": [
                        {"attempt": 1, "error": "blocked on a Claude Code startup gate"}
                    ]
                }
            )
        )

        report = self.roll_call([])

        row = self.row(report, "api--never-started")
        self.assertEqual(row["verdict"], "never-launched")
        self.assertIn("startup gate", row["note"])

    def test_a_pending_instruction_with_a_live_agent_is_launched_unconfirmed(
        self,
    ) -> None:
        # The half-landed launch: an agent is up on this instruction's session
        # but dispatch-task.py confirm never ran. Reading the instruction alone
        # calls that never-launched and invites a second dispatch on top of a
        # worker already doing the job.
        instruction_path, _ = self.write_dispatch(slug="half-landed")
        instruction = json.loads(instruction_path.read_text())

        report = self.roll_call([agent("wF:p9", str(instruction["session_id"]))])

        row = self.row(report, "api--half-landed")
        self.assertEqual(row["verdict"], "launched-unconfirmed")
        self.assertEqual(row["worker_pane"], "wF:p9")

    def test_a_launched_codex_worker_is_found_through_its_receipt_before_confirm(
        self,
    ) -> None:
        # A Codex instruction carries no usable fingerprint until confirm runs:
        # session_id is None at write and herdr_terminal_id is filled only at
        # confirm. Without the receipt this live worker reads as
        # never-launched AND unattributed -- both halves of the incident this
        # script exists to prevent, at once.
        instruction_path, _ = self.write_dispatch("codex", slug="codex-preconfirm")
        instruction_path.with_name("api--codex-preconfirm.launch.json").write_text(
            json.dumps({"pane_id": "wF:p9", "herdr_terminal_id": "terminal-wF:p9"})
        )
        worker = agent("wF:p9", "unused-for-codex")
        worker["agent"] = "codex"

        report = self.roll_call([worker])

        row = self.row(report, "api--codex-preconfirm")
        self.assertEqual(row["verdict"], "launched-unconfirmed")
        self.assertEqual(row["worker_pane"], "wF:p9")
        self.assertNotIn(
            "wF:p9", {a["pane_id"] for a in report["agents_without_instruction"]}
        )

    def test_a_pane_a_failed_launch_kept_is_attributed_to_its_dispatch(self) -> None:
        # The launcher keeps a startup-gate pane on purpose. That worker has no
        # fingerprint yet -- herdr exposes no agent_session before the first
        # turn -- so the launch-failure record is the only thing tying the pane
        # back to its dispatch.
        instruction_path, _ = self.write_dispatch(slug="gated")
        instruction_path.with_name("api--gated.launch-failure.json").write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "attempt": 1,
                            "pane_id": "wF:p9",
                            "pane_left_open": True,
                            "error": "stopped on a Claude Code startup gate\nmore detail",
                        }
                    ]
                }
            )
        )
        gated = agent("wF:p9", "no-session-yet", status="blocked")
        del gated["agent_session"]

        report = self.roll_call([gated])

        row = self.row(report, "api--gated")
        self.assertEqual(row["verdict"], "awaiting-startup-gate")
        self.assertIn("startup gate", row["note"])
        self.assertEqual(row["worker_pane"], "wF:p9")
        self.assertNotIn(
            "wF:p9", {a["pane_id"] for a in report["agents_without_instruction"]}
        )

    def test_a_kept_pane_that_is_already_gone_is_not_reported_as_still_waiting(
        self,
    ) -> None:
        instruction_path, _ = self.write_dispatch(slug="gate-closed")
        instruction_path.with_name("api--gate-closed.launch-failure.json").write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "attempt": 1,
                            "pane_id": "wF:p9",
                            "pane_left_open": True,
                            "error": "stopped on a Claude Code startup gate",
                        }
                    ]
                }
            )
        )

        report = self.roll_call([], panes=[])

        row = self.row(report, "api--gate-closed")
        self.assertEqual(row["verdict"], "never-launched")

    def test_mine_refuses_rather_than_silently_reporting_everything(self) -> None:
        # Falling back to "all dispatches" answers the only question --mine
        # exists to answer, wrongly, and says nothing about having done so.
        self.write_dispatch(slug="somebody-elses")
        fake_bin, capture = self.install_fake_herdr()
        fingerprintless = agent("lonely-pane", "")
        del fingerprintless["agent_session"]
        fingerprintless["terminal_id"] = ""

        result = self.run_script(
            "roll-call.py",
            "--json",
            "--mine",
            extra_env={
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                "HERDR_CAPTURE": str(capture),
                "HERDR_AGENT_LIST": json.dumps([fingerprintless]),
                "HERDR_PANE_LIST": json.dumps([{"pane_id": "lonely-pane"}]),
                "HERDR_PANE_ID": "lonely-pane",
            },
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cannot tell this session's dispatches apart", result.stderr)

    def test_mine_matches_a_codex_coordinator_on_its_terminal_fingerprint(self) -> None:
        mine, _ = self.write_dispatch(main_agent_kind="codex", slug="codex-boss")
        self.set_worker_endpoint(mine, pane="wF:p9", session="my-worker-session")
        theirs, _ = self.write_dispatch(slug="claude-boss")
        self.set_worker_endpoint(theirs, pane="wF:p12", session="their-worker-session")

        report = self.roll_call(
            [
                agent("main-pane", "", name="codex-coordinator"),
                agent("wF:p9", "my-worker-session"),
                agent("wF:p12", "their-worker-session"),
            ],
            "--mine",
            pane_id="main-pane",
        )

        self.assertEqual([r["dispatch"] for r in report["dispatches"]], ["api--codex-boss"])

    def test_a_dispatchs_own_sibling_files_are_never_read_as_instructions(self) -> None:
        instruction_path, _ = self.write_dispatch(slug="with-siblings")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")
        for suffix in ("launch", "status", "launch-failure"):
            instruction_path.with_name(f"api--with-siblings.{suffix}.json").write_text(
                json.dumps({"status": "done"})
            )

        report = self.roll_call([agent("wF:p9", "worker-session")])

        self.assertEqual([r["dispatch"] for r in report["dispatches"]], ["api--with-siblings"])

    def test_a_coordinator_and_an_unwritten_worker_pane_are_named_not_orphaned(
        self,
    ) -> None:
        # Neither has an instruction of its own: the coordinator by design, the
        # fresh pane because its dispatch has not reached dispatch-task.py
        # write yet. Reporting either as ownerless is what got somebody else's
        # pane closed.
        instruction_path, _ = self.write_dispatch(slug="attributed")
        self.set_worker_endpoint(instruction_path, pane="wF:p9", session="worker-session")

        report = self.roll_call(
            [
                agent("wF:p9", "worker-session"),
                agent("main-pane", "main-session", name="api-coordinator"),
                agent("wF:p11", "just-split-session"),
            ]
        )

        roles = {a["pane_id"]: a["role"] for a in report["agents_without_instruction"]}
        self.assertEqual(roles, {"main-pane": "coordinator", "wF:p11": "unattributed"})

    def test_mine_narrows_dispatches_without_unattributing_another_coordinators_worker(
        self,
    ) -> None:
        mine, _ = self.write_dispatch(slug="mine")
        self.set_worker_endpoint(mine, pane="wF:p9", session="my-worker-session")
        theirs, _ = self.write_dispatch(slug="theirs")
        payload = json.loads(theirs.read_text())
        payload.update(
            {
                "status": "in-progress",
                "herdr_pane_id": "wF:p12",
                "session_id": "their-worker-session",
                "main_agent_herdr_pane_id": "their-pane",
                "main_agent_session_id": "their-session",
            }
        )
        theirs.write_text(json.dumps(payload, indent=2) + "\n")

        report = self.roll_call(
            [
                agent("main-pane", "main-session", name="api-coordinator"),
                agent("wF:p9", "my-worker-session"),
                agent("their-pane", "their-session", name="other-coordinator"),
                agent("wF:p12", "their-worker-session"),
            ],
            "--mine",
            pane_id="main-pane",
        )

        self.assertEqual([r["dispatch"] for r in report["dispatches"]], ["api--mine"])
        listed = {a["pane_id"] for a in report["agents_without_instruction"]}
        self.assertNotIn("wF:p12", listed)
        self.assertEqual(
            {a["pane_id"]: a["role"] for a in report["agents_without_instruction"]},
            {"main-pane": "coordinator", "their-pane": "coordinator"},
        )


if __name__ == "__main__":
    unittest.main()
