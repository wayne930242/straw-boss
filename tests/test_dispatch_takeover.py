from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


def live_agent(pane_id: str, session: str) -> dict[str, object]:
    return {
        "agent": "claude",
        "agent_session": {"value": session},
        "agent_status": "idle",
        "pane_id": pane_id,
        "terminal_id": f"terminal-{pane_id}",
        "name": pane_id,
    }


class DispatchTakeoverTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    """The user asks one main agent to take over dispatches another coordinates."""

    def takeover_env(
        self, *, previous_live: bool = False, pane: str = "taker-pane"
    ) -> dict[str, str]:
        fake_bin, capture = self.install_fake_herdr()
        agents = [live_agent("taker-pane", "taker-session")]
        if previous_live:
            agents.append(live_agent("main-pane", "main-session"))
        return {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": pane,
            "HERDR_PROCESS_INFO_CALLER": "1",
            "HERDR_SESSIONS": json.dumps(
                {
                    "taker-pane": "taker-session",
                    "main-pane": "main-session",
                    "worker-pane": "worker-session",
                }
            ),
            "HERDR_AGENT_LIST": json.dumps(agents),
        }

    def live_dispatch(self, slug: str = "contract-claude") -> Path:
        path, _ = self.write_dispatch("claude", main_agent_kind="claude", slug=slug)
        self.set_worker_endpoint(path)
        return path

    def take_over(
        self, *paths: Path, env: dict[str, str], requested: bool = True
    ) -> subprocess.CompletedProcess[str]:
        args = ["--user-requested"] if requested else []
        for path in paths:
            args.extend(["--instruction-path", str(path)])
        return self.run_script("take-over-dispatch.py", *args, extra_env=env)

    def test_takeover_refuses_without_the_users_request(self) -> None:
        path = self.live_dispatch()
        before = path.read_text()

        result = self.take_over(path, env=self.takeover_env(), requested=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only when the user asks", result.stderr)
        self.assertEqual(path.read_text(), before)

    def test_takeover_moves_the_dispatch_and_its_coworker_root_to_the_caller(self) -> None:
        parent = self.live_dispatch()
        written = self.write_coworker(parent)
        self.assertEqual(written.returncode, 0, written.stderr)
        child = Path(json.loads(written.stdout)["instruction_path"])
        self.set_worker_endpoint(child, pane="coworker-pane", session="coworker-session")
        env = self.takeover_env()

        result = self.take_over(parent, env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["coordinator"]["herdr_pane_id"], "taker-pane")
        taken = output["taken_over"][0]
        self.assertEqual(taken["before"]["herdr_pane_id"], "main-pane")
        self.assertFalse(taken["previous_coordinator_live"])
        instruction = json.loads(parent.read_text())
        self.assertEqual(instruction["main_agent_herdr_pane_id"], "taker-pane")
        self.assertEqual(instruction["main_agent_session_id"], "taker-session")
        entry = instruction["main_agent_transfers"][-1]
        self.assertEqual(entry["reason"], "user-requested-takeover")
        self.assertEqual(entry["evidence"], {"user_requested": True})
        coworker = json.loads(child.read_text())
        self.assertEqual(coworker["root_main_agent_herdr_pane_id"], "taker-pane")
        self.assertEqual(coworker["root_main_agent_session_id"], "taker-session")

        closed_worker = {"HERDR_MISSING_PANES": json.dumps(["worker-pane"])}
        recovered = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(parent),
            "--status",
            "failed",
            "--note",
            "Worker pane closed; the new coordinator records the outcome.",
            extra_env={**env, **closed_worker},
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_takeover_proceeds_and_reports_a_previous_coordinator_that_is_still_live(
        self,
    ) -> None:
        path = self.live_dispatch()

        result = self.take_over(path, env=self.takeover_env(previous_live=True))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["taken_over"][0]["previous_coordinator_live"])
        self.assertEqual(json.loads(path.read_text())["main_agent_herdr_pane_id"], "taker-pane")

    def test_one_refused_dispatch_writes_nothing(self) -> None:
        live = self.live_dispatch()
        pending, _ = self.write_dispatch("claude", main_agent_kind="claude", slug="not-launched")
        before = (live.read_text(), pending.read_text())

        result = self.take_over(live, pending, env=self.takeover_env())

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only an in-progress dispatch moves", result.stderr)
        self.assertEqual((live.read_text(), pending.read_text()), before)

    def test_takeover_refuses_a_dispatch_already_routed_to_the_caller(self) -> None:
        path = self.live_dispatch()
        env = self.takeover_env()
        self.assertEqual(self.take_over(path, env=env).returncode, 0)

        again = self.take_over(path, env=env)

        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already routes to this coordinator", again.stderr)
        self.assertEqual(len(json.loads(path.read_text())["main_agent_transfers"]), 1)


    def test_a_codex_coordinator_takes_over_a_claude_coordinators_dispatch(self) -> None:
        path = self.live_dispatch()
        taker = {
            **live_agent("taker-pane", "codex-session"),
            "agent": "codex",
            "terminal_id": "terminal-codex",
        }
        env = {
            **self.takeover_env(),
            "HERDR_AGENT_LIST": json.dumps([taker]),
            "HERDR_AGENT_KINDS": json.dumps({"taker-pane": "codex"}),
            "HERDR_TERMINAL_IDS": json.dumps({"taker-pane": "terminal-codex"}),
            "HERDR_SESSIONS": json.dumps(
                {"taker-pane": "codex-session", "worker-pane": "worker-session"}
            ),
        }

        result = self.take_over(path, env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        instruction = json.loads(path.read_text())
        self.assertEqual(instruction["main_agent_kind"], "codex")
        self.assertEqual(instruction["main_agent_session_id"], "codex-session")
        self.assertEqual(instruction["main_agent_herdr_terminal_id"], "terminal-codex")
        recovered = self.run_script(
            "recover-task-status.py",
            "--instruction-path",
            str(path),
            "--status",
            "failed",
            "--note",
            "Worker pane closed; the Codex coordinator records the outcome.",
            extra_env={**env, "HERDR_MISSING_PANES": json.dumps(["worker-pane"])},
        )
        self.assertEqual(recovered.returncode, 0, recovered.stderr)


if __name__ == "__main__":
    unittest.main()
