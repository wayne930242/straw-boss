"""Delivery evidence is distinct from terminal viewport completeness."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from straw_boss.herdr.transport import confirm_prompt_delivery, transcript_confirm_poll_interval_seconds


class PromptDeliveryEvidenceTests(unittest.TestCase):
    def test_transcript_poll_interval_defaults_to_two_seconds_and_accepts_an_override(self) -> None:
        variable = "STRAW_BOSS_TRANSCRIPT_CONFIRM_POLL_INTERVAL_SECONDS"
        with patch.dict("os.environ", {}, clear=False) as env:
            env.pop(variable, None)
            self.assertEqual(transcript_confirm_poll_interval_seconds(), 2.0)
            env[variable] = "0"
            self.assertEqual(transcript_confirm_poll_interval_seconds(), 0.0)

    def receipt(self, **agent_fields):
        return {"result": {"type": "agent_prompted", "agent": {
            "pane_id": "scratch-pane", "agent": "codex", **agent_fields,
        }}}

    def test_accepted_busy_and_lifecycle_gated_submissions_need_no_full_text(self):
        for status in ("working", "idle", "done", "blocked"):
            with self.subTest(status=status), patch(
                "straw_boss.herdr.transport.read_agent_transcript"
            ) as read:
                confirm_prompt_delivery(self.receipt(), "scratch-pane", "long reply", "codex", status)
                read.assert_not_called()

    def test_unrecognized_or_mismatched_receipts_require_transcript_evidence(self):
        for receipt, status in (
            ({"result": {}}, "working"),
            (self.receipt(pane_id="other-pane"), "working"),
            (self.receipt(agent="claude"), "working"),
            (self.receipt(), None),
            (self.receipt(), "unknown"),
            ({"result": {"type": "agent_info", "agent": self.receipt()["result"]["agent"]}}, "working"),
        ):
            with self.subTest(receipt=receipt, status=status), patch(
                "straw_boss.herdr.transport.read_agent_transcript",
                return_value="Messages to be submitted after next tool call\n ↳ truncated …",
            ) as read, patch("straw_boss.herdr.transport.sleep"):
                with self.assertRaisesRegex(ValueError, "6 transcript reads.*not resent"):
                    confirm_prompt_delivery(receipt, "scratch-pane", "long reply", "codex", status)
                self.assertEqual(read.call_count, 6)

    def test_reply_visible_after_current_turn_confirms_without_receipt(self):
        with patch("straw_boss.herdr.transport.read_agent_transcript", side_effect=[
            "queued …", "quoted 繁 體中\n文 reply",
        ]) as read, patch("straw_boss.herdr.transport.sleep"):
            confirm_prompt_delivery({}, "scratch-pane", "quoted 繁體中文 reply", "codex", "working")
            self.assertEqual(read.call_count, 2)

    def test_read_failure_remains_an_error(self):
        with patch("straw_boss.herdr.transport.read_agent_transcript", side_effect=ValueError("read unavailable")):
            with self.assertRaisesRegex(ValueError, "read unavailable"):
                confirm_prompt_delivery({}, "scratch-pane", "reply", "codex", "working")
