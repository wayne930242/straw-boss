from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


ALPHA = "wA:p1"
BETA = "wB:p1"


def agent(
    pane_id: str,
    session: str | None,
    *,
    name: str | None = None,
    kind: str = "claude",
    status: str = "idle",
    cwd: str = "/repo",
) -> dict[str, object]:
    record: dict[str, object] = {
        "agent": kind,
        "agent_status": status,
        "pane_id": pane_id,
        "terminal_id": f"terminal-{pane_id}",
        "cwd": cwd,
    }
    if session is not None:
        record["agent_session"] = {"value": session}
    if name is not None:
        record["name"] = name
    return record


ALPHA_AGENT = agent(ALPHA, "orchestrator-a", name="orchestrator-alpha")
BETA_AGENT = agent(BETA, "orchestrator-b", name="orchestrator-beta")


class OrchestratorDirectoryTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def run_directory_script(
        self,
        script_name: str,
        *args: str,
        agents: list[dict[str, object]],
        pane_id: str | None = None,
        sessions: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        fake_bin, capture = self.install_fake_herdr()
        self.capture = capture
        live_sessions = {
            str(one["pane_id"]): (one.get("agent_session") or {}).get("value")
            for one in agents
        }
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PROCESS_INFOS": json.dumps(getattr(self, "process_infos", {})),
            "HERDR_AGENT_LIST": json.dumps(agents),
            "HERDR_SESSIONS": json.dumps(sessions if sessions is not None else live_sessions),
            "HERDR_AGENT_KINDS": json.dumps(
                {str(one["pane_id"]): str(one["agent"]) for one in agents}
            ),
            "HERDR_TERMINAL_IDS": json.dumps(
                {str(one["pane_id"]): str(one["terminal_id"]) for one in agents}
            ),
            "HERDR_AGENT_STATUSES": json.dumps(
                {str(one["pane_id"]): str(one["agent_status"]) for one in agents}
            ),
        }
        if pane_id is not None:
            env["HERDR_PANE_ID"] = pane_id
        return self.run_script(script_name, *args, extra_env=env)

    def register(
        self,
        scope: str,
        *,
        pane_id: str,
        agents: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        result = self.run_directory_script(
            "register-orchestrator.py",
            "--scope",
            scope,
            agents=agents if agents is not None else [ALPHA_AGENT, BETA_AGENT],
            pane_id=pane_id,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def send(
        self,
        *args: str,
        pane_id: str,
        agents: list[dict[str, object]] | None = None,
        sessions: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self.run_directory_script(
            "send-orchestrator-message.py",
            *args,
            agents=agents if agents is not None else [ALPHA_AGENT, BETA_AGENT],
            pane_id=pane_id,
            sessions=sessions,
        )

    def records(self) -> list[Path]:
        return sorted((self.home / ".straw-boss" / "orchestrators").glob("*.json"))

    def ledger(self, fingerprint: str) -> list[dict[str, object]]:
        path = (
            self.home
            / ".straw-boss"
            / "orchestrators"
            / f"claude-{fingerprint}.messages.jsonl"
        )
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def prompts(self) -> list[list[str]]:
        calls = [
            json.loads(line)
            for line in self.capture.read_text().splitlines()
            if line.strip()
        ]
        return [call for call in calls if call[:2] == ["agent", "prompt"]]

    def install_claude_session(self, pane: str, session: object, **overrides: object) -> None:
        pid = 4242
        self.process_infos = {
            pane: {
                "pane_id": pane,
                "foreground_process_group_id": pid,
                "foreground_processes": [{"pid": pid, "argv0": "claude"}],
            }
        }
        root = self.home / ".claude" / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        record = {"pid": pid, "sessionId": session, "kind": "interactive", "entrypoint": "cli"}
        record.update(overrides)
        (root / f"{pid}.json").write_text(json.dumps(record))

    def test_missing_title_session_registers_lists_and_sends_both_ways(self) -> None:
        self.install_claude_session(BETA, "orchestrator-b")
        agents = [ALPHA_AGENT, agent(BETA, None, name="orchestrator-beta")]
        output = self.register("缺少 title 的協調者", pane_id=BETA, agents=agents)
        self.assertEqual(output["record"]["session_id"], "orchestrator-b")
        self.register("測試協調者", pane_id=ALPHA, agents=agents)
        listed = self.run_directory_script("register-orchestrator.py", "--list", agents=agents)
        row = next(row for row in json.loads(listed.stdout)["directory"] if row["session_id"] == "orchestrator-b")
        self.assertTrue(row["live"])
        for source, target in ((ALPHA, BETA), (BETA, ALPHA)):
            result = self.send("--to", target, "--intent", "inform", "--message", "驗證 session 定址。", pane_id=source, agents=agents)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["submitted"])
            self.assertEqual(self.prompts()[-1][2], target)

    def test_missing_title_rejects_unverified_registry(self) -> None:
        for overrides in ({"pid": 999}, {"kind": "sdk"}, {"entrypoint": "sdk"}, {"sessionId": ""}, {"sessionId": 42}):
            with self.subTest(overrides=overrides):
                self.install_claude_session(BETA, "orchestrator-b", **overrides)
                result = self.run_directory_script("register-orchestrator.py", "--scope", "測試", agents=[agent(BETA, None)], pane_id=BETA)
                self.assertEqual(result.returncode, 1)
                self.assertIn("cannot be addressed", result.stderr)
                self.assertEqual(self.records(), [])

    def test_missing_title_without_registry_is_unaddressable(self) -> None:
        self.register("既有接收端", pane_id=BETA)
        agents = [agent(BETA, None)]
        result = self.run_directory_script("register-orchestrator.py", "--scope", "測試", agents=agents, pane_id=BETA)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cannot be addressed", result.stderr)
        listed = self.run_directory_script("register-orchestrator.py", "--list", agents=agents)
        row = json.loads(listed.stdout)["directory"][0]
        self.assertFalse(row["live"])
        self.assertIn("verified", row["unavailable_reason"])

    def test_missing_title_replacement_session_does_not_receive_old_address(self) -> None:
        self.install_claude_session(BETA, "orchestrator-b")
        agents = [ALPHA_AGENT, agent(BETA, None)]
        self.register("接收端", pane_id=BETA, agents=agents)
        self.register("發送端", pane_id=ALPHA, agents=agents)
        self.install_claude_session(BETA, "replacement-session")
        result = self.send("--to", BETA, "--intent", "inform", "--message", "驗證替換。", pane_id=ALPHA, agents=agents)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["submitted"])
        self.assertEqual(self.prompts(), [])

    def test_registering_records_this_session_and_returns_the_live_directory(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)

        output = self.register("Repairing this plugin.", pane_id=ALPHA)

        self.assertEqual(
            [path.name for path in self.records()],
            ["claude-orchestrator-a.json", "claude-orchestrator-b.json"],
        )
        record = json.loads((self.home / ".straw-boss" / "orchestrators" / "claude-orchestrator-a.json").read_text())
        self.assertEqual(record["scope"], "Repairing this plugin.")
        self.assertEqual(record["herdr_pane_id"], ALPHA)
        self.assertEqual(record["name"], "orchestrator-alpha")
        self.assertEqual(record["cwd"], "/repo")
        peer = next(
            row for row in output["directory"] if row["name"] == "orchestrator-beta"
        )
        self.assertEqual(peer["scope"], "Coordinating the billing app.")
        self.assertEqual(peer["herdr_pane_id"], BETA)
        self.assertTrue(peer["live"])

    def test_re_registering_updates_the_same_record(self) -> None:
        first = self.register("Repairing this plugin.", pane_id=ALPHA)

        self.register("Repairing this plugin and its docs.", pane_id=ALPHA)

        self.assertEqual([path.name for path in self.records()], ["claude-orchestrator-a.json"])
        record = json.loads(self.records()[0].read_text())
        self.assertEqual(record["scope"], "Repairing this plugin and its docs.")
        self.assertEqual(record["registered_at"], first["record"]["registered_at"])

    def test_registering_needs_a_live_agent_in_this_pane(self) -> None:
        without_pane = self.run_directory_script(
            "register-orchestrator.py",
            "--scope",
            "Repairing this plugin.",
            agents=[ALPHA_AGENT],
            pane_id="",
        )
        self.assertEqual(without_pane.returncode, 1)
        self.assertIn("HERDR_PANE_ID", without_pane.stderr)

        unknown_pane = self.run_directory_script(
            "register-orchestrator.py",
            "--scope",
            "Repairing this plugin.",
            agents=[BETA_AGENT],
            pane_id=ALPHA,
        )
        self.assertEqual(unknown_pane.returncode, 1)
        self.assertIn("no live agent in pane", unknown_pane.stderr)
        self.assertEqual(self.records(), [])

    def test_an_agent_kind_with_no_delivery_path_is_refused(self) -> None:
        result = self.run_directory_script(
            "register-orchestrator.py",
            "--scope",
            "Repairing this plugin.",
            agents=[agent(ALPHA, "orchestrator-a", kind="gemini")],
            pane_id=ALPHA,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("unsupported agent kind", result.stderr)
        self.assertEqual(self.records(), [])

    def test_a_scope_is_one_short_line(self) -> None:
        for scope in ("   ", "first line\nsecond line", "x" * 201):
            result = self.run_directory_script(
                "register-orchestrator.py",
                "--scope",
                scope,
                agents=[ALPHA_AGENT],
                pane_id=ALPHA,
            )
            self.assertEqual(result.returncode, 1, scope)
            self.assertIn("scope", result.stderr)
        self.assertEqual(self.records(), [])

    def test_dispatch_write_auto_registers_an_unregistered_main_agent(self) -> None:
        """A live coordinator that never ran register-orchestrator.py itself is
        still addressable: dispatch-task.py write's own --main-agent-pane-id/
        --main-agent-session-id are enough to seed a record, with no herdr call
        of their own."""
        self.write_dispatch("claude")

        records = self.records()
        self.assertEqual([path.name for path in records], ["claude-main-session.json"])
        record = json.loads(records[0].read_text())
        self.assertEqual(record["session_id"], "main-session")
        self.assertEqual(record["herdr_pane_id"], "main-pane")
        self.assertIn("api", record["scope"])

    def test_dispatch_write_auto_register_never_overwrites_an_explicit_scope(self) -> None:
        self.register(
            "Coordinating the billing app.",
            pane_id="main-pane",
            agents=[agent("main-pane", "main-session")],
        )

        self.write_dispatch("claude")

        records = self.records()
        self.assertEqual(len(records), 1)
        record = json.loads(records[0].read_text())
        self.assertEqual(record["scope"], "Coordinating the billing app.")

    def test_dispatch_write_does_not_auto_register_a_coworkers_own_pane(self) -> None:
        """A coworker's main_agent_* fields are the dispatched worker's own
        pane/session (see resolve_coworker_context), not the root
        orchestrator -- auto-registering from those would put a busy task
        worker into the orchestrator directory as if it coordinated."""
        parent_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(parent_path)

        result = self.write_coworker(parent_path)
        self.assertEqual(result.returncode, 0, result.stderr)

        records = self.records()
        self.assertEqual([path.name for path in records], ["claude-main-session.json"])

    def test_a_record_whose_session_ended_lists_as_not_live_and_is_kept(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)

        result = self.run_directory_script(
            "register-orchestrator.py", "--list", agents=[ALPHA_AGENT]
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["directory"][0]
        self.assertFalse(row["live"])
        self.assertEqual(row["herdr_pane_id"], BETA)
        self.assertEqual(row["scope"], "Coordinating the billing app.")
        self.assertEqual([path.name for path in self.records()], ["claude-orchestrator-b.json"])

    def test_registering_retires_records_whose_session_ended_a_week_ago(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        retired_record = self.records()[0]
        stale = json.loads(retired_record.read_text())
        stale["updated_at"] = (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).isoformat()
        retired_record.write_text(json.dumps(stale))
        ledger = retired_record.with_name("claude-orchestrator-b.messages.jsonl")
        ledger.write_text(json.dumps({"direction": "to-orchestrator"}) + "\n")

        output = self.register(
            "Repairing this plugin.", pane_id=ALPHA, agents=[ALPHA_AGENT]
        )

        self.assertEqual(output["retired"], [str(retired_record)])
        self.assertEqual([path.name for path in self.records()], ["claude-orchestrator-a.json"])
        self.assertTrue(ledger.is_file())

    def test_a_week_old_record_whose_session_is_still_live_is_kept(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        record_path = self.records()[0]
        aged = json.loads(record_path.read_text())
        aged["updated_at"] = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        record_path.write_text(json.dumps(aged))

        output = self.register("Repairing this plugin.", pane_id=ALPHA)

        self.assertEqual(output["retired"], [])
        self.assertEqual(len(self.records()), 2)

    def test_a_delta_reaches_the_other_orchestrator_naming_this_pane(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        self.register("Repairing this plugin.", pane_id=ALPHA)

        result = self.send(
            "--to",
            "orchestrator-beta",
            "--intent",
            "inform",
            "--message",
            "The plugin now installs from the GitHub marketplace source.",
            "--ref",
            "scripts/install.sh",
            pane_id=ALPHA,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        submitted = json.loads(result.stdout)
        self.assertTrue(submitted["submitted"])
        prompt = self.prompts()[-1]
        self.assertEqual(prompt[2], BETA)
        envelope = prompt[3]
        self.assertIn("[orchestrator inform ", envelope)
        self.assertIn(f"id={submitted['message_id']}", envelope)
        self.assertIn("from=orchestrator-alpha", envelope)
        self.assertIn(f"pane={ALPHA}", envelope)
        self.assertIn('refs=["scripts/install.sh"]', envelope)
        self.assertIn(
            "The plugin now installs from the GitHub marketplace source.", envelope
        )
        delivered = self.ledger("orchestrator-b")
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0]["direction"], "to-orchestrator")
        self.assertEqual(delivered[0]["source_session_id"], "orchestrator-a")
        self.assertEqual(delivered[0]["target_session_id"], "orchestrator-b")

    def test_a_message_body_stays_a_delta(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        self.register("Repairing this plugin.", pane_id=ALPHA)

        result = self.send(
            "--to",
            "orchestrator-beta",
            "--intent",
            "inform",
            "--message",
            "One fact. A second fact. A third fact.",
            pane_id=ALPHA,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("at most two sentences", result.stderr)
        self.assertEqual(self.prompts(), [])

    def test_an_unregistered_orchestrator_is_refused(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)

        result = self.send(
            "--to",
            "orchestrator-beta",
            "--intent",
            "inform",
            "--message",
            "This session owns the plugin repair.",
            pane_id=ALPHA,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("unregistered", result.stderr)
        self.assertEqual(self.prompts(), [])

    def test_a_target_pane_holding_another_session_is_refused(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        self.register("Repairing this plugin.", pane_id=ALPHA)

        result = self.send(
            "--to",
            BETA,
            "--intent",
            "inform",
            "--message",
            "This session owns the plugin repair.",
            pane_id=ALPHA,
            sessions={ALPHA: "orchestrator-a", BETA: "somebody-elses-session"},
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("session mismatch", result.stderr)
        self.assertEqual(self.prompts(), [])
        self.assertEqual(self.ledger("orchestrator-b"), [])

    def test_a_target_whose_session_ended_is_recorded_undelivered(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        self.register("Repairing this plugin.", pane_id=ALPHA)

        result = self.send(
            "--to",
            "orchestrator-beta",
            "--intent",
            "inform",
            "--message",
            "This session owns the plugin repair.",
            pane_id=ALPHA,
            agents=[ALPHA_AGENT],
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["submitted"])
        self.assertEqual(self.prompts(), [])
        recorded = self.ledger("orchestrator-b")
        self.assertEqual(len(recorded), 1)
        self.assertFalse(recorded[0]["delivered"])
        self.assertEqual(recorded[0]["message"], "This session owns the plugin repair.")

    def test_an_answer_names_the_question_it_replies_to(self) -> None:
        self.register("Coordinating the billing app.", pane_id=BETA)
        self.register("Repairing this plugin.", pane_id=ALPHA)
        asked = self.send(
            "--to",
            "orchestrator-beta",
            "--intent",
            "question",
            "--message",
            "Does the billing app still pin plugin 0.18.21?",
            pane_id=ALPHA,
        )
        self.assertEqual(asked.returncode, 0, asked.stderr)
        question_id = json.loads(asked.stdout)["message_id"]

        invented = self.send(
            "--to",
            "orchestrator-alpha",
            "--intent",
            "answer",
            "--in-reply-to",
            "00000000-0000-4000-8000-000000000000",
            "--message",
            "It pins 0.18.33.",
            pane_id=BETA,
        )
        self.assertEqual(invented.returncode, 1)
        self.assertIn("unknown peer question", invented.stderr)

        answered = self.send(
            "--to",
            "orchestrator-alpha",
            "--intent",
            "answer",
            "--in-reply-to",
            question_id,
            "--message",
            "It pins 0.18.33.",
            pane_id=BETA,
        )

        self.assertEqual(answered.returncode, 0, answered.stderr)
        envelope = self.prompts()[-1][3]
        self.assertIn("[orchestrator answer ", envelope)
        self.assertIn(f"in-reply-to={question_id}", envelope)
        self.assertIn("from=orchestrator-beta", envelope)
        self.assertIn(f"pane={BETA}", envelope)


if __name__ == "__main__":
    unittest.main()
