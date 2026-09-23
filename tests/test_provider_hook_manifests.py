"""Provider hook discovery must preserve commands and Claude function modules."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def codex_hooks():
    manifest = json.loads((ROOT / '.codex-plugin/plugin.json').read_text())
    return json.loads((ROOT / manifest.get('hooks', 'hooks/hooks.json')).read_text())


class ProviderHookManifestsTest(unittest.TestCase):
    def test_codex_discovered_file_uses_supported_top_level_fields(self):
        # Codex 0.155.1 rejects the entire file on unknown fields, including modules.
        payload = codex_hooks()
        self.assertEqual(set(payload) - {'description', 'hooks'}, set())
        self.assertEqual(set(payload['hooks']), {'SessionStart', 'Stop'})

    def test_provider_commands_stay_in_sync_and_claude_keeps_jev(self):
        claude = json.loads((ROOT / 'hooks/hooks.json').read_text())
        # Only Claude's hook input names the subagent making a tool call.
        shared = {event: entries for event, entries in claude['hooks'].items()
                  if event != 'PreToolUse'}
        self.assertEqual(codex_hooks()['hooks'], shared)
        self.assertEqual(claude['modules'], ['./jev-pruning.ts'])
        self.assertTrue((ROOT / 'hooks' / claude['modules'][0]).is_file())

    def test_codex_commands_run_from_installed_root_with_spaces(self):
        # Codex supplies CLAUDE_PLUGIN_ROOT as its compatibility environment.
        with tempfile.TemporaryDirectory(prefix='installed plugin ') as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            names = ['orchestrator-priming.py', 'dispatched-agent-stop-guard.py',
                     'context-renewal-guard.py']
            for name in names:
                script = scripts / name
                script.write_text('#!/bin/sh\ncat >/dev/null\nprintf "%s\\n" "' + name + '"\n')
                script.chmod(0o755)
            env = {**os.environ, 'CLAUDE_PLUGIN_ROOT': str(root)}
            seen = []
            for entries in codex_hooks()['hooks'].values():
                for entry in entries:
                    for hook in entry['hooks']:
                        result = subprocess.run(hook['command'], shell=True, input='{}',
                                                text=True, capture_output=True, env=env,
                                                cwd='/', timeout=10)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        seen.append(result.stdout.strip())
            self.assertEqual(seen, names)
