from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from straw_boss import renewal
from tests.dispatched_agent_lifecycle_support import ROOT, SCRIPTS, DispatchedAgentLifecycleFixture


def varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def field(number: int, value: int | bytes) -> bytes:
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    return varint(number << 3 | 2) + varint(len(value)) + value


def agy_generation(uncached: int, cached: int | None) -> bytes:
    counts = field(1, 1319) + field(2, uncached) + field(3, 305)
    if cached is not None:
        counts += field(5, cached)
    return field(1, field(3, 1319) + field(4, counts)) + field(3, field(1, 1318))


class ContextRenewalTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def env(self, **extra: str) -> dict[str, str]:
        env = {**os.environ, "HOME": str(self.home)}
        env.pop("HERDR_PANE_ID", None)
        env.update(extra)
        return env

    def hook(
        self, script: str, payload: dict[str, Any], **extra: str
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script)],
            input=json.dumps(payload),
            cwd=ROOT,
            env=self.env(**extra),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def claude_transcript(self, tokens: int) -> Path:
        path = self.home / "claude.jsonl"
        usage = {"input_tokens": 10, "cache_read_input_tokens": tokens - 20, "cache_creation_input_tokens": 10}
        lines = [
            {"type": "assistant", "message": {"usage": {"input_tokens": 1}}},
            {"type": "assistant", "message": {"usage": usage}},
            {"type": "assistant", "isSidechain": True, "message": {"usage": {"input_tokens": 5}}},
            {"type": "user", "message": {}},
        ]
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        return path

    def write_record(self, pane: str, **fields: Any) -> Path:
        path = self.home / ".straw-boss" / "renewal" / f"pane-{pane}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "pane_id": pane,
            "agent_kind": "claude",
            "session_id": "old-session",
            "role": "standalone-worker",
            "payload": "Next action: run the suite.",
            "instruction_paths": [],
            "status": "pending",
            **fields,
        }
        path.write_text(json.dumps(record))
        return path

    # --- measurement ---

    def test_claude_measure_reads_the_last_main_thread_usage(self) -> None:
        self.assertEqual(renewal.claude_context_tokens(self.claude_transcript(250_000)), 250_000)

    def test_codex_measure_reads_the_last_token_count(self) -> None:
        path = self.home / "rollout-x.jsonl"
        events = [
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 5}}}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 218_149}}}},
            {"type": "response_item", "payload": {"type": "message"}},
        ]
        path.write_text("".join(json.dumps(event) + "\n" for event in events))
        self.assertEqual(renewal.codex_context_tokens(path), 218_149)
        self.assertEqual(renewal.payload_agent_kind({"transcript_path": str(path)}), "codex")

    def test_agy_measure_adds_uncached_and_cached_input(self) -> None:
        self.assertEqual(renewal.agy_usage_tokens(agy_generation(4900, 77473)), 82373)
        self.assertEqual(renewal.agy_usage_tokens(agy_generation(17637, None)), 17637)
        self.assertIsNone(renewal.agy_usage_tokens(b"\xff\xff"))

        database = self.home / ".gemini" / "antigravity-cli" / "conversations" / "conv-1.db"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE gen_metadata (idx integer primary key, data blob, size integer)")
            connection.execute("INSERT INTO gen_metadata VALUES (0, ?, 0)", (agy_generation(10, 10),))
            connection.execute("INSERT INTO gen_metadata VALUES (1, ?, 0)", (agy_generation(1000, 205_000),))
        payload = {"conversationId": "conv-1"}
        self.assertEqual(renewal.payload_agent_kind(payload), "agy")
        original_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.home)
        try:
            self.assertEqual(renewal.context_tokens(payload, "agy"), 206_000)
        finally:
            os.environ["HOME"] = original_home or ""

    # --- stop guard ---

    def test_guard_lets_a_small_turn_end(self) -> None:
        result = self.hook(
            "context-renewal-guard.py",
            {"session_id": "s1", "transcript_path": str(self.claude_transcript(150_000))},
        )
        self.assertEqual(result.stdout, "")

    def test_guard_asks_a_large_turn_to_renew_once(self) -> None:
        payload = {"session_id": "s1", "transcript_path": str(self.claude_transcript(250_000))}
        blocked = json.loads(self.hook("context-renewal-guard.py", payload).stdout)
        self.assertEqual(blocked["decision"], "block")
        self.assertIn("renew-context.py --agent-kind claude --session-id s1", blocked["reason"])
        self.assertNotIn("?", blocked["reason"].split("Renew now")[1].split("Pipe")[0])

        again = self.hook("context-renewal-guard.py", {**payload, "stop_hook_active": True})
        self.assertEqual(again.stdout, "")

    def test_agy_guard_lets_the_same_turn_end_after_one_block(self) -> None:
        database = self.home / ".gemini" / "antigravity-cli" / "conversations" / "conv-2.db"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE gen_metadata (idx integer primary key, data blob, size integer)")
            connection.execute("INSERT INTO gen_metadata VALUES (0, ?, 0)", (agy_generation(1000, 250_000),))
        payload = {"conversationId": "conv-2", "workspacePaths": [str(self.home)]}
        first = json.loads(self.hook("context-renewal-guard.py", payload).stdout)
        self.assertIn("--agent-kind agy", first["reason"])
        self.assertEqual(self.hook("context-renewal-guard.py", payload).stdout, "")

    def test_renewal_writes_the_record_and_lets_the_turn_end(self) -> None:
        transcript = self.claude_transcript(250_000)
        written = subprocess.run(
            [sys.executable, str(SCRIPTS / "renew-context.py"), "--agent-kind", "claude",
             "--session-id", "s1", "--role", "standalone-worker"],
            input="Goal: ship.\nNext action: run the suite.",
            cwd=self.home,
            env=self.env(),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertEqual(len(written.stdout.strip().splitlines()), 1)
        self.assertIn("run /clear", written.stdout)
        record_path = Path(written.stdout.split("record ")[1].split(";")[0])
        record = json.loads(record_path.read_text())
        self.assertEqual(record["role"], "standalone-worker")
        self.assertEqual(record["status"], "pending")

        payload = {"session_id": "s1", "cwd": str(self.home), "transcript_path": str(transcript)}
        self.assertEqual(self.hook("context-renewal-guard.py", payload).stdout, "")

    def test_renewed_session_above_threshold_reports_once(self) -> None:
        self.write_record("p1", status="consumed", consumed_by="s2")
        payload = {"session_id": "s2", "transcript_path": str(self.claude_transcript(260_000))}
        first = json.loads(self.hook("context-renewal-guard.py", payload, HERDR_PANE_ID="p1").stdout)
        self.assertIn("do not renew again", first["reason"])
        self.assertEqual(self.hook("context-renewal-guard.py", payload, HERDR_PANE_ID="p1").stdout, "")

    def test_renewed_session_renews_again_after_settling_below_threshold(self) -> None:
        self.write_record("p1", status="consumed", consumed_by="s2")
        small = {"session_id": "s2", "transcript_path": str(self.claude_transcript(90_000))}
        self.assertEqual(self.hook("context-renewal-guard.py", small, HERDR_PANE_ID="p1").stdout, "")
        large = {"session_id": "s2", "transcript_path": str(self.claude_transcript(260_000))}
        reason = json.loads(self.hook("context-renewal-guard.py", large, HERDR_PANE_ID="p1").stdout)["reason"]
        self.assertIn("renew-context.py", reason)

    def test_dispatched_worker_renewal_checkpoints_and_passes_the_stop_guard(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(instruction_path, pane="worker-pane", session="worker-session")
        stop = {"session_id": "worker-session"}
        blocked = self.hook("dispatched-agent-stop-guard.py", stop, HERDR_PANE_ID="worker-pane")
        self.assertIn("block", blocked.stdout)

        fake_bin, capture = self.install_fake_herdr()
        written = subprocess.run(
            [sys.executable, str(SCRIPTS / "renew-context.py"), "--agent-kind", "claude",
             "--session-id", "worker-session", "--role", "dispatched-worker",
             "--instruction-path", str(instruction_path)],
            input="Next action: finish the slice.",
            cwd=ROOT,
            env=self.env(
                HERDR_PANE_ID="worker-pane",
                PATH=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                HERDR_CAPTURE=str(capture),
            ),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertIn("clears after the turn ends", written.stdout)
        progress = instruction_path.with_name(instruction_path.name.removesuffix(".json") + ".progress.jsonl")
        self.assertIn("Context renewal checkpoint", progress.read_text())
        self.assertEqual(
            self.hook("dispatched-agent-stop-guard.py", stop, HERDR_PANE_ID="worker-pane").stdout, ""
        )

    # --- SessionStart ---

    def test_session_start_injects_a_record_once_in_its_own_pane(self) -> None:
        path = self.write_record("p1")
        payload = {"session_id": "new-session", "source": "clear"}

        elsewhere = self.hook("orchestrator-priming.py", payload, HERDR_PANE_ID="p2")
        self.assertNotIn("Next action: run the suite.", elsewhere.stdout)

        renewed = self.hook("orchestrator-priming.py", payload, HERDR_PANE_ID="p1")
        self.assertIn("Next action: run the suite.", renewed.stdout)
        self.assertIn("standalone-worker", renewed.stdout)
        self.assertNotIn("Use the smallest sufficient loop", renewed.stdout)
        self.assertEqual(json.loads(path.read_text())["consumed_by"], "new-session")

        again = self.hook("orchestrator-priming.py", {**payload, "session_id": "third"}, HERDR_PANE_ID="p1")
        self.assertNotIn("Next action: run the suite.", again.stdout)

    def test_agy_session_start_emits_its_structured_result(self) -> None:
        self.write_record("p1", agent_kind="agy")
        result = self.hook(
            "orchestrator-priming.py",
            {"conversationId": "new-conversation", "workspacePaths": [str(self.home)]},
            HERDR_PANE_ID="p1",
        )
        steps = json.loads(result.stdout)["injectSteps"]
        self.assertIn("Next action: run the suite.", steps[0]["ephemeralMessage"])

    def test_session_start_ignores_a_record_of_another_provider(self) -> None:
        self.write_record("p1", agent_kind="codex")
        result = self.hook("orchestrator-priming.py", {"session_id": "new-session"}, HERDR_PANE_ID="p1")
        self.assertNotIn("Next action: run the suite.", result.stdout)

    def test_clear_without_a_record_primes_as_today(self) -> None:
        result = self.hook("orchestrator-priming.py", {"session_id": "fresh", "source": "clear"}, HERDR_PANE_ID="p1")
        self.assertIn("Use the smallest sufficient loop", " ".join(result.stdout.replace("`", "").split()))
        self.assertNotIn("Context renewal", result.stdout)

    def renewal_env(self, pane: str) -> dict[str, str]:
        fake_bin, capture = self.install_fake_herdr()
        return {
            "HERDR_PANE_ID": pane,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PROCESS_INFO_CALLER": "1",
        }

    def test_renewed_main_agent_adopts_its_dispatches_and_directory_entry(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(instruction_path)
        instruction = json.loads(instruction_path.read_text())
        old_main = instruction["main_agent_session_id"]
        registry = self.home / ".straw-boss" / "orchestrators"
        registry.mkdir(parents=True, exist_ok=True)
        (registry / f"claude-{old_main}.json").write_text(
            json.dumps({"agent_kind": "claude", "session_id": old_main, "scope": "Ship renewal"})
        )
        self.write_record(
            "main-pane", session_id=old_main, role="main-agent",
            instruction_paths=[str(instruction_path)],
        )

        result = self.hook(
            "orchestrator-priming.py", {"session_id": "renewed-main", "source": "clear"},
            **self.renewal_env("main-pane"),
        )
        self.assertIn("Use the smallest sufficient loop", " ".join(result.stdout.replace("`", "").split()))
        self.assertIn(str(instruction_path), result.stdout)
        adopted = json.loads(instruction_path.read_text())
        self.assertEqual(adopted["main_agent_session_id"], "renewed-main")
        self.assertEqual(adopted["main_agent_adoptions"][-1]["reason"], "context-renewal")
        self.assertEqual(adopted["session_id"], "worker-session")
        moved = json.loads((registry / "claude-renewed-main.json").read_text())
        self.assertEqual(moved["scope"], "Ship renewal")
        self.assertFalse((registry / f"claude-{old_main}.json").exists())

    def test_renewed_worker_adopts_only_its_own_route(self) -> None:
        mine, _ = self.write_dispatch("claude", slug="mine")
        self.set_worker_endpoint(mine, pane="worker-pane", session="worker-session")
        other, _ = self.write_dispatch("claude", slug="other")
        self.set_worker_endpoint(other, pane="other-pane", session="worker-session")
        self.write_record(
            "worker-pane", session_id="worker-session", role="dispatched-worker",
            instruction_paths=[str(mine)],
        )

        result = self.hook(
            "orchestrator-priming.py", {"session_id": "renewed-worker", "source": "clear"},
            **self.renewal_env("worker-pane"),
        )
        self.assertIn("report-task-status.py", result.stdout)
        self.assertNotIn("Use the smallest sufficient loop", " ".join(result.stdout.replace("`", "").split()))
        self.assertEqual(json.loads(mine.read_text())["session_id"], "renewed-worker")
        self.assertEqual(json.loads(mine.read_text())["worker_adoptions"][-1]["before"]["session_id"], "worker-session")
        self.assertEqual(json.loads(other.read_text())["session_id"], "worker-session")

        stop = self.hook("dispatched-agent-stop-guard.py", {"session_id": "renewed-worker"})
        self.assertIn("block", stop.stdout)

    def test_adoption_refuses_a_caller_outside_the_pane(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(instruction_path, pane="worker-pane", session="worker-session")
        self.write_record("worker-pane", session_id="worker-session", role="dispatched-worker")
        env = self.renewal_env("worker-pane")
        env.pop("HERDR_PROCESS_INFO_CALLER")
        result = self.hook("orchestrator-priming.py", {"session_id": "intruder"}, **env)
        self.assertIn("not adopted", result.stdout)
        self.assertEqual(json.loads(instruction_path.read_text())["session_id"], "worker-session")

    def test_hook_registrations_include_the_renewal_guard(self) -> None:
        claude = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        self.assertTrue(any(
            "context-renewal-guard.py" in hook["command"]
            for entry in claude["hooks"]["Stop"] for hook in entry["hooks"]
        ))
        agy = json.loads((ROOT / "hooks.json").read_text())["straw-boss"]
        self.assertTrue(agy["enabled"])
        for event in ("SessionStart", "Stop"):
            self.assertTrue(all(hook["type"] == "command" and hook["command"] for hook in agy[event]))
        self.assertTrue(any("context-renewal-guard.py" in hook["command"] for hook in agy["Stop"]))


if __name__ == "__main__":
    unittest.main()
