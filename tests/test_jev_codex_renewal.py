"""Production renewal contract at guard, transaction, and transport boundaries."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from straw_boss import jev_codex_renewal as runtime, jev_codex_scoring as scoring
from straw_boss import jev_codex_transport as transport
from straw_boss.jev_codex import configuration, history_from_rows
from straw_boss.jev_private import private_replace, root
from straw_boss.renewal import dump_json

ROOT = Path(__file__).resolve().parents[1]


def history():
    items = [{'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Retain the next action.'}]}]
    for i in range(12):
        items += [{'type': 'function_call', 'call_id': f'c{i}', 'name': 'exec',
                   'arguments': json.dumps({'cmd': 'cat AGENTS.md' if i == 2 else 'ls'})},
                  {'type': 'function_call_output', 'call_id': f'c{i}', 'output': 'old output ' * 100},
                  {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': f'Checked {i}.'}]}]
    return items


def rows():
    result = [{'type': 'session_meta', 'payload': {'id': 'source', 'cwd': '/tmp', 'base_instructions': {'text': 'instructions'}}},
              {'type': 'turn_context', 'payload': {'model': 'gpt-6-astra', 'effort': 'low'}}]
    result += [{'type': 'response_item', 'payload': item} for item in history()]
    result.append({'type': 'event_msg', 'payload': {'type': 'token_count', 'info': {'last_token_usage': {'input_tokens': 200001}}}})
    for r in result:
        r['timestamp'] = '2026-09-21T00:00:00Z'
    return result


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv('STRAW_BOSS_HOME', str(tmp_path))
    monkeypatch.setenv('STRAW_BOSS_JEV', '1')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'test-key')
    return tmp_path


@pytest.mark.parametrize('key', [None, '', ' \t\n'])
def test_disabled_guard_silent_jev_fallback(home, key):
    source = home / 'rollout-source.jsonl'
    source.write_text(runtime.probe.serialize(rows()))
    env = dict(os.environ)
    if key is None:
        env.pop('TYPESAFE_API_KEY', None)
    else:
        env['TYPESAFE_API_KEY'] = key
    env.pop('HERDR_PANE_ID', None)
    payload = {'session_id': 'source', 'transcript_path': str(source), 'cwd': str(home)}
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/context-renewal-guard.py')],
        input=json.dumps(payload), env=env, capture_output=True, text=True)
    assert result.returncode == 0
    assert 'Jev' not in result.stdout
    assert '--transcript-path' not in result.stdout
    assert '200000' in result.stdout
    assert not (home / 'jev').exists()


def test_enabled_guard_at_200k_and_turn_loop(home):
    source = home / 'rollout-source.jsonl'
    source.write_text(runtime.probe.serialize(rows()))
    env = {**os.environ, 'HERDR_PANE_ID': 'test'}
    payload = {'session_id': 'source', 'transcript_path': str(source), 'cwd': str(home)}
    def run():
        return subprocess.run([sys.executable, str(ROOT / 'scripts/context-renewal-guard.py')],
            input=json.dumps(payload), env=env, capture_output=True, text=True)
    reason = json.loads(run().stdout)['reason']
    assert '200000' in reason and '--transcript-path' in reason and 'Jev' in reason
    payload['stop_hook_active'] = True
    assert run().stdout == ''
    payload.pop('stop_hook_active')
    data = rows(); data[-1]['payload']['info']['last_token_usage']['input_tokens'] = 200000
    source.write_text(runtime.probe.serialize(data))
    assert run().stdout == ''


def test_live_scoring_locks_and_budgets(home):
    criteria, policy = configuration()
    seen = []
    def ask(body):
        seen.append(body)
        return {'model': 'jev-test', 'usage': {'input_tokens': 123},
                'answers': {key: {'noul': .1} for key in body['questions']}}
    with patch.object(scoring, 'request', side_effect=ask):
        scores, metrics = scoring.score(history(), criteria, policy)
    assert 'c2' not in scores  # governing source
    assert 'c11' not in scores  # recent messages
    assert 'c0' in scores
    for body in seen:
        assert scoring.estimate_tokens(scoring.encoded(body['state'])) <= policy['max_state_tokens']
        assert scoring.estimate_tokens(scoring.encoded(body)) <= policy['max_request_tokens']
        assert not any(key.endswith('_c2') for key in body['questions'])
    assert sum(m['input_tokens'] for m in metrics) == 123 * len(seen)


@pytest.mark.parametrize('value', [None, True, -1, 2, float('nan'), {}, []])
def test_invalid_live_scores_fall_back(home, value):
    criteria, policy = configuration()
    with patch.object(scoring, 'request', side_effect=lambda body: {'model': 'jev-test',
        'usage': {'input_tokens': 1}, 'answers': {k: {'noul': value} for k in body['questions']}}):
        with pytest.raises(ValueError):
            scoring.score(history(), criteria, policy)


@pytest.fixture
def transaction(home):
    source = home / 'rollout-source.jsonl'
    original = runtime.probe.serialize(rows()); source.write_text(original)
    request_path = root() / 'requests/test.json'
    request = {'run_id': 'test', 'pane_id': 'test-pane', 'session_id': 'source',
               'terminal_id': 'terminal', 'transcript': str(source), 'codex_home': str(home / 'codex')}
    private_replace(request_path, json.dumps(request))
    path = home / 'renewal.json'
    dump_json(path, {'jev_request': str(request_path), 'session_id': 'source', 'status': 'pending'})
    metrics = [{'model': 'jev-test', 'input_tokens': 99, 'latency_ms': 1}]
    scores = {f'c{i}': {'keepCall': 0, 'keepResult': 0} for i in range(12)}
    with patch.object(transport, 'validate_original'), \
         patch.object(scoring, 'score', return_value=(scores, metrics)), \
         patch.object(runtime.probe, 'measure', return_value=(
             {'input_tokens': 200001, 'cached_input_tokens': 0},
             {'input_tokens': 140000, 'cached_input_tokens': 0}, {})):
        yield path, source, original


def test_candidate_saved_before_swap_with_lossless_recovery(transaction, home):
    path, source, original = transaction
    registered = home / 'candidate.jsonl'
    def register(home_, candidate_rows, session):
        snapshot = json.loads((root() / 'runs/test.json').read_text())
        assert snapshot['original_rollout'] == original
        assert snapshot['candidate_rows'] == candidate_rows
        assert candidate_rows[-1]['type'] == 'compacted'
        registered.write_text(runtime.probe.serialize(candidate_rows))
        return registered
    with patch.object(transport, 'register_rollout', side_effect=register), \
         patch.object(transport, 'swap', return_value=True) as swap:
        assert runtime.deliver(path) is True
        assert swap.call_args.args[0]['pane_id'] == 'test-pane'
    assert source.read_text() == original
    record = json.loads((root() / 'benchmark.jsonl').read_text())
    assert record['application']['status'] == 'resumed'
    assert record['outcome'] is None
    assert (root() / 'runs/test.json').stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('mode', ['gate', 'cached', 'judge', 'archive'])
def test_preparation_failure_never_swaps(transaction, mode):
    path, source, original = transaction
    with patch.object(transport, 'swap') as swap:
        if mode == 'gate':
            with patch.object(runtime.probe, 'measure', return_value=(
                {'input_tokens': 200001, 'cached_input_tokens': 0},
                {'input_tokens': 190000, 'cached_input_tokens': 0}, {})):
                assert runtime.deliver(path) is False
        elif mode == 'cached':
            with patch.object(runtime.probe, 'measure', return_value=(
                {'input_tokens': 200001, 'cached_input_tokens': 1},
                {'input_tokens': 100000, 'cached_input_tokens': 0}, {})):
                assert runtime.deliver(path) is False
        elif mode == 'judge':
            with patch.object(scoring, 'score', side_effect=TimeoutError):
                assert runtime.deliver(path) is False
        else:
            with patch.object(runtime, 'save', side_effect=OSError):
                assert runtime.deliver(path) is False
        swap.assert_not_called()
    assert source.read_text() == original


def test_source_advanced_does_not_clear_new_work(transaction):
    path, source, original = transaction
    def advance(*args):
        source.write_text(original + '\n')
        return {'input_tokens': 200001, 'cached_input_tokens': 0}, {'input_tokens': 100000, 'cached_input_tokens': 0}, {}
    with patch.object(runtime.probe, 'measure', side_effect=advance), patch.object(transport, 'swap') as swap:
        with pytest.raises(ValueError, match='source-advanced'):
            runtime.deliver(path)
        swap.assert_not_called()
    assert json.loads(path.read_text())['status'] == 'cancelled'


def test_live_input_is_conservative_gate_denominator(transaction):
    path, _, _ = transaction
    with patch.object(runtime.probe, 'measure', return_value=(
        {'input_tokens': 100000, 'cached_input_tokens': 0},
        {'input_tokens': 85000, 'cached_input_tokens': 0}, {})):
        assert runtime.deliver(path) is False
    record = json.loads((root() / 'benchmark.jsonl').read_text())
    assert record['reduction_pct'] == 15
    assert record['gate_reduction_pct'] < 10


def test_resume_keeps_launch_permissions_and_model():
    assert transport.resume_options(['codex', '--model', 'gpt-6-astra', '-c', 'model_reasoning_effort=high',
        '--dangerously-bypass-approvals-and-sandbox', 'original prompt']) == [
        '--model', 'gpt-6-astra', '-c', 'model_reasoning_effort=high', '--dangerously-bypass-approvals-and-sandbox']
    assert transport.resume_options(['codex', 'resume', 'old-id', '-p', 'work', 'old prompt']) == ['-p', 'work']
    with pytest.raises(ValueError):
        transport.resume_options(['codex', '--remote', 'server'])


def test_register_creates_new_private_rollout_and_rejects_symlink(home):
    codex = home / 'codex'; codex.mkdir(mode=0o700)
    session = 'fresh-id'
    candidate = runtime.probe.clone_rows(rows(), history(), session)
    path = transport.register_rollout(codex, candidate, session)
    assert path.stat().st_mode & 0o777 == 0o600
    assert history_from_rows([json.loads(x) for x in path.read_text().splitlines()]) == history()
    other = home / 'other'; other.mkdir()
    bad = home / 'bad'; bad.mkdir(mode=0o700); (bad / 'sessions').symlink_to(other)
    with pytest.raises(OSError):
        transport.register_rollout(bad, candidate, 'other-id')
    assert list(other.iterdir()) == []


def test_source_advance_on_gate_miss_keeps_new_work(transaction):
    path, source, original = transaction
    def advance(*args):
        source.write_text(original + '\n')
        return {'input_tokens': 200001, 'cached_input_tokens': 0}, {'input_tokens': 199000, 'cached_input_tokens': 0}, {}
    with patch.object(runtime.probe, 'measure', side_effect=advance):
        with pytest.raises(ValueError, match='source-advanced'):
            runtime.deliver(path)
    assert json.loads(path.read_text())['status'] == 'cancelled'


def test_newer_renewal_record_survives_old_preparation(transaction):
    path, _, _ = transaction
    def replace_record(*args):
        dump_json(path, {'status': 'pending', 'jev_request': 'new-request'})
        return {'input_tokens': 200001, 'cached_input_tokens': 0}, {'input_tokens': 100000, 'cached_input_tokens': 0}, {}
    with patch.object(runtime.probe, 'measure', side_effect=replace_record):
        with pytest.raises(ValueError, match='record-replaced'):
            runtime.deliver(path)
    assert json.loads(path.read_text())['jev_request'] == 'new-request'


def test_failed_candidate_start_restores_original_before_fallback(transaction, home):
    path, _, _ = transaction
    registered = home / 'candidate.jsonl'
    def register(home_, candidate_rows, session):
        registered.write_text(runtime.probe.serialize(candidate_rows))
        return registered
    with patch.object(transport, 'register_rollout', side_effect=register), \
         patch.object(transport, 'validate_original', side_effect=[None, None, ValueError('exited')]), \
         patch.object(transport, 'swap', return_value=False), \
         patch.object(transport, 'shell_ready', return_value=True), \
         patch.object(transport, 'launch', return_value=True) as launch, \
         patch.object(transport, 'run_herdr'):
        assert runtime.deliver(path) is False
        assert launch.call_args.args[1] == 'source'
    assert 'jev_candidate_session' not in json.loads(path.read_text())
    assert json.loads((root() / 'benchmark.jsonl').read_text())['decision'] == 'fallback'


@pytest.mark.parametrize('live_session,should_clear', [('source', True), ('new-work', False)])
def test_deliverer_corrupt_request_falls_back_only_for_original(home, monkeypatch, live_session, should_clear):
    spec = importlib.util.spec_from_file_location('deliver_probe', ROOT / 'scripts/deliver-renewal.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    path = home / 'renewal.json'
    dump_json(path, {'status': 'pending', 'session_id': 'source', 'jev_request': 'missing'})
    monkeypatch.setattr(sys, 'argv', ['deliver-renewal.py', '--pane-id', 'p'])
    calls = []
    monkeypatch.setattr(module, 'renewal_root', lambda: home)
    monkeypatch.setattr(module, 'record_path', lambda _: path)
    monkeypatch.setattr(module, 'herdr', lambda *args: calls.append(args) or 0)
    with patch.object(runtime, 'deliver', side_effect=FileNotFoundError), \
         patch.object(transport, 'live_agent', return_value={'agent_status': 'idle',
             'agent_session': {'value': live_session}}):
        module.main()
    assert any(call[:4] == ('agent', 'prompt', 'p', '/clear') for call in calls) is should_clear


def test_equal_length_distinct_outputs_change_scoring_request():
    criteria, policy = configuration()
    a = history(); b = copy.deepcopy(a)
    a[2]['output'] = 'AAAAAAAA'; b[2]['output'] = 'BBBBBBBB'
    assert scoring.scoring_batches(a, criteria, policy) != scoring.scoring_batches(b, criteria, policy)


def test_full_long_result_coverage_and_max_chunk_score(home):
    criteria, policy = configuration()
    policy = {**policy, 'max_state_tokens': 5000, 'max_request_tokens': 10000}
    original = history(); original[2]['output'] = 'X' * 30000 + ' IMPORTANT_MIDDLE ' + 'Y' * 30000
    batches = scoring.scoring_batches(original, criteria, policy)
    chunks = [target for body in batches for target in body['state']['targets'] if target['call_id'] == 'c0']
    assert len(chunks) > 1
    assert ''.join(t['result'] for t in chunks) == original[2]['output']
    def ask(body):
        important = {t['call_id'] for t in body['state']['targets'] if 'IMPORTANT_MIDDLE' in t['result']}
        return {'model': 'jev-test', 'usage': {'input_tokens': 10},
            'answers': {key: {'noul': .9 if key.removeprefix('keepResult_') in important else .1}
                        for key in body['questions']}}
    with patch.object(scoring, 'request', side_effect=ask):
        scores, _ = scoring.score(original, criteria, policy)
    assert scores['c0']['keepResult'] == .9
    for body in batches:
        assert scoring.estimate_tokens(scoring.encoded(body['state'])) <= 5000
        assert scoring.estimate_tokens(scoring.encoded(body)) <= 10000


def test_credential_absent_after_prelaunch_clone_failure(home):
    directory = root() / 'probe-failure'
    codex = home / 'codex'; codex.mkdir(); (codex / 'auth.json').write_text('fake credential')
    with patch.object(runtime.probe, 'clone_rows', side_effect=OSError):
        with pytest.raises(OSError):
            runtime.probe.measure_one(rows(), history(), directory, codex, 'gpt-6-astra', 'low')
    assert not (directory / 'auth.json').exists()


def test_credential_removed_after_rollout_write_or_spawn_failure(home):
    directory = root() / 'probe-failure'
    codex = home / 'codex'; codex.mkdir(); (codex / 'auth.json').write_text('fake credential')
    with patch.object(runtime.probe.subprocess, 'run', side_effect=OSError):
        with pytest.raises(OSError):
            runtime.probe.measure_one(rows(), history(), directory, codex, 'gpt-6-astra', 'low')
    assert not (directory / 'auth.json').exists()


def test_outer_handler_does_not_adopt_new_pending_session(home, monkeypatch):
    spec = importlib.util.spec_from_file_location('deliver_replaced', ROOT / 'scripts/deliver-renewal.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    path = home / 'renewal.json'
    dump_json(path, {'status': 'pending', 'session_id': 'old', 'jev_request': 'old-request'})
    def reject(_):
        dump_json(path, {'status': 'pending', 'session_id': 'new', 'jev_request': 'new-request'})
        raise ValueError('codex-renewal-source-changed')
    monkeypatch.setattr(sys, 'argv', ['deliver-renewal.py', '--pane-id', 'p'])
    calls = []
    monkeypatch.setattr(module, 'renewal_root', lambda: home)
    monkeypatch.setattr(module, 'record_path', lambda _: path)
    monkeypatch.setattr(module, 'herdr', lambda *args: calls.append(args) or 0)
    with patch.object(runtime, 'deliver', side_effect=reject), \
         patch.object(transport, 'live_agent', return_value={'agent_status': 'idle', 'agent_session': {'value': 'new'}}):
        assert module.main() == 1
    assert not any(call[:2] == ('agent', 'prompt') for call in calls)


def test_empty_successful_pane_run_can_handoff_environment(home):
    import socket
    import threading
    request = {'pane_id': 'p', 'shell_pid': 1, 'terminal_id': 't', 'codex_home': str(home),
               'cwd': str(home), 'executable': '/bin/true', 'options': []}
    received, threads, sockets = [], [], []
    def pane_run(args):
        import shlex
        socket_path = shlex.split(args[-1])[-1]
        sockets.append(socket_path)
        def client():
            with socket.socket(socket.AF_UNIX) as sock:
                sock.connect(socket_path)
                data = bytearray()
                while part := sock.recv(65536):
                    data.extend(part)
                received.append(json.loads(data))
        thread = threading.Thread(target=client); thread.start(); threads.append(thread)
        return ''
    with patch.object(transport, 'shell_ready', return_value=True), \
         patch.object(transport, 'run_herdr_raw', side_effect=pane_run), \
         patch.object(transport, 'wait_for', return_value=True):
        assert transport.launch(request, 'candidate', 'Continue') is True
    for thread in threads:
        thread.join()
    assert received[0]['argv'][1:3] == ['resume', 'candidate']
    assert received[0]['env']['TYPESAFE_API_KEY'] == 'test-key'
    assert all(not Path(path).exists() for path in sockets)
    assert not any('test-key' in p.read_text() for p in root().rglob('*') if p.is_file())


def test_resumed_usage_is_distinct_and_survives_transport_save(transaction, home):
    path, source, original = transaction
    request = json.loads(Path(json.loads(path.read_text())['jev_request']).read_text())
    criteria, policy = configuration()
    record = runtime.benchmark_record('test', criteria, policy, [], source={}, request_metrics=[])
    record.update(decision='apply', tokens_before=200001)
    record['measurement']['live_input_tokens_before'] = 220000
    record['application'] = {'status': 'resuming'}
    candidate_rows = runtime.probe.clone_rows(rows(), history(), 'candidate')
    runtime.save(record, original, candidate_rows)
    continuity = {**json.loads(path.read_text()), 'jev_candidate_session': 'candidate'}
    runtime.observe(continuity, 'candidate', 10000)
    stale = copy.deepcopy(record); stale['application']['status'] = 'resumed'
    runtime.save(stale, original, candidate_rows)
    saved = json.loads((root() / 'benchmark.jsonl').read_text())
    assert saved['application']['status'] == 'verified'
    assert saved['measurement']['actual_session_tokens_after'] == 10000
    assert saved['measurement']['actual_reduction_pct'] > 90
    assert saved['outcome'] == 'applied'


def test_user_turn_during_scoring_cancels_old_pending_checkpoint(transaction):
    path, _, _ = transaction
    with patch.object(transport, 'validate_original', side_effect=[None, ValueError('busy')]):
        with pytest.raises(runtime.RenewalInterrupted):
            runtime.deliver(path)
    assert json.loads(path.read_text())['status'] == 'cancelled'


@pytest.mark.parametrize('cancellation_write_fails', [False, True])
def test_source_advance_and_archive_failure_never_clear(transaction, home, monkeypatch, cancellation_write_fails):
    path, source, original = transaction
    spec = importlib.util.spec_from_file_location('deliver_archive_failure', ROOT / 'scripts/deliver-renewal.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def scoring_timeout(*args):
        source.write_text(original + '\n')
        raise TimeoutError
    calls = []
    monkeypatch.setattr(sys, 'argv', ['deliver-renewal.py', '--pane-id', 'p'])
    monkeypatch.setattr(module, 'renewal_root', lambda: home)
    monkeypatch.setattr(module, 'record_path', lambda _: path)
    monkeypatch.setattr(module, 'herdr', lambda *args: calls.append(args) or 0)
    if cancellation_write_fails:
        monkeypatch.setattr(runtime, 'dump_json', lambda *args: (_ for _ in ()).throw(OSError()))
    with patch.object(scoring, 'score', side_effect=scoring_timeout), \
         patch.object(runtime, 'save', side_effect=OSError), \
         patch.object(transport, 'live_agent', return_value={'agent_status': 'idle', 'agent_session': {'value': 'source'}}):
        assert module.main() == 1
    assert not any(call[:2] == ('agent', 'prompt') for call in calls)
    if not cancellation_write_fails:
        assert json.loads(path.read_text())['status'] == 'cancelled'
