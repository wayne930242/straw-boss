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
            "    installed_version = plugin.read_text().strip() if plugin.exists() else None\n"
            "    if provider == 'claude':\n"
            "        payload = ([{'id': 'straw-boss@straw-boss', 'version': installed_version, 'enabled': True}] if installed_version else [])\n"
            "    else:\n"
            "        payload = {'installed': ([{'pluginId': 'straw-boss@straw-boss', 'version': installed_version, 'enabled': True, 'source': {'source': 'local', 'path': '/fake/straw-boss'}}] if installed_version else [])}\n"
            "    print(json.dumps(payload)); raise SystemExit\n"
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

    def run_installer(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALLER)],
            cwd=ROOT,
            env={
                **os.environ,
                "PATH": f"{self.bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
                "INSTALLER_STATE": str(self.state_dir),
                "INSTALLER_CAPTURE": str(self.capture),
                "EXPECTED_VERSION": self.version,
            },
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
        self.assertTrue(
            any(call[:4] == ["codex", "plugin", "marketplace", "add"] for call in calls)
        )
        self.assertTrue(any(call[:3] == ["codex", "plugin", "add"] for call in calls))
        self.assertIn(f"straw-boss {self.version}", result.stdout)

    def test_stale_install_updates_claude_and_replaces_only_codex_plugin(self) -> None:
        for provider in ("claude", "codex"):
            (self.state_dir / f"{provider}-market").touch()
            (self.state_dir / f"{provider}-plugin").write_text("0.0.1")

        result = self.run_installer()

        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertTrue(
            any(call[:3] == ["claude", "plugin", "update"] for call in calls)
        )
        self.assertTrue(
            any(call[:3] == ["codex", "plugin", "remove"] for call in calls)
        )
        self.assertTrue(any(call[:3] == ["codex", "plugin", "add"] for call in calls))
        self.assertEqual((self.state_dir / "claude-plugin").read_text(), self.version)
        self.assertEqual((self.state_dir / "codex-plugin").read_text(), self.version)

    def test_both_readmes_document_the_checkout_installer(self) -> None:
        for readme in (ROOT / "README.md", ROOT / "README.zh-TW.md"):
            self.assertIn("bash scripts/install.sh", readme.read_text())


if __name__ == "__main__":
    unittest.main()
