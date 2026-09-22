from __future__ import annotations

import json
import os
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class AdoptWorkerEndpointTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    """A Codex worker that restarts in its own pane keeps the pane and loses the
    terminal it was recorded against, which is its whole identity until a
    conversation id is on record."""

    def restarted_worker(self, slug: str, **overrides: str):
        path, _ = self.write_dispatch('codex', slug=slug)
        instruction = self.set_worker_endpoint(path)
        # write_dispatch records no tab; the relocation check needs one on file.
        instruction['herdr_tab_id'] = 'worker-tab'
        path.write_text(json.dumps(instruction, indent=2) + '\n')
        fake_bin, capture = self.install_fake_herdr()
        env = {
            'PATH': f'{fake_bin}{os.pathsep}{os.environ.get("PATH", "")}',
            'HERDR_CAPTURE': str(capture), 'HERDR_PANE_ID': 'main-pane',
            'HERDR_SESSIONS': json.dumps(
                {'worker-pane': 'restarted-session', 'main-pane': 'main-session'}),
            'HERDR_AGENT_KINDS': json.dumps({'worker-pane': 'codex', 'main-pane': 'claude'}),
            'HERDR_TERMINAL_IDS': json.dumps({'worker-pane': 'terminal-after-restart'}),
            'HERDR_PROMPT_ACCEPTED': '1',
        }
        env.update(overrides)
        return path, instruction, env

    def run_adopt(self, path: Path, env: dict[str, str], session: str = 'restarted-session'):
        return self.run_script(
            'adopt-worker-endpoint.py', '--instruction-path', str(path),
            '--worker-session-id', session, extra_env=env,
        )

    def test_records_the_live_conversation_and_terminal(self):
        path, instruction, env = self.restarted_worker('restart')
        self.assertIsNone(instruction['session_id'])
        self.assertEqual(instruction['herdr_terminal_id'], 'terminal-worker-pane')

        result = self.run_adopt(path, env)
        self.assertEqual(result.returncode, 0, result.stderr)

        saved = json.loads(path.read_text())
        self.assertEqual(saved['session_id'], 'restarted-session')
        self.assertEqual(saved['herdr_terminal_id'], 'terminal-after-restart')
        # Routing only: the contract, task and status are untouched.
        for key in ('contract_path', 'contract_sha256', 'task', 'status', 'herdr_pane_id'):
            self.assertEqual(saved[key], instruction[key])
        adoption, = saved['worker_endpoint_adoptions']
        self.assertEqual(adoption['before'],
                         {'session_id': None, 'herdr_terminal_id': 'terminal-worker-pane'})
        self.assertEqual(adoption['after'],
                         {'session_id': 'restarted-session',
                          'herdr_terminal_id': 'terminal-after-restart'})

    def test_adopted_endpoint_carries_a_worker_message(self):
        """The point of the repair: delivery works again afterwards."""
        path, _, env = self.restarted_worker('delivers')
        refused = self.run_script(
            'send-dispatch-message.py', '--instruction-path', str(path),
            '--to', 'worker', '--intent', 'inform', '--message', 'A verified finding.',
            extra_env=env,
        )
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('terminal mismatch', refused.stderr)

        self.assertEqual(self.run_adopt(path, env).returncode, 0)

        delivered = self.run_script(
            'send-dispatch-message.py', '--instruction-path', str(path),
            '--to', 'worker', '--intent', 'inform', '--message', 'A verified finding.',
            extra_env=env,
        )
        self.assertEqual(delivered.returncode, 0, delivered.stderr)

    def test_refuses_a_session_the_pane_does_not_corroborate(self):
        path, _, env = self.restarted_worker('uncorroborated')
        result = self.run_adopt(path, env, session='a-session-i-made-up')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('cannot corroborate', result.stderr)
        self.assertIsNone(json.loads(path.read_text())['session_id'])

    def test_refuses_a_different_conversation_rather_than_repointing(self):
        path, _, env = self.restarted_worker('stranger')
        instruction = json.loads(path.read_text())
        instruction['session_id'] = 'the-dispatched-conversation'
        path.write_text(json.dumps(instruction, indent=2) + '\n')

        result = self.run_adopt(path, env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('different agent', result.stderr)
        self.assertEqual(json.loads(path.read_text())['session_id'],
                         'the-dispatched-conversation')

    def test_refuses_a_relocated_worker(self):
        for field, variable, value in (('tab_id', 'HERDR_AGENT_TAB_ID', 'another-tab'),
                                       ('cwd', 'HERDR_AGENT_CWD', '/somewhere/else')):
            with self.subTest(field=field):
                path, _, env = self.restarted_worker(f'moved-{field}', **{variable: value})
                result = self.run_adopt(path, env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('not a relocated worker', result.stderr)
                self.assertIsNone(json.loads(path.read_text())['session_id'])

    def test_refuses_a_different_agent_kind(self):
        path, _, env = self.restarted_worker(
            'rekinded', HERDR_AGENT_KINDS=json.dumps(
                {'worker-pane': 'claude', 'main-pane': 'claude'}))
        result = self.run_adopt(path, env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('dispatch the work again', result.stderr)

    def test_refuses_a_caller_that_is_not_the_coordinator(self):
        path, _, env = self.restarted_worker('outsider')
        result = self.run_adopt(path, {**env, 'HERDR_PANE_ID': 'some-other-pane'})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('sender pane mismatch', result.stderr)
        self.assertIsNone(json.loads(path.read_text())['session_id'])


if __name__ == '__main__':
    unittest.main()
