from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import (
    ROOT,
    SCRIPTS,
    DispatchedAgentLifecycleFixture,
)


class DispatchedAgentLifecycleContractTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def test_write_generates_a_hashed_system_contract_before_launch(self) -> None:
        instruction_path, output = self.write_dispatch("claude")

        instruction = json.loads(instruction_path.read_text())
        contract_path = Path(str(output["contract_path"]))
        self.assertTrue(contract_path.is_file())
        self.assertEqual(instruction["contract_path"], str(contract_path))
        self.assertRegex(str(instruction["contract_sha256"]), r"^[0-9a-f]{64}$")
        self.assertEqual(instruction["main_agent_session_id"], "main-session")

        contract = contract_path.read_text()
        self.assertIn(str(instruction_path), contract)
        self.assertIn("report-task-status.py", contract)
        self.assertIn("awaiting-user-input", contract)
        self.assertIn("awaiting-main-agent", contract)
        self.assertIn("awaiting-authorization", contract)
        self.assertIn("Before stopping", contract)
        self.assertIn("Do not use SendMessage", contract)
        self.assertIn("delta-only", contract)
        self.assertIn("--ref", contract)
        self.assertIn("independent agent", contract)
        self.assertIn("notifies the main agent through Herdr", contract)

    def test_write_records_provider_profile_and_claude_advisor(self) -> None:
        instruction_path, _ = self.write_dispatch(
            "claude",
            agent_profile="worker",
            agent_model="sonnet",
            agent_effort="high",
            advisor_model="opus",
        )

        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["agent_profile"], "worker")
        self.assertEqual(instruction["agent_model"], "sonnet")
        self.assertEqual(instruction["agent_effort"], "high")
        self.assertEqual(instruction["advisor_model"], "opus")

    def test_write_records_an_explicit_workroom_role(self) -> None:
        instruction_path, _ = self.write_dispatch("claude", role="database")

        instruction = json.loads(instruction_path.read_text())
        self.assertEqual(instruction["role"], "database")

    def test_write_defaults_role_to_none_when_omitted(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")

        instruction = json.loads(instruction_path.read_text())
        self.assertIsNone(instruction["role"])

    def test_write_rejects_codex_advisor_before_creating_instruction(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            "codex-advisor",
            "--task",
            "Write the documentation.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            "codex",
            "--advisor-model",
            "opus",
            "--main-agent-kind",
            "claude",
            "--main-agent-pane-id",
            "main-pane",
            "--main-agent-session-id",
            "main-session",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("advisor", result.stderr.lower())
        self.assertIn("claude", result.stderr.lower())
        self.assertFalse(
            (self.home / ".straw-boss" / "dispatch" / "api--codex-advisor.json").exists()
        )

    def test_contract_uses_version_neutral_launcher_that_follows_plugin_updates(
        self,
    ) -> None:
        instruction_path, output = self.write_dispatch("claude")
        contract = Path(str(output["contract_path"])).read_text()
        launcher = self.home / ".straw-boss" / "bin" / "run-straw-boss-script.py"

        self.assertTrue(launcher.is_file())
        self.assertEqual(contract.count(f"uv run --script {launcher}"), 3)
        self.assertNotIn(
            f"uv run --script {SCRIPTS / 'report-progress.py'}", contract
        )

        cache_root = (
            self.home / ".claude" / "plugins" / "cache" / "straw-boss" / "straw-boss"
        )
        old_root = cache_root / "0.18.2"
        new_root = cache_root / "0.18.3"
        for root, marker in ((old_root, "old"), (new_root, "new")):
            script = root / "scripts" / "report-progress.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "# /// script\n"
                "# requires-python = \">=3.11\"\n"
                "# dependencies = []\n"
                "# ///\n"
                "import sys\n"
                f"print({marker!r}, *sys.argv[1:])\n"
            )

        old_scripts = old_root / "scripts"
        (old_scripts / "dispatch_state.py").write_text(
            (SCRIPTS / "dispatch_state.py").read_text()
        )
        managed_contract = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; from pathlib import Path; "
                    f"sys.path.insert(0, {str(old_scripts)!r}); "
                    "from dispatch_state import render_dispatch_contract; "
                    "print(render_dispatch_contract(Path('/tmp/instruction.json')))"
                ),
            ],
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(managed_contract.returncode, 0, managed_contract.stderr)
        self.assertIn("--prefer-installed", managed_contract.stdout)

        fake_bin = self.home / "bin"
        fake_bin.mkdir(exist_ok=True)
        fake_claude = fake_bin / "claude"
        fake_claude.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            f"print(json.dumps([{{'id': 'straw-boss@straw-boss', 'enabled': True, 'installPath': {str(new_root)!r}}}]))\n"
        )
        fake_claude.chmod(0o755)
        env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        }

        result = subprocess.run(
            [
                sys.executable,
                str(launcher),
                "--origin-root",
                str(old_root),
                "--prefer-installed",
                "--script",
                "report-progress.py",
                "--",
                "--instruction-path",
                str(instruction_path),
                "--note",
                "version probe",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("new --instruction-path", result.stdout)
        self.assertNotIn("old --instruction-path", result.stdout)

        fake_claude.write_text(
            "#!/usr/bin/env python3\n"
            "print('[]')\n"
        )
        fallback = subprocess.run(
            [
                sys.executable,
                str(launcher),
                "--origin-root",
                str(old_root),
                "--prefer-installed",
                "--script",
                "report-progress.py",
                "--",
                "--note",
                "fallback probe",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(fallback.returncode, 0, fallback.stderr)
        self.assertIn("old --note fallback probe", fallback.stdout)

        rejected = subprocess.run(
            [
                sys.executable,
                str(launcher),
                "--origin-root",
                str(old_root),
                "--script",
                "../dispatch-task.py",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unsupported Straw Boss script", rejected.stderr)

    def test_task_authoring_leaves_work_definition_to_worker_and_user(self) -> None:
        shipping = (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text()
        plan_mechanics = (
            ROOT / "skills" / "dispatching-work" / "references" / "plan-mechanics.md"
        ).read_text()

        for source in (shipping, plan_mechanics):
            normalized = " ".join(source.split())
            self.assertIn("user requirement", normalized)
            self.assertIn("requested outcome", normalized)
            self.assertIn("already-known coordination facts", normalized)
            self.assertIn(
                "specification, design, implementation, and the verification method",
                normalized,
            )
            # Scoped to the anchor the main agent named, so the brief boundary
            # and the generated contract cannot contradict each other.
            self.assertRegex(normalized, r"verification method[^.]{0,60}anchor")
            self.assertIn("generic lifecycle prose", source.lower())
            self.assertNotIn("possible implementation", source)
            self.assertNotIn("concrete deliverable and proof", source)

        self.assertNotIn(
            "selected lifecycle/worktree, mutation gates, tracker boundary, checkpoints",
            shipping,
        )
        self.assertNotIn(
            "Task-specific prose adds only tracker boundaries",
            plan_mechanics,
        )

        self.assertIn("non-overlapping requirement scopes", plan_mechanics)

    def test_communication_skills_keep_user_routing_concise(self) -> None:
        peer = (ROOT / "skills" / "asking-peer-agents" / "SKILL.md").read_text()
        notify = (ROOT / "skills" / "notifying-main-agent" / "SKILL.md").read_text()
        shipping = (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text()

        self.assertIn("--sender-instruction-path", peer)
        self.assertIn("--in-reply-to", peer)
        self.assertIn("directly with the user", notify)
        self.assertIn("directly in the dispatched agent's session", shipping)
        self.assertLessEqual(len(peer.splitlines()), 55)
        self.assertLessEqual(len(notify.splitlines()), 60)
        self.assertIn("at most two sentences", peer)
        self.assertIn("at most two sentences", notify)

    def test_dispatch_profile_guidance_is_route_centric_and_provider_accurate(
        self,
    ) -> None:
        init = (ROOT / "skills" / "init" / "SKILL.md").read_text()
        dispatching = (ROOT / "skills" / "dispatching-work" / "SKILL.md").read_text()
        mechanics = (
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "dispatch-mechanics.md"
        ).read_text()
        coworker = (ROOT / "skills" / "bringing-coworker" / "SKILL.md").read_text()

        for source in (init, dispatching, mechanics):
            normalized = " ".join(source.lower().split())
            self.assertIn("work route", normalized)
            self.assertIn("provider profile", normalized)
        self.assertIn("Claude Code native advisor", init)
        self.assertIn("Claude Code native advisor", dispatching)
        self.assertIn("--agent-profile", mechanics)
        self.assertIn("--advisor-model", mechanics)
        self.assertIn("--advisor <advisor_model>", mechanics)
        self.assertIn("Codex has no native advisor", mechanics)
        self.assertNotIn("advisor", coworker.lower())

    def test_dispatch_brief_leaves_target_context_discovery_to_worker(self) -> None:
        roles = (ROOT / "docs" / "roles.md").read_text()
        dispatching = (ROOT / "skills" / "dispatching-work" / "SKILL.md").read_text()
        shipping = (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text()
        boss_say = (ROOT / "skills" / "boss-say" / "SKILL.md").read_text()
        plan_mechanics = (
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "plan-mechanics.md"
        ).read_text()
        contract_source = (ROOT / "scripts" / "dispatch_state.py").read_text()

        normalize = lambda source: " ".join(source.replace("`", "").split())
        self.assertIn(
            "Target-app context discovery belongs to the dispatched agent",
            normalize(roles),
        )
        self.assertIn(
            "Target-app implementation, precedent, and local-context discovery stays with the worker",
            normalize(dispatching),
        )
        self.assertIn("dispatching-work Task 3's brief boundary", normalize(shipping))
        self.assertIn("dispatching-work Task 3's brief boundary", normalize(boss_say))
        self.assertIn(
            "dispatching-work Task 3's brief boundary",
            normalize(plan_mechanics),
        )
        self.assertIn(
            "Investigate the target app's implementation and precedent yourself",
            normalize(contract_source),
        )

    def test_target_app_research_dispatches_for_explanatory_evidence(self) -> None:
        roles = (ROOT / "docs" / "roles.md").read_text()
        context = (ROOT / "CONTEXT.md").read_text()
        orchestrator = (ROOT / "skills" / "i-am-orchestrator" / "SKILL.md").read_text()
        boss_say = (ROOT / "skills" / "boss-say" / "SKILL.md").read_text()
        work_on = (ROOT / "skills" / "work-on" / "SKILL.md").read_text()
        investigating = (ROOT / "skills" / "investigating-app" / "SKILL.md").read_text()
        inspecting = (ROOT / "skills" / "inspecting-app" / "SKILL.md").read_text()
        troubleshooting = (ROOT / "skills" / "troubleshooting-app" / "SKILL.md").read_text()

        normalize = lambda source: " ".join(source.replace("`", "").split())
        for source in (roles, context, orchestrator):
            self.assertIn(
                "dispatches that investigation instead of reading across managed app roots",
                normalize(source),
            )
        self.assertIn(
            "Any item that must read under a managed app root uses a dispatched agent",
            normalize(boss_say),
        )
        self.assertIn(
            "Bounded investigation may use a confirmed lower-tier work route",
            normalize(boss_say),
        )
        self.assertIn(
            "managed-app files makes dispatch mandatory",
            normalize(work_on),
        )
        self.assertNotIn("Reads/explanations that don't change code — answer inline", work_on)
        for source in (investigating, inspecting):
            normalized = normalize(source)
            self.assertIn("always dispatches", normalized)
            self.assertIn("evidence references", normalized)
            self.assertIn("explanatory", normalized)
            self.assertNotIn("- **Solo:**", source)

        normalized_troubleshooting = normalize(troubleshooting)
        self.assertIn("integration preflight", normalized_troubleshooting)
        self.assertIn("only when both conditions hold", normalized_troubleshooting)
        self.assertIn("stays in the same worker", normalized_troubleshooting)
        self.assertIn("evidence references", normalized_troubleshooting)
        self.assertIn("explanatory", normalized_troubleshooting)
        self.assertNotIn("- **Solo:**", troubleshooting)

    def test_prompt_authority_keeps_herdr_worker_independent(self) -> None:
        roles = (ROOT / "docs" / "roles.md").read_text()
        context = (ROOT / "CONTEXT.md").read_text()
        orchestrator = (ROOT / "skills" / "i-am-orchestrator" / "SKILL.md").read_text()
        dispatching = (ROOT / "skills" / "dispatching-work" / "SKILL.md").read_text()
        boss_say = (ROOT / "skills" / "boss-say" / "SKILL.md").read_text()
        contract_source = (ROOT / "scripts" / "dispatch_state.py").read_text()

        for source in (roles, context, orchestrator):
            self.assertIn("own the loop, not the work", source.lower())
            self.assertNotIn("adjust an item's spec", source)
        self.assertIn("accept", roles.lower())
        self.assertIn("user and dispatched agent", roles)
        for source in (roles, context, orchestrator, dispatching, boss_say, contract_source):
            normalized = " ".join(source.split())
            self.assertIn(
                "specification, design, implementation, and the verification method",
                normalized,
            )
            self.assertRegex(normalized, r"verification method[^.]{0,60}anchor")
        normalized_contract = " ".join(contract_source.split())
        self.assertIn(
            "supplies the user requirement, necessary hints, and known coordination facts",
            normalized_contract,
        )
        self.assertIn(
            "Investigate the target app's implementation and precedent yourself",
            normalized_contract,
        )
        self.assertNotIn('--reply "<the decision>"', boss_say)

    def test_dispatch_guidance_never_creates_or_closes_worker_tabs(self) -> None:
        sources = [
            (ROOT / "skills" / "dispatching-work" / "SKILL.md").read_text(),
            (
                ROOT
                / "skills"
                / "dispatching-work"
                / "references"
                / "dispatch-mechanics.md"
            ).read_text(),
            (
                ROOT
                / "skills"
                / "dispatching-work"
                / "references"
                / "plan-mechanics.md"
            ).read_text(),
            (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text(),
            (ROOT / "skills" / "init" / "SKILL.md").read_text(),
        ]

        for source in sources:
            self.assertNotIn("herdr tab create", source)
            self.assertNotIn("herdr tab close", source)
        self.assertIn("same tab", sources[1].lower())
        self.assertIn("pane split", sources[1])

    def test_herdr_dispatch_requires_main_agent_session_fingerprint(self) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            "missing-main-session",
            "--task",
            "Run the task.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "claude",
            "--main-agent-pane-id",
            "main-pane",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--main-agent-session-id is required", result.stderr)

    def test_herdr_dispatch_requires_main_agent_terminal_fingerprint_for_codex(
        self,
    ) -> None:
        result = self.run_script(
            "dispatch-task.py",
            "write",
            "--app",
            "api",
            "--slug",
            "missing-main-terminal",
            "--task",
            "Run the task.",
            "--mode",
            "herdr-pane",
            "--repo-root",
            str(ROOT),
            "--agent-kind",
            "claude",
            "--main-agent-kind",
            "codex",
            "--main-agent-pane-id",
            "main-pane",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--main-agent-terminal-id is required", result.stderr)

    def test_stop_hook_blocks_a_dispatched_agent_without_a_status_report(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "dispatched-agent-stop-guard.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual(decision["decision"], "block")
        self.assertIn(str(instruction_path), decision["reason"])
        self.assertIn("report-task-status.py", decision["reason"])

    def test_stop_hook_allows_a_dispatched_agent_after_a_valid_report(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        instruction["status"] = "in-progress"
        instruction_path.write_text(json.dumps(instruction, indent=2) + "\n")
        status_path = instruction_path.with_name("api--contract-claude.status.json")
        status_path.write_text(
            json.dumps({"status": "done", "note": "verified", "timestamp": "now"})
        )

        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "dispatched-agent-stop-guard.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_hook_registration_includes_the_stop_guard(self) -> None:
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        commands = [
            hook["command"]
            for entry in hooks["hooks"]["Stop"]
            for hook in entry["hooks"]
        ]
        self.assertTrue(
            any("dispatched-agent-stop-guard.py" in command for command in commands)
        )

    def test_hook_commands_never_resolve_scripts_from_the_session_directory(self) -> None:
        # A hook runs in the session's own working directory, not in the plugin
        # directory. Resolving the script relative to that cwd either exits 127 or
        # runs an unrelated file that happens to sit at scripts/<same-name>.
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        env = {**os.environ, "HOME": str(self.home)}
        env.pop("CLAUDE_PLUGIN_ROOT", None)

        session_dir = self.home / "session"
        decoy_dir = session_dir / "scripts"
        decoy_dir.mkdir(parents=True)
        marker = session_dir / "decoy-ran"
        for script in ("orchestrator-priming.py", "dispatched-agent-stop-guard.py"):
            decoy = decoy_dir / script
            decoy.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                "Path(%r).write_text('ran')\n" % str(marker)
            )
            decoy.chmod(0o755)

        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry["hooks"]:
                    result = subprocess.run(
                        hook["command"],
                        shell=True,
                        input="{}",
                        cwd=session_dir,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse(
                        marker.exists(),
                        "hook executed a script from the session directory",
                    )
                    self.assertIn("CLAUDE_PLUGIN_ROOT", result.stdout)

    def test_hook_commands_honor_claude_root_outside_plugin_directory(self) -> None:
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())
        env = {
            **os.environ,
            "HOME": str(self.home),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
        }

        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry["hooks"]:
                    result = subprocess.run(
                        hook["command"],
                        shell=True,
                        input="{}",
                        cwd=self.home,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_session_start_repeats_the_matching_worker_contract_on_resume(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "orchestrator-priming.py")],
            input=json.dumps({"session_id": instruction["session_id"]}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(instruction_path), result.stdout)
        self.assertIn("report-task-status.py", result.stdout)
        self.assertNotIn("orchestrator", result.stdout.lower())

    def test_session_start_primes_a_main_agent_with_a_compact_stance(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "orchestrator-priming.py")],
            input=json.dumps({"session_id": "main-session-with-no-dispatch"}),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        injected = result.stdout.strip()

        # The hook injects the stance body, never the skill's YAML frontmatter.
        self.assertNotIn("name: i-am-orchestrator", injected)
        self.assertNotIn("---", injected)
        # A main agent never runs the worker's reporting command; that contract
        # belongs to the dispatched branch of this same hook.
        self.assertNotIn("report-task-status.py", injected)

        normalized = " ".join(injected.replace("`", "").split())
        for boundary in (
            "Own the loop, not the work",
            "specification, design, implementation, and the verification method",
            "inside that anchor",
            "dispatches that investigation instead of reading across managed app roots",
            "Keep the lifecycle event-driven",
            "A dispatch reports itself",
            "spend the time between events on other coordination or on the user's conversation",
            "when observed evidence and its recorded state actually disagree, or when the user asks",
        ):
            self.assertIn(boundary, normalized)

        # The complaint this budget guards: the stance injected at every
        # main-agent session start had grown to 2,373 characters of restated
        # rules. Keep the trim, or restate a rule somewhere it is not already
        # stated and this fails.
        self.assertLessEqual(len(injected), 1800, injected)

    def test_control_message_preserves_the_exact_slash_command(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = self.set_worker_endpoint(
            instruction_path, session=json.loads(instruction_path.read_text())["session_id"]
        )
        fake_bin, capture = self.install_fake_herdr()
        env = {
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "HERDR_CAPTURE": str(capture),
            "HERDR_PANE_ID": "main-pane",
            "HERDR_SESSIONS": json.dumps(
                {
                    "main-pane": "main-session",
                    "worker-pane": str(instruction["session_id"]),
                }
            ),
        }

        result = self.run_script(
            "send-dispatch-message.py",
            "--instruction-path",
            str(instruction_path),
            "--to",
            "worker",
            "--intent",
            "control",
            "--message",
            "/compact preserve transport state",
            extra_env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = [json.loads(line) for line in capture.read_text().splitlines()]
        self.assertEqual(calls[2], ["agent", "prompt", "worker-pane", "/compact preserve transport state"])

    def test_wrap_up_archives_contract_receipt_and_delivery_ledger(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        self.set_worker_endpoint(instruction_path)
        stem = instruction_path.name.removesuffix(".json")
        status_path = instruction_path.with_name(f"{stem}.status.json")
        status_path.write_text(json.dumps({"status": "done"}) + "\n")
        launch_path = instruction_path.with_name(f"{stem}.launch.json")
        launch_path.write_text(json.dumps({"session_id": "worker"}) + "\n")
        messages_path = instruction_path.with_name(f"{stem}.messages.jsonl")
        messages_path.write_text(json.dumps({"intent": "status"}) + "\n")

        result = self.run_script(
            "wrap-up-task.py", "--app", "api", "--slug", "contract-claude"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = self.home / ".straw-boss" / "dispatch" / "archive"
        for suffix in (".json", ".contract.md", ".launch.json", ".status.json", ".messages.jsonl"):
            self.assertTrue((archive / f"{stem}{suffix}").is_file(), suffix)

    def test_active_skills_have_no_provider_native_cross_session_fallback(self) -> None:
        skill_text = "\n".join(
            path.read_text() for path in sorted((ROOT / "skills").rglob("*.md"))
        )
        self.assertNotIn("SendMessage", skill_text)
        self.assertFalse((SCRIPTS / "get-main-agent.py").exists())


if __name__ == "__main__":
    unittest.main()
