"""The main agent's restriction tier must reach the dispatched agent."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from straw_boss.dispatch.launch.provider import provider_profile_args
from straw_boss.dispatch.permission import (
    GUARDED_WRITE,
    NO_MIRROR,
    READ_ONLY,
    UNRESTRICTED,
    detect_claude_tier,
    tier_flags,
)


class PermissionMirroringTests(unittest.TestCase):
    def test_documented_tiers_map_to_their_flags(self) -> None:
        self.assertEqual(tier_flags(UNRESTRICTED, "claude"), ("--dangerously-skip-permissions",))
        self.assertEqual(
            tier_flags(UNRESTRICTED, "codex"), ("--dangerously-bypass-approvals-and-sandbox",)
        )
        self.assertEqual(tier_flags(READ_ONLY, "codex"), ("--sandbox", "read-only"))
        self.assertEqual(tier_flags(UNRESTRICTED, "agy"), ("--dangerously-skip-permissions",))
        self.assertEqual(tier_flags(READ_ONLY, "agy"), ("--mode", "plan"))

    def test_an_undocumented_pairing_keeps_the_provider_default(self) -> None:
        # Leaving the default is never more permissive than the tier being
        # mirrored, so an unmapped kind must not be guessed at or refused.
        self.assertEqual(tier_flags(GUARDED_WRITE, "agy"), ())
        self.assertEqual(tier_flags(GUARDED_WRITE, "claude"), ())

    def test_an_unknown_tier_adds_nothing(self) -> None:
        # None means "could not read", not "unrestricted" -- it must never
        # silently grant the widest tier.
        self.assertEqual(tier_flags(None, "claude"), ())

    def test_detection_reads_the_named_process_and_never_guesses(self) -> None:
        self.assertIsNone(detect_claude_tier("not-a-pid"))
        self.assertIsNone(detect_claude_tier(""))
        # This test process carries no claude flags, so it reads as guarded.
        import os

        self.assertEqual(detect_claude_tier(str(os.getpid())), GUARDED_WRITE)

    def test_launcher_prepends_the_mirrored_flag(self) -> None:
        instruction = {
            "agent_kind": "claude",
            "main_agent_permission_tier": UNRESTRICTED,
            "agent_model": "sonnet",
        }
        args = provider_profile_args(instruction, [])
        self.assertIn("--dangerously-skip-permissions", args)
        self.assertLess(
            args.index("--dangerously-skip-permissions"), args.index("--model")
        )

    def test_an_explicit_caller_flag_is_not_duplicated(self) -> None:
        instruction = {"agent_kind": "claude", "main_agent_permission_tier": UNRESTRICTED}
        args = provider_profile_args(instruction, ["--dangerously-skip-permissions"])
        # The caller's own copy is returned; the mirror must not add a second.
        self.assertEqual(args.count("--dangerously-skip-permissions"), 1)

    def test_a_different_caller_permission_flag_replaces_the_mirrored_one(self) -> None:
        # Matching only the identical flag left the worker carrying both
        # `--permission-mode plan` and `--dangerously-skip-permissions`.
        instruction = {"agent_kind": "claude", "main_agent_permission_tier": UNRESTRICTED}
        args = provider_profile_args(instruction, ["--permission-mode", "plan"])
        self.assertNotIn("--dangerously-skip-permissions", args)

        codex = {"agent_kind": "codex", "main_agent_permission_tier": READ_ONLY}
        codex_args = provider_profile_args(
            codex, ["--dangerously-bypass-approvals-and-sandbox"]
        )
        self.assertNotIn("--sandbox", codex_args)

    def test_no_mirror_launches_with_no_permission_flag(self) -> None:
        for kind in ("claude", "codex"):
            with self.subTest(agent_kind=kind):
                instruction = {"agent_kind": kind, "main_agent_permission_tier": NO_MIRROR}
                self.assertEqual(tier_flags(NO_MIRROR, kind), ())
                self.assertEqual(provider_profile_args(instruction, []), [])


if __name__ == "__main__":
    unittest.main()
