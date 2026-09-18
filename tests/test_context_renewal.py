from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
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

    def test_rewritten_renewal_clears_its_pane_once(self) -> None:
        fake_bin = self.home / "gated-bin"
        fake_bin.mkdir()
        capture = self.home / "herdr-calls.jsonl"
        turn_end = self.home / "turn-ended"
        (fake_bin / "herdr").write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys, time\n"
            "with open(os.environ['HERDR_CAPTURE'], 'a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1:3] == ['agent', 'wait']:\n"
            "    while not pathlib.Path(os.environ['HERDR_TURN_END']).exists():\n"
            "        time.sleep(0.05)\n"
        )
        (fake_bin / "herdr").chmod(0o755)
        env = self.env(
            PATH=f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            HERDR_CAPTURE=str(capture),
            HERDR_TURN_END=str(turn_end),
        )
        deliver = [sys.executable, str(SCRIPTS / "deliver-renewal.py"), "--pane-id", "p1"]

        def calls() -> list[list[str]]:
            return [json.loads(line) for line in capture.read_text().splitlines()] if capture.exists() else []

        first = subprocess.Popen(deliver, cwd=ROOT, env=env)
        deadline = time.monotonic() + 10
        while not any(call[:2] == ["agent", "wait"] for call in calls()):
            self.assertLess(time.monotonic(), deadline, "the first deliverer never waited")
            time.sleep(0.05)
        second = subprocess.Popen(deliver, cwd=ROOT, env=env)
        try:
            self.assertEqual(second.wait(timeout=5), 0)
        finally:
            turn_end.touch()
            first.wait(timeout=10)
            second.wait(timeout=10)

        clears = [call for call in calls() if call == ["agent", "prompt", "p1", renewal.CLEAR_COMMAND]]
        self.assertEqual(len(clears), 1)

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

        # "new-session" confirms by reaching its own Stop below the threshold,
        # so a further SessionStart in the pane can no longer take the record.
        self.assertEqual(
            self.hook(
                "context-renewal-guard.py",
                {"session_id": "new-session", "transcript_path": str(self.claude_transcript(50_000))},
                HERDR_PANE_ID="p1",
            ).stdout,
            "",
        )
        self.assertTrue(json.loads(path.read_text())["confirmed"])

        again = self.hook("orchestrator-priming.py", {**payload, "session_id": "third"}, HERDR_PANE_ID="p1")
        self.assertNotIn("Next action: run the suite.", again.stdout)

    def test_a_throwaway_session_that_never_turns_cannot_strand_the_record(self) -> None:
        """Reproduces the 2026-09-18 pane wF:p5R incident: a duplicated /clear
        starts a second session in the same pane a moment after the first,
        before the first ever reaches its own Stop. The record must not be
        stuck consumed_by the throwaway session that never ran a turn."""
        path = self.write_record("p1")
        payload = {"session_id": "throwaway", "source": "clear"}

        first = self.hook("orchestrator-priming.py", payload, HERDR_PANE_ID="p1")
        self.assertIn("Next action: run the suite.", first.stdout)
        record = json.loads(path.read_text())
        self.assertEqual(record["consumed_by"], "throwaway")
        self.assertFalse(record["confirmed"])

        # "throwaway" is cleared away again without ever reaching Stop; the
        # session that the continue prompt actually lands on must still get it.
        second = self.hook("orchestrator-priming.py", {**payload, "session_id": "real"}, HERDR_PANE_ID="p1")
        self.assertIn("Next action: run the suite.", second.stdout)
        record = json.loads(path.read_text())
        self.assertEqual(record["consumed_by"], "real")
        self.assertFalse(record["confirmed"])

        # once "real" reaches its own Stop, the record is confirmed and a
        # further SessionStart in the pane can no longer take it.
        self.assertEqual(
            self.hook(
                "context-renewal-guard.py",
                {"session_id": "real", "transcript_path": str(self.claude_transcript(50_000))},
                HERDR_PANE_ID="p1",
            ).stdout,
            "",
        )
        self.assertTrue(json.loads(path.read_text())["confirmed"])
        intruder = self.hook("orchestrator-priming.py", {**payload, "session_id": "intruder"}, HERDR_PANE_ID="p1")
        self.assertNotIn("Next action: run the suite.", intruder.stdout)

    def test_reclaimed_main_agent_adopts_routes_a_throwaway_claim_already_moved(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(instruction_path)
        instruction = json.loads(instruction_path.read_text())
        old_main = instruction["main_agent_session_id"]
        self.write_record(
            "main-pane", session_id=old_main, role="main-agent",
            instruction_paths=[str(instruction_path)],
        )
        env = self.renewal_env("main-pane")

        self.hook("orchestrator-priming.py", {"session_id": "throwaway", "source": "clear"}, **env)
        self.assertEqual(json.loads(instruction_path.read_text())["main_agent_session_id"], "throwaway")

        self.hook("orchestrator-priming.py", {"session_id": "real", "source": "clear"}, **env)
        adopted = json.loads(instruction_path.read_text())
        self.assertEqual(adopted["main_agent_session_id"], "real")
        self.assertEqual(adopted["main_agent_adoptions"][-1]["before"], {"main_agent_session_id": "throwaway"})

    def test_record_outside_herdr_is_claimed_only_by_a_prompt_clear(self) -> None:
        from datetime import datetime, timedelta, timezone

        key = renewal.record_key(None, str(self.home), "claude")
        path = self.home / ".straw-boss" / "renewal" / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        base = {"pane_id": None, "agent_kind": "claude", "session_id": "old", "role": "standalone-worker",
                "payload": "Next action: run the suite.", "instruction_paths": [], "status": "pending"}
        stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        path.write_text(json.dumps({**base, "created_at": stale}))
        payload = {"session_id": "new", "cwd": str(self.home), "source": "clear"}
        self.assertNotIn("Next action", self.hook("orchestrator-priming.py", payload).stdout)

        path.write_text(json.dumps({**base, "created_at": datetime.now(timezone.utc).isoformat()}))
        startup = {**payload, "source": "startup"}
        self.assertNotIn("Next action", self.hook("orchestrator-priming.py", startup).stdout)
        self.assertIn("Next action", self.hook("orchestrator-priming.py", payload).stdout)

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
        question = json.dumps({"intent": "question", "message_id": "asked-before-clear"}) + "\n"
        (registry / f"claude-{old_main}.messages.jsonl").write_text(question)
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
        self.assertEqual((registry / "claude-renewed-main.messages.jsonl").read_text(), question)
        self.assertFalse((registry / f"claude-{old_main}.messages.jsonl").exists())
        lineage = [json.loads(line) for line in (self.home / ".straw-boss" / "renewal" / "lineage.jsonl").read_text().splitlines()]
        self.assertEqual(
            [(hop["pane_id"], hop["old_session_id"], hop["new_session_id"]) for hop in lineage],
            [("main-pane", old_main, "renewed-main")],
        )

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

    def dispatch_with_coworker(self) -> tuple[Path, Path]:
        parent, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(parent, pane="worker-pane", session="worker-session")
        written = self.write_coworker(parent)
        self.assertEqual(written.returncode, 0, written.stderr)
        child = Path(json.loads(written.stdout)["instruction_path"])
        self.set_worker_endpoint(child, pane="coworker-pane", session="coworker-session")
        return parent, child

    def test_renewed_main_agent_moves_its_coworkers_root_route(self) -> None:
        parent, child = self.dispatch_with_coworker()
        self.write_record(
            "main-pane", session_id="main-session", role="main-agent",
            instruction_paths=[str(parent)],
        )

        self.hook(
            "orchestrator-priming.py", {"session_id": "renewed-main", "source": "clear"},
            **self.renewal_env("main-pane"),
        )

        coworker = json.loads(child.read_text())
        self.assertEqual(coworker["root_main_agent_session_id"], "renewed-main")
        self.assertEqual(coworker["root_main_agent_adoptions"][-1]["reason"], "context-renewal")
        self.assertEqual(coworker["main_agent_session_id"], "worker-session")
        self.assertEqual(json.loads(parent.read_text())["main_agent_session_id"], "renewed-main")

    def test_renewed_parent_worker_moves_its_coworkers_main_route(self) -> None:
        parent, child = self.dispatch_with_coworker()
        self.write_record(
            "worker-pane", session_id="worker-session", role="dispatched-worker",
            instruction_paths=[str(parent)],
        )

        self.hook(
            "orchestrator-priming.py", {"session_id": "renewed-worker", "source": "clear"},
            **self.renewal_env("worker-pane"),
        )

        coworker = json.loads(child.read_text())
        self.assertEqual(coworker["main_agent_session_id"], "renewed-worker")
        self.assertEqual(
            coworker["main_agent_adoptions"][-1]["before"], {"main_agent_session_id": "worker-session"}
        )
        self.assertEqual(coworker["root_main_agent_session_id"], "main-session")
        self.assertEqual(coworker["session_id"], None)
        self.assertEqual(json.loads(parent.read_text())["session_id"], "renewed-worker")

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
