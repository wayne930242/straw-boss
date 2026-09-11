from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

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
        self.assertIn("`task` field", contract)
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

    def test_launcher_allows_every_script_a_dispatched_agent_is_told_to_run(self) -> None:
        """The runner's allowlist must cover the skills' own instructions.

        A worker can only reach these scripts through the launcher, so anything
        a skill tells it to run and the allowlist omits is an instruction it
        cannot follow. bringing-coworker's closing step is the case that bit:
        without wrap-up-task.py here a finished coworker's instruction stays
        live and blocks the next coworker on the same parent.
        """
        runner = (SCRIPTS / "run-straw-boss-script.py").read_text()
        allowlist_block = runner[runner.index("ALLOWED_SCRIPTS = {"):]
        allowlist_block = allowlist_block[: allowlist_block.index("}")]

        for script in (
            "dispatch-coworker.py",
            "report-progress.py",
            "report-task-status.py",
            "send-dispatch-message.py",
            "wrap-up-task.py",
        ):
            with self.subTest(script=script):
                self.assertIn(f'"{script}"', allowlist_block)
                self.assertTrue((SCRIPTS / script).is_file())

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
        state_module = old_scripts / "straw_boss" / "dispatch" / "state.py"
        state_module.parent.mkdir(parents=True, exist_ok=True)
        # `straw_boss/__init__.py` is what anchors SCRIPTS_DIR/PLUGIN_ROOT, so the
        # copy has to be the real one for this fake root to resolve to itself.
        (state_module.parent.parent / "__init__.py").write_text(
            (SCRIPTS / "straw_boss" / "__init__.py").read_text()
        )
        (state_module.parent / "__init__.py").write_text("")
        state_module.write_text(
            (SCRIPTS / "straw_boss" / "dispatch" / "state.py").read_text()
        )
        managed_contract = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys; from pathlib import Path; "
                    f"sys.path.insert(0, {str(old_scripts)!r}); "
                    "from straw_boss.dispatch.state import render_dispatch_contract; "
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
        source = (ROOT / "skills/dispatching-work/SKILL.md").read_text()
        for requirement in ("user requirement", "requested outcome", "verified coordination facts",
                            "Target-app context discovery", "verification method inside that anchor"):
            self.assertIn(requirement, source)
        self.assertIn("generated contract supplies lifecycle", source)
        shipping = (ROOT / "skills/shipping-task/SKILL.md").read_text()
        self.assertIn("../dispatching-work/SKILL.md", shipping)

    def test_communication_skills_keep_user_routing_concise(self) -> None:
        peer = (ROOT / "skills" / "asking-peer-agents" / "SKILL.md").read_text()
        notify = (ROOT / "skills" / "notifying-main-agent" / "SKILL.md").read_text()
        shipping = (ROOT / "skills" / "shipping-task" / "SKILL.md").read_text()

        self.assertIn("--sender-instruction-path", peer)
        self.assertIn("--in-reply-to", peer)
        self.assertIn("directly with the user", notify)
        self.assertIn("worker asks in its own pane", shipping)
        self.assertLessEqual(len(peer.splitlines()), 55)
        self.assertLessEqual(len(notify.splitlines()), 60)
        self.assertIn("at most two sentences", peer)
        self.assertIn("at most two sentences", notify)

    def test_dispatch_profile_guidance_is_route_centric_and_provider_accurate(self) -> None:
        init = (ROOT / "skills/init/SKILL.md").read_text()
        dispatch = (ROOT / "skills/dispatching-work/SKILL.md").read_text()
        mechanics = (ROOT / "skills/dispatching-work/references/dispatch-mechanics.md").read_text()
        self.assertIn("local provider configuration and the user's model preferences", init)
        self.assertIn("references/dispatch-mechanics.md#resolve-mode-and-work-route", dispatch)
        for flag in ("--agent-profile", "--agent-model", "--agent-effort", "--advisor-model"):
            self.assertIn(flag, mechanics)
        self.assertIn("Codex records no advisor", mechanics)
        self.assertIn("Claude's optional native advisor", mechanics)
        self.assertIn("must never be more permissive", mechanics)

    def test_dispatch_brief_leaves_target_context_discovery_to_worker(self) -> None:
        dispatch = (ROOT / "skills/dispatching-work/SKILL.md").read_text()
        contract = (ROOT / "scripts/straw_boss/dispatch/state.py").read_text()
        self.assertIn("Target-app context discovery and work decisions stay with the worker", dispatch)
        self.assertIn("Investigate this working directory yourself", " ".join(contract.split()))
        for skill in ("boss-say", "shipping-task"):
            source = (ROOT / "skills" / skill / "SKILL.md").read_text()
            self.assertIn("../dispatching-work/SKILL.md", source)

    def test_target_app_work_uses_the_smallest_sufficient_execution_tier(self) -> None:
        boss = (ROOT / "skills/boss-say/SKILL.md").read_text()
        work_on = (ROOT / "skills/work-on/SKILL.md").read_text()
        self.assertIn("Carry bounded work here", boss)
        self.assertIn("when app ownership, interaction, or continuity warrants one", boss)
        self.assertIn("this skill only resolves targets", work_on)
        self.assertIn("../choosing-graph/SKILL.md", boss)
        self.assertIn("Keep diagnosis and repair in the same worker", boss)

    def test_prompt_authority_keeps_herdr_worker_independent(self) -> None:
        for path in ("CONTEXT.md", "skills/i-am-orchestrator/SKILL.md", "scripts/straw_boss/dispatch/state.py"):
            source = " ".join((ROOT / path).read_text().split())
            self.assertIn("specification, design, implementation, and the verification method", source)
            self.assertRegex(source, r"verification method[^.]{0,60}anchor")
        dispatch = (ROOT / "skills/dispatching-work/SKILL.md").read_text()
        self.assertIn("worker and user choose the verification method inside that anchor", dispatch)
        self.assertIn("Route a work decision to the user", dispatch)

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
        self.assertIn("recorded main pane's tab", sources[1])
        self.assertIn("splits a pane", sources[1])

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

    def prime_session(self, payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "orchestrator-priming.py")],
            input=json.dumps(payload),
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_session_start_repeats_the_matching_worker_contract_on_resume(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        result = self.prime_session(
            {"session_id": instruction["session_id"], "source": "resume"}
        )
        self.assertIn(str(instruction_path), result.stdout)
        self.assertIn("report-task-status.py", result.stdout)
        self.assertNotIn("orchestrator", result.stdout.lower())

    def test_session_start_leaves_a_live_worker_contract_to_the_system_prompt(
        self,
    ) -> None:
        """The launcher already put this contract in the worker's system
        prompt, and startup/clear/compact all keep that process. Printing it
        again would hand the worker the whole contract twice at the moment it
        has the least room for it."""
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        for source in ("startup", "clear", "compact"):
            with self.subTest(source=source):
                result = self.prime_session(
                    {"session_id": instruction["session_id"], "source": source}
                )
                self.assertEqual(result.stdout.strip(), "")

    def test_session_start_repeats_the_contract_for_an_unknown_source(self) -> None:
        instruction_path, _ = self.write_dispatch("claude")
        instruction = json.loads(instruction_path.read_text())
        result = self.prime_session({"session_id": instruction["session_id"]})
        self.assertIn(str(instruction_path), result.stdout)

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
            "Use the smallest sufficient loop",
            "Run ADAAV silently",
            "specification, design, implementation, and the verification method",
            "inside that anchor",
            "Once work is dispatched",
            "Keep the lifecycle event-driven",
            "A dispatch reports itself",
            "spend the time between events on other coordination or on the user's conversation",
            "when observed evidence and its recorded state actually disagree, or when the user asks",
            "Keep user interaction compact",
            "current coordination delta",
            "harness-native ask-question interface",
            "Present exactly one decision, wait for its answer, then present the next",
        ):
            self.assertIn(boundary, normalized)
        self.assertEqual(normalized.count("Run ADAAV silently"), 1)

        # The complaint this budget guards: the stance injected at every
        # main-agent session start had grown to 2,373 characters of restated
        # rules. Keep the trim, or restate a rule somewhere it is not already
        # stated and this fails. The budget buys one line per coordination rule
        # a main agent actually operates -- 1,800 to 1,900 when orchestrator
        # registration became one of them, and 1,900 to 2,400 when deleting
        # docs/roles.md made this the only execution-time home for the naming
        # rule and the dispatched-agent boundary, and ADAAV stopped being an
        # acronym with no definition anywhere a session could reach. The
        # each-rule-stated-once assertions above stay the guard against
        # restatement buying that room back.
        self.assertLessEqual(len(injected), 2400, injected)

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
        # Only the fixed positional prefix is asserted here -- the trailing
        # flags are the lifecycle-delivery-confirmation strategy, not part of
        # what this test is about (the slash command reaching the pane
        # unwrapped, unlike every other intent's bracketed envelope).
        self.assertEqual(
            calls[2][:4],
            ["agent", "prompt", "worker-pane", "/compact preserve transport state"],
        )

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
