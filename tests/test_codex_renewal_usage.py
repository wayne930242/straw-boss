"""Comparable per-renewal Codex usage records, independent of whether Jev ran.

Design: docs/specs/2026-09-21-codex-renewal-usage-records/design.md.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from straw_boss import renewal_usage
from straw_boss.jev_private import private_replace, root as jev_root
from tests.dispatched_agent_lifecycle_support import ROOT, SCRIPTS, DispatchedAgentLifecycleFixture


def token_count_row(input_tokens: int, cached: int = 0, output: int = 0) -> dict:
    return {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {
        "input_tokens": input_tokens, "cached_input_tokens": cached,
        "cache_write_input_tokens": 0, "output_tokens": output,
        "reasoning_output_tokens": 0, "total_tokens": input_tokens + output}}}}


def compacted_row() -> dict:
    return {"type": "compacted", "payload": {"message": "", "replacement_history": []}}


class CodexRenewalUsageTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def env(self, **extra: str) -> dict[str, str]:
        env = {**os.environ, "HOME": str(self.home), "STRAW_BOSS_HOME": str(self.home / ".straw-boss")}
        env.pop("HERDR_PANE_ID", None)
        env.pop("STRAW_BOSS_JEV", None)
        env.pop("TYPESAFE_API_KEY", None)
        env.update(extra)
        return env

    def transcript(self, rows: list[dict], name: str = "rollout-x.jsonl") -> Path:
        path = self.home / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return path

    def hook(self, payload: dict, **extra: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "context-renewal-guard.py")],
            input=json.dumps(payload), cwd=ROOT, env=self.env(**extra),
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def usage_lines(self) -> list[dict]:
        path = self.home / ".straw-boss" / "renewal" / "codex-usage.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def write_continuity(self, pane: str, **fields: object) -> Path:
        path = self.home / ".straw-boss" / "renewal" / f"pane-{pane}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "pane_id": pane, "agent_kind": "codex", "session_id": "old-session",
            "role": "standalone-worker", "payload": "Next action: run the suite.",
            "instruction_paths": [], "status": "consumed", "consumed_by": "new-session",
            "confirmed": True, **fields,
        }
        path.write_text(json.dumps(record))
        return path

    # --- guard integration: ordinary renewal (Jev fully off) ---

    def test_ordinary_renewal_records_usage_with_jev_disabled(self) -> None:
        transcript = self.transcript([token_count_row(52_000, cached=1_000, output=812)])
        self.write_continuity("p1")
        payload = {"session_id": "new-session", "transcript_path": str(transcript)}

        self.assertEqual(self.usage_lines(), [])
        self.hook(payload, HERDR_PANE_ID="p1")
        lines = self.usage_lines()
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(entry["kind"], "renewal")
        self.assertEqual(entry["path"], "ordinary-jev-off")
        self.assertEqual(entry["path_reason"], "disabled")
        self.assertIsNone(entry["jev"])
        self.assertEqual(entry["old_session_id"], "old-session")
        self.assertEqual(entry["new_session_id"], "new-session")
        self.assertEqual(entry["post_renewal"], {
            "window": "first-stop-of-renewed-session",
            "input_tokens": 52_000, "cached_input_tokens": 1_000, "output_tokens": 812,
        })

        # A second Stop in the same renewed session does not duplicate the line.
        self.hook(payload, HERDR_PANE_ID="p1")
        self.assertEqual(len(self.usage_lines()), 1)

    def test_ordinary_renewal_reports_blank_key_reason(self) -> None:
        transcript = self.transcript([token_count_row(10_000)])
        self.write_continuity("p1")
        payload = {"session_id": "new-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p1", STRAW_BOSS_JEV="1", TYPESAFE_API_KEY="  ")
        entry = self.usage_lines()[0]
        self.assertEqual(entry["path"], "ordinary-jev-off")
        self.assertEqual(entry["path_reason"], "blank-api-key")

    # --- guard integration: Jev-attempted paths ---

    def _jev_fixture(self, run_id: str, **archive_kwargs: object) -> str:
        with mock.patch.dict(os.environ, {"STRAW_BOSS_HOME": str(self.home / ".straw-boss")}):
            archive(run_id, **archive_kwargs)
            return request(run_id)

    def test_jev_applied_renewal_recorded_through_the_real_guard(self) -> None:
        jev_request = self._jev_fixture(
            "run-apply", decision="apply", fallback_reason=None,
            measurement={
                "baseline_resume_usage": {"input_tokens": 200_001, "cached_input_tokens": 0, "output_tokens": 4},
                "candidate_resume_usage": {"input_tokens": 118_000, "cached_input_tokens": 0, "output_tokens": 4},
            },
        )
        transcript = self.transcript([token_count_row(30_000, cached=500, output=200)])
        self.write_continuity("p4", jev_request=jev_request, jev_candidate_session="new-session")
        payload = {"session_id": "new-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p4", STRAW_BOSS_JEV="1", TYPESAFE_API_KEY="test-key")

        lines = [e for e in self.usage_lines() if e["kind"] == "renewal"]
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(entry["path"], "jev-applied")
        self.assertIsNone(entry["path_reason"])
        self.assertEqual(entry["jev"]["input_tokens"], 210)
        self.assertEqual(entry["jev"]["probe"]["baseline_resume_usage"], {
            "input_tokens": 200_001, "cached_input_tokens": 0, "output_tokens": 4})
        self.assertEqual(entry["post_renewal"], {
            "window": "first-stop-of-renewed-session",
            "input_tokens": 30_000, "cached_input_tokens": 500, "output_tokens": 200,
        })
        record = json.loads((self.home / ".straw-boss" / "renewal" / "pane-p4.json").read_text())
        self.assertTrue(record["usage_recorded"])

    def test_jev_gate_miss_recorded_through_the_real_guard(self) -> None:
        jev_request = self._jev_fixture(
            "run-gate", decision="fallback", fallback_reason="under-reduction-gate")
        transcript = self.transcript([token_count_row(48_000)])
        self.write_continuity("p5", jev_request=jev_request)
        payload = {"session_id": "new-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p5", STRAW_BOSS_JEV="1", TYPESAFE_API_KEY="test-key")

        entry = [e for e in self.usage_lines() if e["kind"] == "renewal"][0]
        self.assertEqual((entry["path"], entry["path_reason"]), ("jev-gate-miss", "under-reduction-gate"))
        self.assertIsNotNone(entry["jev"])

    def test_jev_failure_recorded_through_the_real_guard(self) -> None:
        jev_request = self._jev_fixture(
            "run-fail", decision="fallback", fallback_reason="preparation-TimeoutError",
            measurement={"baseline_resume_usage": None, "candidate_resume_usage": None})
        transcript = self.transcript([token_count_row(48_000)])
        self.write_continuity("p6", jev_request=jev_request)
        payload = {"session_id": "new-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p6", STRAW_BOSS_JEV="1", TYPESAFE_API_KEY="test-key")

        entry = [e for e in self.usage_lines() if e["kind"] == "renewal"][0]
        self.assertEqual((entry["path"], entry["path_reason"]), ("jev-failure", "preparation-TimeoutError"))
        self.assertIsNone(entry["jev"]["probe"]["baseline_resume_usage"])

    # --- guard integration: native 300k compaction preempting our Stop ---

    def test_native_compaction_recorded_once_below_threshold(self) -> None:
        transcript = self.transcript([compacted_row(), token_count_row(42_000, output=900)])
        payload = {"session_id": "solo-session", "transcript_path": str(transcript)}

        self.hook(payload, HERDR_PANE_ID="p2")
        lines = self.usage_lines()
        self.assertEqual(len(lines), 1)
        entry = lines[0]
        self.assertEqual(entry["kind"], "native-300k-compaction")
        self.assertEqual(entry["session_id"], "solo-session")
        self.assertEqual(entry["post_compaction"], {
            "input_tokens": 42_000, "cached_input_tokens": 0, "output_tokens": 900,
        })
        self.assertIn("pre-compaction peak", entry["limitation"])

        # A later Stop in the same session, still below threshold, does not duplicate it.
        self.hook(payload, HERDR_PANE_ID="p2")
        self.assertEqual(len(self.usage_lines()), 1)

    def test_no_native_compaction_signal_without_a_compacted_row(self) -> None:
        transcript = self.transcript([token_count_row(42_000)])
        payload = {"session_id": "solo-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p2")
        self.assertEqual(self.usage_lines(), [])

    def test_jev_candidate_session_own_compacted_row_is_not_native_compaction(self) -> None:
        transcript = self.transcript([compacted_row(), token_count_row(42_000)])
        self.write_continuity("p3", jev_candidate_session="candidate-session")
        payload = {"session_id": "candidate-session", "transcript_path": str(transcript)}
        self.hook(payload, HERDR_PANE_ID="p3")
        self.assertEqual([e for e in self.usage_lines() if e["kind"] == "native-300k-compaction"], [])


@pytest.fixture
def jev_home(tmp_path, monkeypatch):
    monkeypatch.setenv("STRAW_BOSS_HOME", str(tmp_path))
    monkeypatch.delenv("STRAW_BOSS_JEV", raising=False)
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    return tmp_path


def archive(run_id: str, *, decision: str, fallback_reason: str | None,
            jev: dict | None = None, measurement: dict | None = None) -> None:
    record = {
        "run_id": run_id, "decision": decision, "fallback_reason": fallback_reason,
        "jev": jev or {"model": ["gpt-6-astra"], "requests": 3, "input_tokens": 210, "latency_ms": 640},
        "gate_reduction_pct": 41.2,
        "application": {"status": "prepared", "live_application_supported": True},
        "outcome": None,
        "measurement": measurement or {
            "baseline_resume_usage": {"input_tokens": 200_001, "cached_input_tokens": 0, "output_tokens": 4},
            "candidate_resume_usage": {"input_tokens": 118_000, "cached_input_tokens": 0, "output_tokens": 4},
        },
    }
    private_replace(jev_root() / "runs" / f"{run_id}.json", json.dumps({"record": record}))


def request(run_id: str) -> str:
    path = jev_root() / "requests" / f"{run_id}.json"
    private_replace(path, json.dumps({"run_id": run_id}))
    return str(path)


def test_ordinary_jev_off_when_no_request_and_disabled(jev_home):
    assert renewal_usage.classify({"session_id": "s"}, "new") == ("ordinary-jev-off", "disabled", None)


def test_jev_failure_schedule_failed_when_enabled_but_no_request(jev_home, monkeypatch):
    monkeypatch.setenv("STRAW_BOSS_JEV", "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "key")
    assert renewal_usage.classify({"session_id": "s"}, "new") == ("jev-failure", "schedule-failed", None)


def test_jev_applied_reads_the_archive(jev_home):
    archive("run-a", decision="apply", fallback_reason=None)
    path, reason, archived = renewal_usage.classify({"session_id": "s", "jev_request": request("run-a")}, "new")
    assert path == "jev-applied"
    assert reason is None
    assert archived["run_id"] == "run-a"


def test_jev_gate_miss_classified_from_fallback_reason(jev_home):
    archive("run-b", decision="fallback", fallback_reason="under-reduction-gate")
    path, reason, _ = renewal_usage.classify({"session_id": "s", "jev_request": request("run-b")}, "new")
    assert (path, reason) == ("jev-gate-miss", "under-reduction-gate")


def test_jev_failure_classified_from_exception_reason(jev_home):
    archive("run-c", decision="fallback", fallback_reason="preparation-TimeoutError")
    path, reason, _ = renewal_usage.classify({"session_id": "s", "jev_request": request("run-c")}, "new")
    assert (path, reason) == ("jev-failure", "preparation-TimeoutError")


def test_jev_block_keeps_probe_and_jev_tokens_separate(jev_home):
    archive("run-d", decision="apply", fallback_reason=None)
    _, _, archived = renewal_usage.classify({"session_id": "s", "jev_request": request("run-d")}, "new")
    block = renewal_usage._jev_block(archived)
    assert block["input_tokens"] == 210
    assert block["probe"]["baseline_resume_usage"] == {
        "input_tokens": 200_001, "cached_input_tokens": 0, "output_tokens": 4}
    assert block["probe"]["candidate_resume_usage"] == {
        "input_tokens": 118_000, "cached_input_tokens": 0, "output_tokens": 4}


if __name__ == "__main__":
    unittest.main()
