"""Antigravity carries no conversation id, so its terminal is its identity."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from straw_boss.herdr.session import agent_matches_identity


class AgyIdentityRoutingTests(unittest.TestCase):
    def test_antigravity_matches_on_terminal_alone(self) -> None:
        # Without this, every agy endpoint fails identity and the caller reports
        # a terminal mismatch quoting two ids that are equal.
        agent = {"agent": "agy", "terminal_id": "term_a"}
        self.assertTrue(agent_matches_identity(agent, "agy", None, "term_a"))
        self.assertFalse(agent_matches_identity(agent, "agy", None, "term_b"))
        self.assertFalse(agent_matches_identity(agent, "agy", None, None))

    def test_legacy_codex_keeps_its_terminal_only_path(self) -> None:
        agent = {"agent": "codex", "terminal_id": "term_a"}
        self.assertTrue(agent_matches_identity(agent, "codex", None, "term_a"))

    def test_a_recorded_session_still_wins_over_the_terminal(self) -> None:
        agent = {
            "agent": "agy",
            "terminal_id": "term_a",
            "agent_session": {"value": "s-live"},
        }
        self.assertTrue(agent_matches_identity(agent, "agy", "s-live", "term_other"))
        self.assertFalse(agent_matches_identity(agent, "agy", "s-stale", "term_a"))

    def test_claude_is_never_identified_by_terminal(self) -> None:
        # Claude always mints a session id, so a terminal-only match there would
        # accept a replaced agent occupying the same pane.
        agent = {"agent": "claude", "terminal_id": "term_a"}
        self.assertFalse(agent_matches_identity(agent, "claude", None, "term_a"))


if __name__ == "__main__":
    unittest.main()
