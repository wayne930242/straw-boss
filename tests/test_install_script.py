from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"
PLUGIN_ID = "straw-boss@straw-boss"


class InstallScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.bin_dir = self.root / "bin"
        self.state_dir = self.root / "state"
        self.bin_dir.mkdir()
        self.state_dir.mkdir()
        self.capture = self.root / "calls.jsonl"
        self.version = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text()
        )["version"]
        self._write_fake_cli("claude")
        self._write_fake_cli("codex")

    def _write_fake_cli(self, provider: str) -> None:
        path = self.bin_dir / provider
        path.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            f"provider = {provider!r}\n"
            "args = sys.argv[1:]\n"
            "state = Path(os.environ['INSTALLER_STATE'])\n"
            "capture = Path(os.environ['INSTALLER_CAPTURE'])\n"
            "version = os.environ['EXPECTED_VERSION']\n"
            "with capture.open('a') as stream:\n"
            "    stream.write(json.dumps([provider, *args]) + '\\n')\n"
            "market = state / f'{provider}-market'\n"
            "plugin = state / f'{provider}-plugin'\n"
            "if args[:3] == ['plugin', 'marketplace', 'list']:\n"
            "    if provider == 'claude':\n"
            "        payload = ([{'name': 'straw-boss', 'source': 'directory'}] if market.exists() else [])\n"
            "    else:\n"
            "        payload = {'marketplaces': ([{'name': 'straw-boss', 'marketplaceSource': {'sourceType': os.environ.get('CODEX_MARKET_TYPE', 'local')}}] if market.exists() else [])}\n"
            "    print(json.dumps(payload)); raise SystemExit\n"
            "if args[:3] == ['plugin', 'marketplace', 'add']:\n"
            "    market.touch(); print('{}'); raise SystemExit\n"
            "if args[:3] == ['plugin', 'marketplace', 'update']:\n"
            "    print('{}'); raise SystemExit\n"
            "if args[:3] == ['plugin', 'marketplace', 'upgrade']:\n"
            "    print('{}'); raise SystemExit\n"
            "if args[:2] == ['plugin', 'list']:\n"
            "    fail_key = f'FAIL_{provider.upper()}_PLUGIN_LIST'\n"
            "    if os.environ.get(fail_key) == '1':\n"
            "        print(f'{provider} plugin list failed', file=sys.stderr); raise SystemExit(9)\n"
            "    installed_version = plugin.read_text().strip() if plugin.exists() else None\n"
            "    if provider == 'claude':\n"
            "        scope = 'user'\n"
            "        first_list = state / 'claude-first-list-seen'\n"
            "        if os.environ.get('CLAUDE_PROJECT_ONLY_ON_FIRST_LIST') == '1' and not first_list.exists():\n"
            "            scope = 'project'; first_list.touch()\n"
            "        payload = ([{'id': 'straw-boss@straw-boss', 'version': installed_version, 'scope': scope, 'enabled': True}] if plugin.exists() else [])\n"
            "    else:\n"
            "        payload = {'installed': ([{'pluginId': 'straw-boss@straw-boss', 'version': installed_version, 'enabled': True, 'source': {'source': 'local', 'path': '/fake/straw-boss'}}] if plugin.exists() else [])}\n"
            "    print(json.dumps(payload)); raise SystemExit\n"
            "if provider == 'claude' and args[:2] == ['plugin', 'uninstall']:\n"
            "    if '--keep-data' not in args:\n"
            "        print('missing --keep-data', file=sys.stderr); raise SystemExit(3)\n"
            "    plugin.unlink(missing_ok=True); print('{}'); raise SystemExit\n"
            "if provider == 'claude' and args[:2] in (['plugin', 'install'], ['plugin', 'update']):\n"
            "    plugin.write_text(version); print('{}'); raise SystemExit\n"
            "if provider == 'codex' and args[:2] == ['plugin', 'remove']:\n"
            "    plugin.unlink(missing_ok=True); print('{}'); raise SystemExit\n"
            "if provider == 'codex' and args[:2] == ['plugin', 'add']:\n"
            "    plugin.write_text(version); print('{}'); raise SystemExit\n"
            "print(f'unexpected {provider} command: {args}', file=sys.stderr)\n"
            "raise SystemExit(2)\n"
        )
        path.chmod(0o755)

    def run_installer(
        self, extra_env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "INSTALLER_STATE": str(self.state_dir),
            "INSTALLER_CAPTURE": str(self.capture),
            "EXPECTED_VERSION": self.version,
        }
        env.update(extra_env or {})
        return subprocess.run(
            ["bash", str(INSTALLER)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def calls(self) -> list[list[str]]:
        return [json.loads(line) for line in self.capture.read_text().splitlines()]

    def test_fresh_install_adds_both_local_marketplaces_and_plugins(self) -> None:
        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(
            any(call[:4] == ["claude", "plugin", "marketplace", "add"] for call in calls)
        )
        self.assertTrue(
            any(call[:3] == ["claude", "plugin", "install"] for call in calls)
        )
        claude_plugin_mutations = [
            call[:3]
            for call in calls
            if call[:2] == ["claude", "plugin"]
            and call[2] in {"install", "uninstall", "update"}
        ]
        self.assertEqual(claude_plugin_mutations, [["claude", "plugin", "install"]])
        self.assertTrue(
            any(call[:4] == ["codex", "plugin", "marketplace", "add"] for call in calls)
        )
        codex_plugin_mutations = [
            call[:3]
            for call in calls
            if call[:2] == ["codex", "plugin"]
            and call[2] in {"add", "remove"}
        ]
        self.assertEqual(codex_plugin_mutations, [["codex", "plugin", "add"]])
        self.assertIn(f"straw-boss {self.version}", result.stdout)

    def test_stale_install_replaces_both_existing_plugins(self) -> None:
        for provider in ("claude", "codex"):
            (self.state_dir / f"{provider}-market").touch()
            (self.state_dir / f"{provider}-plugin").write_text("0.0.1")

        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(
            [
                call[:3]
                for call in calls
                if call[:2] == ["claude", "plugin"]
                and call[2] in {"install", "uninstall", "update"}
            ],
            [
                ["claude", "plugin", "uninstall"],
                ["claude", "plugin", "install"],
            ],
        )
        self.assertIn(
            [
                "claude",
                "plugin",
                "uninstall",
                PLUGIN_ID,
                "--scope",
                "user",
                "--keep-data",
            ],
            calls,
        )
        self.assertTrue(
            any(call[:3] == ["codex", "plugin", "remove"] for call in calls)
        )
        self.assertTrue(any(call[:3] == ["codex", "plugin", "add"] for call in calls))
        self.assertEqual((self.state_dir / "claude-plugin").read_text(), self.version)
        self.assertEqual((self.state_dir / "codex-plugin").read_text(), self.version)

    def test_same_version_install_still_replaces_both_plugins(self) -> None:
        for provider in ("claude", "codex"):
            (self.state_dir / f"{provider}-market").touch()
            (self.state_dir / f"{provider}-plugin").write_text(self.version)

        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertEqual(
            [
                call[:3]
                for call in calls
                if call[:2] == ["claude", "plugin"]
                and call[2] in {"install", "uninstall", "update"}
            ],
            [
                ["claude", "plugin", "uninstall"],
                ["claude", "plugin", "install"],
            ],
        )
        self.assertEqual(
            [
                call[:3]
                for call in calls
                if call[:2] == ["codex", "plugin"]
                and call[2] in {"add", "remove"}
            ],
            [["codex", "plugin", "remove"], ["codex", "plugin", "add"]],
        )
        self.assertEqual((self.state_dir / "codex-plugin").read_text(), self.version)

    def test_existing_plugins_without_versions_are_replaced(self) -> None:
        for provider in ("claude", "codex"):
            (self.state_dir / f"{provider}-market").touch()
            (self.state_dir / f"{provider}-plugin").write_text("")

        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        claude_plugin_mutations = [
            call[:3]
            for call in calls
            if call[:2] == ["claude", "plugin"]
            and call[2] in {"install", "uninstall", "update"}
        ]
        self.assertEqual(
            claude_plugin_mutations,
            [
                ["claude", "plugin", "uninstall"],
                ["claude", "plugin", "install"],
            ],
        )
        codex_plugin_mutations = [
            call[:3]
            for call in calls
            if call[:2] == ["codex", "plugin"]
            and call[2] in {"add", "remove"}
        ]
        self.assertEqual(
            codex_plugin_mutations,
            [["codex", "plugin", "remove"], ["codex", "plugin", "add"]],
        )

    def test_codex_list_failure_stops_before_plugin_mutation(self) -> None:
        (self.state_dir / "codex-market").touch()

        result = self.run_installer({"FAIL_CODEX_PLUGIN_LIST": "1"})

        self.assertNotEqual(result.returncode, 0)
        codex_plugin_mutations = [
            call[:3]
            for call in self.calls()
            if call[:2] == ["codex", "plugin"]
            and call[2] in {"add", "remove"}
        ]
        self.assertEqual(codex_plugin_mutations, [])

    def test_claude_list_failure_stops_before_plugin_mutation(self) -> None:
        (self.state_dir / "claude-market").touch()

        result = self.run_installer({"FAIL_CLAUDE_PLUGIN_LIST": "1"})

        self.assertNotEqual(result.returncode, 0)
        claude_plugin_mutations = [
            call[:3]
            for call in self.calls()
            if call[:2] == ["claude", "plugin"]
            and call[2] in {"install", "uninstall", "update"}
        ]
        self.assertEqual(claude_plugin_mutations, [])

    def test_project_only_claude_install_does_not_trigger_user_uninstall(self) -> None:
        (self.state_dir / "claude-market").touch()
        (self.state_dir / "claude-plugin").write_text(self.version)

        result = self.run_installer({"CLAUDE_PROJECT_ONLY_ON_FIRST_LIST": "1"})

        self.assertEqual(result.returncode, 0, result.stderr)
        claude_plugin_mutations = [
            call[:3]
            for call in self.calls()
            if call[:2] == ["claude", "plugin"]
            and call[2] in {"install", "uninstall", "update"}
        ]
        self.assertEqual(claude_plugin_mutations, [["claude", "plugin", "install"]])

    def test_both_readmes_document_the_checkout_installer(self) -> None:
        for readme in (ROOT / "README.md", ROOT / "README.zh-TW.md"):
            self.assertIn("bash scripts/install.sh", readme.read_text())


if __name__ == "__main__":
    unittest.main()
