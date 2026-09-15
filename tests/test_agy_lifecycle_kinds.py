"""A kind that can be dispatched must also be recoverable and wrappable."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from straw_boss import orchestrator
from straw_boss.dispatch import state


class AgyLifecycleKindsTests(unittest.TestCase):
    def test_lifecycle_kinds_cover_every_dispatchable_kind(self) -> None:
        # Antigravity reached dispatch without reaching this tuple, so an agy
        # coworker launched fine and then could never be recovered or archived:
        # its instruction sat in-progress after its pane was already gone.
        self.assertEqual(
            set(orchestrator.SUPPORTED_AGENT_KINDS) - set(state.SUPPORTED_AGENT_KINDS),
            set(),
            "a dispatchable kind missing here strands its instruction in-progress",
        )
