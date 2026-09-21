"""Immediate-parent permission inheritance and override resistance."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from straw_boss.dispatch.coworker_permission import effective_tier, parent_permission_tier
from straw_boss.dispatch.launch.provider import provider_profile_args
from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class PermissionPolicyTests(unittest.TestCase):
    def test_effective_parent_overrides_and_ambiguity(self):
        cases = [
            ("codex", ["--sandbox", "read-only"], "read-only"),
            ("codex", ["-s=workspace-write"], "guarded-write"),
            ("codex", ["--yolo"], "unrestricted"),
            ("claude", ["--permission-mode=plan"], "read-only"),
            ("claude", ["--dangerously-skip-permissions"], "unrestricted"),
            ("codex", ["--yolo", "-c", 'sandbox_mode="read-only"'], None),
            ("codex", ["--yolo", "--sandbox", "read-only"], None),
            ("codex", ["--profile", "custom"], None),
            ("codex", [], None),
            ("claude", [], "guarded-write"),
            ("codex", ["--yolo", "-sread-only"], None),
            ("codex", ["-sread-only"], "read-only"),
            ("codex", ["--", "--yolo"], None),
            ("codex", ["--yolo", "-pcustom"], None),
        ]
        for kind, args, expected in cases:
            with self.subTest(kind=kind, args=args):
                self.assertEqual(effective_tier(kind, args), expected)

    def test_legacy_parent_uses_own_process_not_root_tier(self):
        for kind, args, expected in [
            ("codex", ["--dangerously-bypass-approvals-and-sandbox"], "unrestricted"),
            ("claude", ["--dangerously-skip-permissions"], "unrestricted"),
            ("codex", ["--sandbox", "read-only"], "read-only"),
        ]:
            parent = {"agent_kind": kind, "herdr_pane_id": "parent", "main_agent_permission_tier": "unrestricted"}
            info = {"result": {"process_info": {"pane_id": "parent", "foreground_processes": [{"argv": [kind, *args]}]}}}
            with patch("straw_boss.dispatch.coworker_permission.run_herdr", return_value=info):
                self.assertEqual(parent_permission_tier(parent), expected)
        with patch("straw_boss.dispatch.coworker_permission.run_herdr", side_effect=ValueError("unavailable")):
            self.assertEqual(parent_permission_tier(parent), "read-only")

    def test_child_rejects_permission_overrides_at_launcher_boundary(self):
        child = {"agent_kind": "codex", "parent_instruction_path": "/parent.json", "main_agent_permission_tier": "read-only"}
        for args in [["-c", "model_reasoning_effort=low\nsandbox_mode=\"danger-full-access\""], ["--yolo"], ["--sandbox=danger-full-access"], ["-s", "danger-full-access"], ["--full-auto"], ["-c", 'sandbox_mode="danger-full-access"'], ["--profile", "custom"], ["--dangerously-bypass-approvals-and-sandbox"]]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                provider_profile_args(child, args)
        self.assertEqual(provider_profile_args(child, ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=low"]), ["--sandbox", "read-only", "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=low"])


class CoworkerLaunchTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def test_codex_coworker_launches_from_each_parent_at_effective_tier(self):
        for kind in ("codex", "claude"):
            for tier, expected in (("unrestricted", "--dangerously-bypass-approvals-and-sandbox"), ("guarded-write", "workspace-write"), ("read-only", "read-only")):
                with self.subTest(kind=kind, tier=tier):
                    parent_path, _ = self.write_dispatch(kind, slug=f"parent-{kind}-{tier}")
                    parent = self.set_worker_endpoint(parent_path)
                    parent.update(main_agent_permission_tier="unrestricted", agent_permission_tier=tier)
                    parent_path.write_text(json.dumps(parent))
                    fake_bin, capture = self.install_fake_herdr()
                    capture.unlink(missing_ok=True)
                    result = self.run_script("dispatch-coworker.py", "--parent-instruction-path", str(parent_path), "--slug", f"child-{kind}-{tier}", "--task", "Report status without editing repository files.", "--agent-kind", "codex", extra_env={
                        "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
                        "HERDR_CAPTURE": str(capture), "HERDR_PANE_ID": "worker-pane",
                        "HERDR_WORKER_PANE_ID": "coworker-pane",
                        "HERDR_AGENT_KINDS": json.dumps({"worker-pane": kind, "coworker-pane": "codex", "main-pane": "claude"}),
                        "HERDR_SESSIONS": json.dumps({"worker-pane": "worker-session", "coworker-pane": "coworker-session", "main-pane": "main-session"}),
                    })
                    self.assertEqual(result.returncode, 0, result.stderr)
                    child = json.loads(Path(json.loads(result.stdout)["instruction_path"]).read_text())
                    self.assertEqual(child["main_agent_permission_tier"], tier)
                    self.assertEqual(child["agent_permission_tier"], tier)
                    self.assertIn("review-only", Path(child["contract_path"]).read_text())
                    start = next(c for c in map(json.loads, capture.read_text().splitlines()) if c[:2] == ["agent", "start"])
                    self.assertIn(expected, start)
                    if tier != "unrestricted":
                        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", start)

    def test_default_claude_parent_launch_chain_records_guarded_write(self):
        parent_path, _ = self.write_dispatch("claude")
        parent = json.loads(parent_path.read_text())
        parent["main_agent_permission_tier"] = "guarded-write"
        parent_path.write_text(json.dumps(parent))
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_LIVE_SESSION": str(parent["session_id"]),
        }
        launched = self.run_script("launch-dispatched-agent.py", "--instruction-path", str(parent_path), extra_env=env)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        parent = json.loads(parent_path.read_text())
        self.assertEqual(parent["agent_permission_tier"], "guarded-write")
        child = self.run_script("dispatch-coworker.py", "--parent-instruction-path", str(parent_path), "--slug", "chain-child", "--task", "Report status.", "--agent-kind", "codex", extra_env={
            **env, "HERDR_PANE_ID": "worker-pane", "HERDR_WORKER_PANE_ID": "coworker-pane",
            "HERDR_SESSIONS": json.dumps({"worker-pane": parent["session_id"], "coworker-pane": "coworker-session", "main-pane": "main-session"}),
        })
        self.assertEqual(child.returncode, 0, child.stderr)
        child_instruction = json.loads(Path(json.loads(child.stdout)["instruction_path"]).read_text())
        self.assertEqual(child_instruction["main_agent_permission_tier"], "guarded-write")
        starts = [c for c in map(json.loads, capture.read_text().splitlines()) if c[:2] == ["agent", "start"]]
        self.assertIn("workspace-write", starts[-1])
        self.assertIn("on-request", starts[-1])
