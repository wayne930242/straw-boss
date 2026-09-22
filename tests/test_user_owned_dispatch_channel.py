from __future__ import annotations

import json
import os
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture


class UserOwnedDispatchChannelTests(DispatchedAgentLifecycleFixture, unittest.TestCase):
    def test_user_checkpoint_refuses_directing_intents_before_transport(self):
        for kind in ('claude', 'codex'):
            for status in ('awaiting-user-input', 'awaiting-authorization'):
                for intent in ('redirect', 'control'):
                    with self.subTest(kind=kind, status=status, intent=intent):
                        path, _ = self.write_dispatch(kind, slug=f"{kind}-{status}-{intent}")
                        self.set_worker_endpoint(path)
                        path.with_suffix('.status.json').write_text(json.dumps({'status': status}))
                        fake_bin, capture = self.install_fake_herdr()
                        capture.unlink(missing_ok=True)
                        result = self.run_script(
                            'send-dispatch-message.py', '--instruction-path', str(path),
                            '--to', 'worker', '--intent', intent,
                            '--message', '/compact' if intent == 'control' else 'A verified fact.',
                            extra_env={
                                'PATH': f'{fake_bin}{os.pathsep}{os.environ.get("PATH", "")}',
                                'HERDR_CAPTURE': str(capture), 'HERDR_PANE_ID': 'main-pane',
                            },
                        )
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn(status, result.stderr)
                        self.assertIn('directs the worker', result.stderr)
                        self.assertIn('--intent inform', result.stderr)
                        self.assertFalse(capture.exists())
                        self.assertFalse(path.with_suffix('.messages.jsonl').exists())

    def test_user_checkpoint_keeps_inform_open_for_the_coordinator(self):
        """The user owns the checkpoint's decision, not its information."""
        for kind in ('claude', 'codex'):
            for status in ('awaiting-user-input', 'awaiting-authorization'):
                with self.subTest(kind=kind, status=status):
                    path, _ = self.write_dispatch(kind, slug=f"open-{kind}-{status}")
                    self.set_worker_endpoint(path)
                    path.with_suffix('.status.json').write_text(json.dumps({'status': status}))
                    fake_bin, capture = self.install_fake_herdr()
                    capture.unlink(missing_ok=True)
                    result = self.run_script(
                        'send-dispatch-message.py', '--instruction-path', str(path),
                        '--to', 'worker', '--intent', 'inform',
                        '--message', 'A verified finding the worker needs.',
                        extra_env={
                            'PATH': f'{fake_bin}{os.pathsep}{os.environ.get("PATH", "")}',
                            'HERDR_CAPTURE': str(capture), 'HERDR_PANE_ID': 'main-pane',
                            'HERDR_SESSIONS': json.dumps(
                                {'worker-pane': 'worker-session', 'main-pane': 'main-session'}),
                            'HERDR_AGENT_KIND': kind, 'HERDR_PROMPT_ACCEPTED': '1',
                        },
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue(capture.exists())
                    self.assertTrue(path.with_suffix('.messages.jsonl').exists())
                    # Informing leaves the user's checkpoint exactly where it was.
                    saved = json.loads(path.with_suffix('.status.json').read_text())
                    self.assertEqual(saved, {'status': status})

    def test_user_checkpoint_does_not_strand_replies_or_peer_traffic(self):
        for intent in ('reply', 'question', 'answer'):
            with self.subTest(intent=intent):
                path, _ = self.write_dispatch('claude', slug=f'quiet-{intent}')
                self.set_worker_endpoint(path)
                path.with_suffix('.status.json').write_text(
                    json.dumps({'status': 'awaiting-user-input'}))
                fake_bin, capture = self.install_fake_herdr()
                capture.unlink(missing_ok=True)
                extra_args = []
                if intent in ('question', 'answer'):
                    sender, _ = self.write_dispatch('claude', slug=f'peer-quiet-{intent}')
                    self.set_worker_endpoint(sender)
                    extra_args = ['--sender-instruction-path', str(sender)]
                    if intent == 'answer':
                        extra_args += ['--in-reply-to', 'question-id']
                result = self.run_script(
                    'send-dispatch-message.py', '--instruction-path', str(path),
                    '--to', 'worker', '--intent', intent, '--message', 'A verified fact.',
                    *extra_args,
                    extra_env={
                        'PATH': f'{fake_bin}{os.pathsep}{os.environ.get("PATH", "")}',
                        'HERDR_CAPTURE': str(capture), 'HERDR_PANE_ID': 'main-pane',
                    },
                )
                self.assertNotIn('directs the worker', result.stderr)

    def test_plan_status_wins_over_standalone_status_and_newer_progress(self):
        path, _ = self.write_dispatch('claude')
        instruction = json.loads(path.read_text())
        instruction.update(plan_id='p-checkpoint', task_id='guard')
        path.write_text(json.dumps(instruction))
        plan_status = self.home / '.straw-boss/plans/checkpoint/status/guard.json'
        plan_status.parent.mkdir(parents=True)
        plan_status.write_text(json.dumps({'status': 'awaiting-user-input'}))
        path.with_suffix('.status.json').write_text(json.dumps({'status': 'in-progress'}))
        path.with_suffix('.progress.jsonl').write_text('{"note":"newer progress"}\n')
        result = self.run_script(
            'send-dispatch-message.py', '--instruction-path', str(path),
            '--to', 'worker', '--intent', 'redirect', '--message', 'A fact.',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('awaiting-user-input', result.stderr)
        self.assertIn('directs the worker', result.stderr)

    def test_malformed_status_reports_failure_before_transport(self):
        for index, raw in enumerate(('broken json', '[]', 'null')):
            with self.subTest(raw=raw):
                path, _ = self.write_dispatch('claude', slug=f'bad-status-{index}')
                path.with_suffix('.status.json').write_text(raw)
                result = self.run_script(
                    'send-dispatch-message.py', '--instruction-path', str(path),
                    '--to', 'worker', '--intent', 'inform', '--message', 'A fact.',
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('cannot read dispatch status', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_stale_reply_hint_preserves_user_route(self):
        path, _ = self.write_dispatch('claude')
        self.set_worker_endpoint(path)
        status = path.with_suffix('.status.json')
        status.write_text(json.dumps({'status': 'awaiting-user-input'}))
        os.utime(status, (1, 1))
        path.with_suffix('.progress.jsonl').write_text('{"note":"resumed"}\n')
        result = self.run_script(
            'reply-to-worker.py', '--worker-instruction-path', str(path), '--reply', 'A fact.',
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('directly to the user', result.stderr)
        self.assertNotIn('--intent inform', result.stderr)

    def test_question_reopens_checkpoint_before_requesting_main_agent_reply(self):
        for status in ('awaiting-user-input', 'awaiting-authorization'):
            with self.subTest(status=status):
                path, _ = self.write_dispatch('claude', slug=status)
                self.set_worker_endpoint(path)
                path.with_suffix('.status.json').write_text(json.dumps({'status': status}))
                fake_bin, capture = self.install_fake_herdr()
                capture.unlink(missing_ok=True)
                env = {
                    'PATH': f'{fake_bin}{os.pathsep}{os.environ.get("PATH", "")}',
                    'HERDR_CAPTURE': str(capture), 'HERDR_PANE_ID': 'worker-pane',
                    'HERDR_SESSIONS': json.dumps({'worker-pane': 'worker-session', 'main-pane': 'main-session'}),
                    'HERDR_PROMPT_ACCEPTED': '1',
                }
                result = self.run_script(
                    'send-dispatch-message.py', '--instruction-path', str(path),
                    '--to', 'main', '--intent', 'question', '--message', 'Which shared port is free?',
                    extra_env=env,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('--status awaiting-main-agent', result.stderr)
                self.assertFalse(capture.exists())
                reported = self.run_script(
                    'report-task-status.py', '--instruction-path', str(path),
                    '--status', 'awaiting-main-agent', '--note', 'Need the shared port assignment.',
                    extra_env=env,
                )
                self.assertEqual(reported.returncode, 0, reported.stderr)
                asked = self.run_script(
                    'send-dispatch-message.py', '--instruction-path', str(path),
                    '--to', 'main', '--intent', 'question', '--message', 'Which shared port is free?',
                    extra_env=env,
                )
                self.assertEqual(asked.returncode, 0, asked.stderr)
                replied = self.run_script(
                    'reply-to-worker.py', '--worker-instruction-path', str(path),
                    '--reply', 'Port 4321 is free.', extra_env={**env, 'HERDR_PANE_ID': 'main-pane'},
                )
                self.assertEqual(replied.returncode, 0, replied.stderr)
                saved = json.loads(path.with_suffix('.status.json').read_text())
                self.assertIn('resolved_by_main_agent_at', saved)
