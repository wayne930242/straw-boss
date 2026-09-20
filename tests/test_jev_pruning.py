from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from straw_boss import jev_measurement, jev_renewal, jev_storage

ROOT = Path(__file__).resolve().parents[1]


class JevPruningTests(unittest.TestCase):
    def test_existing_storage_is_made_private_before_writing(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRAW_BOSS_HOME": directory}):
            root = Path(directory) / "jev"
            root.mkdir(mode=0o755)
            (root / "runs").mkdir(mode=0o755)
            benchmark = root / "benchmark.jsonl"
            benchmark.write_text("")
            benchmark.chmod(0o644)
            jev_storage.persist({"record": {"run_id": "private", "decisions": []}, "original_messages": []})
            for path in (root, root / "runs"):
                self.assertEqual(path.stat().st_mode & 0o777, 0o700)
            self.assertEqual(benchmark.stat().st_mode & 0o777, 0o600)

    def test_storage_rejects_symlinks_without_changing_targets(self):
        for name in ("jev", "jev/runs", "jev/benchmark.jsonl", "jev/benchmark.lock", "jev/runs/private.json"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRAW_BOSS_HOME": directory}):
                target = Path(directory) / "outside"
                if name in ("jev", "jev/runs"):
                    target.mkdir(mode=0o755)
                else:
                    target.write_text("unchanged")
                link = Path(directory) / name
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(target)
                before = target.stat().st_mode
                with self.assertRaises((OSError, ValueError)):
                    jev_storage.persist({"record": {"run_id": "private", "decisions": []}, "original_messages": []})
                self.assertEqual(target.stat().st_mode, before)
                if target.is_file():
                    self.assertEqual(target.read_text(), "unchanged")
                else:
                    self.assertEqual(list(target.iterdir()), [])

    def test_storage_rejects_hardlinks_special_files_and_foreign_ownership(self):
        for kind in ("hardlink", "fifo", "foreign-owner"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRAW_BOSS_HOME": directory}):
                root = Path(directory) / "jev"
                root.mkdir()
                benchmark = root / "benchmark.jsonl"
                if kind == "hardlink":
                    target = Path(directory) / "target"
                    target.write_text("untouched")
                    os.link(target, benchmark)
                elif kind == "fifo":
                    os.mkfifo(benchmark)
                if kind == "foreign-owner":
                    with patch("straw_boss.jev_private.os.getuid", return_value=os.getuid() + 1):
                        with self.assertRaises(ValueError):
                            jev_storage.persist({"record": {"run_id": "private", "decisions": []}, "original_messages": []})
                    self.assertEqual(list(root.iterdir()), [])
                else:
                    with self.assertRaises((OSError, ValueError)):
                        jev_storage.persist({"record": {"run_id": "private", "decisions": []}, "original_messages": []})
                    if kind == "hardlink":
                        self.assertEqual(target.read_text(), "untouched")

    def test_pair_bytes_vary_with_real_content_and_ignore_mirrored_host_metadata(self):
        call = {"tool_use_id": "a", "tool": "Read", "input": {"file_path": "x"}}
        short = {"tool_use_id": "a", "text": "ok"}
        long = {"tool_use_id": "a", "text": "原文" * 100}
        self.assertGreater(jev_storage.pair_bytes(call, long), jev_storage.pair_bytes(call, short))
        mirrored = {**call, "text": long["text"], "result": {"body": long["text"]}}
        self.assertEqual(jev_storage.pair_bytes(mirrored, long), jev_storage.pair_bytes(call, long))

    def test_measure_counts_native_blocks_and_conservative_full_context_gate(self):
        history = [{"role": "user", "text": "Keep this verbatim", "toolUses": []},
                   {"role": "assistant", "text": "", "toolUses": [
                       {"tool_use_id": "a", "tool": "Read", "input": {"file_path": "x"}}]},
                   {"role": "user", "text": "", "toolUses": [], "toolResults": [
                       {"tool_use_id": "a", "text": "original body"}]}]
        blocks = jev_measurement.native_messages(history)
        self.assertEqual(blocks[1]["content"][0]["type"], "tool_use")
        self.assertEqual(blocks[2]["content"][0]["content"], "original body")
        with patch.object(jev_measurement, "credential_headers", return_value={}), \
             patch.object(jev_measurement, "count_tokens", side_effect=[100, 80]):
            record = jev_measurement.measure({"model": "test", "before": history,
                                               "after": history[:1], "live_input_tokens": 1000})
        self.assertEqual(record["reduction_pct"], 20)
        self.assertEqual(record["gate_reduction_pct"], 2)
        self.assertIsNone(record["measurement"]["actual_session_tokens_after"])

    def test_recovery_keeps_exact_originals_and_pair_byte_accounting(self):
        call = {"tool_use_id": "a", "tool": "Bash", "input": {"command": "once"}}
        result = {"tool_use_id": "a", "text": "one-shot output 原文"}
        original = [{"role": "assistant", "text": "preserved", "toolUses": [call]},
                    {"role": "user", "text": "", "toolUses": [], "toolResults": [result]}]
        candidate = [{"role": "assistant", "text": "preserved", "toolUses": []}]
        record = {"run_id": "test-run", "decisions": [{"id": "t1", "action": "drop_call"}]}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRAW_BOSS_HOME": directory}):
            saved = jev_storage.persist({"record": record, "original_messages": original,
                                         "candidate_messages": candidate})
            recovery = Path(saved["recovery_path"])
            self.assertEqual(json.loads(recovery.read_text())["original_messages"], original)
            rows = Path(saved["benchmark_path"]).read_text().splitlines()
            self.assertEqual(len(rows), 1)
            decision = json.loads(rows[0])["decisions"][0]
            self.assertEqual(decision["original_content"], [call, result])
            self.assertEqual(decision["original_indices"], [0, 1])
            self.assertEqual(decision["bytes_after"], 0)
            self.assertEqual(decision["bytes_before"], jev_storage.pair_bytes(call, result))
            self.assertEqual(recovery.stat().st_mode & 0o777, 0o600)

    def test_missing_or_empty_key_has_no_output_and_no_files(self):
        with tempfile.TemporaryDirectory() as directory:
            for key in (None, "", " "):
                env = {**os.environ, "STRAW_BOSS_JEV": "1", "STRAW_BOSS_HOME": directory}
                env.pop("TYPESAFE_API_KEY", None)
                if key is not None:
                    env["TYPESAFE_API_KEY"] = key
                result = subprocess.run([sys.executable, str(ROOT / "scripts/jev-runtime.py"), "persist"],
                                        input="invalid input", text=True, capture_output=True, env=env)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_application_stays_unverified_until_backend_usage_and_survives_restart(self):
        for after, expected in [(500, "applied"), (1100, None)]:
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"STRAW_BOSS_HOME": directory}):
                record = {"run_id": "test-run", "session_id": "s", "decision": "apply",
                          "outcome": None, "decisions": [], "measurement": {"live_input_tokens_before": 1000}}
                jev_storage.persist({"record": record, "original_messages": [], "candidate_messages": []})
                self.assertEqual(jev_storage.pending("s"), {"run_id": "test-run"})
                jev_storage.observe({"session_id": "s", "run_id": "test-run", "actual_session_tokens_after": after})
                rows = (jev_storage.root() / "benchmark.jsonl").read_text().splitlines()
                self.assertEqual(len(rows), 1)
                self.assertEqual(json.loads(rows[0])["outcome"], expected)
                self.assertIsNone(jev_storage.pending("s"))
                # A repeated observer cannot append another row or overwrite it.
                self.assertFalse(jev_storage.observe({"session_id": "s", "run_id": "test-run",
                                                     "actual_session_tokens_after": 1})["observed"])

    def test_renewal_requires_loaded_current_session_and_key(self):
        env = {"STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "key", "STRAW_BOSS_JEV_READY_SESSION": "s"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(jev_renewal.enabled("claude", "s"))
            self.assertFalse(jev_renewal.enabled("codex", "s"))
            self.assertFalse(jev_renewal.enabled("claude", "other"))
            self.assertEqual(jev_renewal.threshold(), 300000)
            os.environ["TYPESAFE_API_KEY"] = ""
            self.assertFalse(jev_renewal.enabled("claude", "s"))

    def test_old_usage_after_manual_compaction_does_not_trigger_renewal(self):
        old = {"type": "assistant", "message": {"usage": {"input_tokens": 400000}}}
        boundary = {"type": "system", "subtype": "compact_boundary"}
        fresh = {"type": "assistant", "message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": 200000}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transcript.jsonl"
            path.write_text("\n".join(map(json.dumps, [old, boundary])))
            self.assertIsNone(jev_renewal.current_tokens({"transcript_path": str(path)}))
            path.write_text("\n".join(map(json.dumps, [old, boundary, fresh])))
            self.assertEqual(jev_renewal.current_tokens({"transcript_path": str(path)}), 200010)


if __name__ == "__main__":
    unittest.main()
