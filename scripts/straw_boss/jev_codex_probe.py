"""Backend accounting through isolated Codex copied-history resumes."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import uuid
from pathlib import Path

from .jev_codex import CALLS, history_from_rows, replacement_rows
from .jev_private import private_read, private_replace, root

PROBE_PROMPT = 'This is an input-token accounting probe. Reply with exactly OK. Use no tools and perform no task actions.'


def serialize(rows: list[dict]) -> str:
    return ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)


def clone_rows(rows: list[dict], history: list[dict], session: str) -> list[dict]:
    result = replacement_rows(rows, history)
    meta = next(row['payload'] for row in result if row['type'] == 'session_meta')
    meta['id'] = session
    if 'session_id' in meta:
        meta['session_id'] = session
    meta.pop('forked_from_id', None)
    return result


def measure_one(rows: list[dict], history: list[dict], directory: Path,
                codex_home: Path, model: str, effort: str) -> dict:
    session = str(uuid.uuid4())
    workspace = directory / 'workspace'
    # All probe artifacts, including the short-lived credential copy, use the
    # same descriptor-relative private store boundary as recovery records.
    private_replace(workspace / 'AGENTS.md', 'Reply OK for the accounting probe. Use no tools.\n')
    instructions = directory / 'instructions.md'
    meta = next(row['payload'] for row in rows if row['type'] == 'session_meta')
    base = (meta.get('base_instructions') or {}).get('text', '')
    # Equal-length fresh prefixes avoid accidentally measuring a cached replay.
    nonce = ' '.join(str(int(c, 16) % 10) for c in uuid.uuid4().hex)
    private_replace(instructions, f'Accounting instance: {nonce}.\n' + base)
    flags = ['apps', 'hooks', 'codex_hooks', 'plugins', 'memories', 'chronicle',
             'multi_agent', 'multi_agent_v2', 'shell_tool', 'apply_patch_freeform',
             'browser_use', 'computer_use', 'image_generation', 'view_image',
             'js_repl', 'web_search', 'shell_snapshot']
    config = (f'model = {json.dumps(model)}\nmodel_reasoning_effort = {json.dumps(effort)}\n'
              f'model_instructions_file = {json.dumps(str(instructions))}\n'
              'approval_policy = "never"\nsandbox_mode = "read-only"\nweb_search = "disabled"\n'
              'model_auto_compact_token_limit = 1000000000\n'
              '[features]\n' + ''.join(f'{flag} = false\n' for flag in flags))
    private_replace(directory / 'config.toml', config)
    auth = directory / 'auth.json'
    copied = clone_rows(rows, history, session)
    for row in copied:
        if row['type'] == 'session_meta':
            row['payload'].update(cwd=str(workspace), base_instructions={'text': base},
                                  runtime_workspace_roots=[str(workspace)])
        elif row['type'] == 'turn_context':
            row['payload'].update(cwd=str(workspace), workspace_roots=[str(workspace)],
                approval_policy='never', sandbox_policy={'type': 'read-only'})
            row['payload'].pop('permission_profile', None)
    rollout = directory / 'sessions/2000/01/01' / f'rollout-2000-01-01T00-00-00-{session}.jsonl'
    private_replace(rollout, serialize(copied))
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('HERDR_', 'CODEX_', 'STRAW_BOSS_')) and k != 'TYPESAFE_API_KEY'}
    env['CODEX_HOME'] = str(directory)
    try:
        private_replace(auth, (codex_home / 'auth.json').read_text())
        result = subprocess.run(['codex', 'exec', '--sandbox', 'read-only', 'resume',
            session, '--skip-git-repo-check', '--json', PROBE_PROMPT],
            cwd=workspace, env=env, capture_output=True, text=True, timeout=240)
        private_replace(directory / 'events.jsonl', result.stdout)
        if result.returncode:
            raise ValueError('codex-probe-failed')
        fresh = [json.loads(line) for line in private_read(rollout).splitlines()][len(copied):]
        if any(row['type'] == 'compacted' or
               (row['type'] == 'response_item' and row['payload']['type'] in CALLS)
               for row in fresh):
            raise ValueError('codex-probe-changed-history')
        usages = [row['payload']['info']['last_token_usage'] for row in fresh
                  if row['type'] == 'event_msg' and row['payload'].get('type') == 'token_count'
                  and row['payload'].get('info')]
        if not usages:
            raise ValueError('codex-probe-no-usage')
        return usages[-1]
    finally:
        from .jev_private import private_unlink
        private_unlink(auth)


def measure(rows: list[dict], candidate: list[dict], run_id: str,
            codex_home: Path) -> tuple[dict, dict, dict]:
    contexts = [row['payload'] for row in rows if row['type'] == 'turn_context']
    if not contexts or not contexts[-1].get('model'):
        raise ValueError('codex-probe-missing-model')
    model = contexts[-1]['model']
    effort = contexts[-1].get('effort') or 'low'
    before = measure_one(rows, history_from_rows(rows), root() / 'probes' / run_id / 'before',
                         codex_home, model, effort)
    after = measure_one(rows, candidate, root() / 'probes' / run_id / 'after',
                        codex_home, model, effort)
    return before, after, {'backend_model': model, 'effort': effort,
        'probe_root': str(root() / 'probes' / run_id)}
