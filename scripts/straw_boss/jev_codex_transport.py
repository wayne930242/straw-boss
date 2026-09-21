"""Same-pane Codex restart with identity checks and memory-only environment handoff."""
from __future__ import annotations

import json
import os
import shlex
import socket
import subprocess
import time
import tempfile
import uuid
from pathlib import Path

from .herdr.session import run_herdr, run_herdr_raw, session_value, validate_current_process_in_pane
from .jev_private import _copy_parent, private_new_file
from .jev_codex_probe import serialize

VALUE_FLAGS = {'-c', '--config', '-m', '--model', '-p', '--profile', '-s', '--sandbox',
               '-a', '--ask-for-approval', '-C', '--cd', '--add-dir', '--enable', '--disable'}
SWITCH_FLAGS = {'--no-alt-screen', '--dangerously-bypass-approvals-and-sandbox',
                '--dangerously-bypass-hook-trust', '--approve-for-me', '--search', '--strict-config'}


def resume_options(argv: list[str]) -> list[str]:
    """Retain supported launch options, excluding old session/prompt positionals."""
    result, i = [], 1
    if len(argv) > 1 and argv[1] in {'resume', 'fork'}:
        i += 1
        if i < len(argv) and not argv[i].startswith('-'):
            i += 1
    while i < len(argv):
        arg = argv[i]
        name = arg.split('=', 1)[0]
        if name in VALUE_FLAGS:
            if '=' in arg:
                result.append(arg)
            elif i + 1 < len(argv):
                result.extend(argv[i:i + 2])
                i += 1
            else:
                raise ValueError('codex-launch-option-missing-value')
        elif arg in SWITCH_FLAGS:
            result.append(arg)
        elif arg in {'--last', '--all', '--include-non-interactive'}:
            pass
        else:
            # An initial positional prompt has already entered the rollout.
            # Unknown switches can change provider/permission behavior.
            if arg.startswith('-'):
                raise ValueError('codex-launch-option-unsupported')
        i += 1
    return result


def live_agent(pane: str) -> dict:
    agent = run_herdr(['agent', 'get', pane])['result']['agent']
    if agent.get('pane_id') != pane or agent.get('agent') != 'codex':
        raise ValueError('codex-pane-identity-mismatch')
    return agent


def process_info(pane: str) -> dict:
    info = run_herdr(['pane', 'process-info', '--pane', pane])['result']['process_info']
    if info.get('pane_id') != pane:
        raise ValueError('codex-pane-process-mismatch')
    return info


def capture(pane: str, session: str, transcript: str) -> dict:
    validate_current_process_in_pane(pane)
    agent = live_agent(pane)
    if session_value(agent) != session:
        raise ValueError('codex-session-mismatch')
    info = process_info(pane)
    processes = [p for p in info['foreground_processes'] if Path(p['argv'][0]).name == 'codex']
    if len(processes) != 1:
        raise ValueError('codex-foreground-process-unavailable')
    process = processes[0]
    rows = [json.loads(line) for line in Path(transcript).read_text().splitlines()]
    meta = next(row['payload'] for row in rows if row['type'] == 'session_meta')
    if meta['id'] != session:
        raise ValueError('codex-rollout-session-mismatch')
    return {'pane_id': pane, 'session_id': session, 'terminal_id': agent['terminal_id'],
        'pid': process['pid'], 'shell_pid': info['shell_pid'], 'executable': process['argv'][0],
        'options': resume_options(process['argv']), 'cwd': process['cwd'],
        'transcript': str(Path(transcript).resolve()),
        'codex_home': str(Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).resolve())}


def validate_original(request: dict, *, idle: bool = True) -> None:
    agent = live_agent(request['pane_id'])
    info = process_info(request['pane_id'])
    if (session_value(agent) != request['session_id'] or agent['terminal_id'] != request['terminal_id']
            or info['shell_pid'] != request['shell_pid']
            or request['pid'] not in [p['pid'] for p in info['foreground_processes']]
            or (idle and agent.get('agent_status') not in {'idle', 'done'})):
        raise ValueError('codex-renewal-source-changed')


def register_rollout(home: Path, rows: list[dict], session: str) -> Path:
    """Publish a new UUID in Codex's session catalog, with no source overwrite."""
    date = time.strftime('%Y/%m/%d')
    parts = ['sessions', *date.split('/')]
    with _copy_parent(home) as base:
        fd = os.dup(base)
        try:
            for part in parts:
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                info = os.fstat(child)
                if info.st_uid != os.getuid() or info.st_mode & 0o022:
                    os.close(child)
                    raise ValueError('unsafe-codex-session-directory')
                os.close(fd)
                fd = child
            name = f'rollout-{time.strftime("%Y-%m-%dT%H-%M-%S")}-{session}.jsonl'
            with private_new_file(fd, name) as file:
                file.write(serialize(rows))
            return home.joinpath(*parts, name)
        finally:
            os.close(fd)


def shell_ready(request: dict) -> bool:
    info = process_info(request['pane_id'])
    return (info['shell_pid'] == request['shell_pid']
            and info['foreground_process_group_id'] == request['shell_pid'])


def wait_for(predicate, seconds: int = 60) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            if predicate():
                return True
        except (ValueError, OSError, KeyError):
            pass
        time.sleep(0.25)
    return False


def launch(request: dict, session: str, prompt: str) -> bool:
    if not shell_ready(request):
        raise ValueError('codex-renewal-shell-unavailable')
    # The shell starts a tiny client. The detached deliverer sends its inherited
    # environment over a private Unix socket; API keys never enter argv/files.
    temporary = tempfile.TemporaryDirectory(prefix='sbjev-', dir=Path('/tmp').resolve())
    path = Path(temporary.name) / 'launch.sock'
    listener = socket.socket(socket.AF_UNIX)
    listener.settimeout(30)
    try:
        listener.bind(str(path))
        os.chmod(path, 0o600)
        listener.listen(1)
        client = Path(__file__).resolve().parents[1] / 'jev-codex-resume.py'
        command = shlex.join(['python3', str(client), '--socket', str(path)])
        run_herdr_raw(['pane', 'run', request['pane_id'], command])
        connection, _ = listener.accept()
        with connection:
            env = dict(os.environ)
            env.pop('CODEX_THREAD_ID', None)
            env.pop('CODEX_INTERNAL_ORIGINATOR_OVERRIDE', None)
            env['CODEX_HOME'] = request['codex_home']
            message = {'argv': [request['executable'], 'resume', session, *request['options'], prompt],
                       'env': env, 'cwd': request['cwd']}
            connection.sendall(json.dumps(message).encode())
    finally:
        listener.close()
        temporary.cleanup()
    def resumed():
        agent = live_agent(request['pane_id'])
        return (agent.get('terminal_id') == request['terminal_id']
                and session_value(agent) == session)
    return wait_for(resumed)


def swap(request: dict, session: str, prompt: str) -> bool:
    validate_original(request)
    run_herdr(['agent', 'prompt', request['pane_id'], '/quit'])
    if not wait_for(lambda: shell_ready(request)):
        raise ValueError('codex-renewal-exit-unconfirmed')
    return launch(request, session, prompt)
