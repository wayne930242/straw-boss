"""Opt-in Codex renewal transaction: score, measure, archive, then resume."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from . import jev_codex_probe as probe, jev_codex_scoring as scoring, jev_codex_transport as transport
from .jev_codex import configuration, history_from_rows, measurement, prune
from .jev_codex_benchmark import benchmark_record
from .jev_private import private_read, private_replace, root
from .jev_storage import benchmark_lock
from .renewal import dump_json, load_record

CONTINUE = 'Continue the unfinished task from the Jev-pruned history loaded in this session. Follow the preserved user decisions and next action.'


class RenewalInterrupted(ValueError):
    """New work or identity superseded this transaction; preserve the pane."""


def cancel_current(path: Path, continuity: dict) -> None:
    current = load_record(path)
    if (current and current.get('status') == 'pending'
            and current.get('jev_request') == continuity.get('jev_request')
            and current.get('session_id') == continuity.get('session_id')):
        dump_json(path, {**current, 'status': 'cancelled'})


def validate_source(path: Path, continuity: dict, request: dict) -> None:
    try:
        transport.validate_original(request)
    except (ValueError, OSError, KeyError):
        try:
            cancel_current(path, continuity)
        except Exception as error:
            print(f'Jev cancellation could not be persisted: {type(error).__name__}.', file=sys.stderr)
        raise RenewalInterrupted('codex-renewal-source-changed') from None


def digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def schedule(record: dict, transcript: str) -> dict:
    request = transport.capture(record['pane_id'], record['session_id'], transcript)
    run = uuid.uuid4().hex
    path = root() / 'requests' / f'{run}.json'
    private_replace(path, json.dumps({**request, 'run_id': run}))
    return {**record, 'jev_request': str(path)}


def save(record: dict, original: str, candidate: list[dict] | None) -> None:
    path = root() / 'runs' / f'{record["run_id"]}.json'
    record['recovery_path'] = str(path)
    # One lock covers the archive and benchmark, including the first resumed
    # Stop racing the deliverer's final transport observation.
    with benchmark_lock():
        benchmark = root() / 'benchmark.jsonl'
        try:
            rows = [json.loads(line) for line in private_read(benchmark).splitlines()]
        except FileNotFoundError:
            rows = []
        prior = next((row for row in rows if row['run_id'] == record['run_id']), None)
        if prior and prior.get('measurement', {}).get('actual_session_tokens_after') is not None:
            if record['measurement'].get('actual_session_tokens_after') is None:
                record['measurement'].update({k: v for k, v in prior['measurement'].items()
                    if k in {'actual_session_tokens_after', 'actual_reduction_pct', 'observation_session'}})
                if record['application']['status'] == 'resumed':
                    record['application']['status'] = prior['application']['status']
                    record['outcome'] = prior['outcome']
        private_replace(path, json.dumps({'record': record, 'original_rollout': original,
            'candidate_rows': candidate}, ensure_ascii=False))
        rows = [row for row in rows if row['run_id'] != record['run_id']]
        rows.append(record)
        private_replace(benchmark, ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))


def observe(continuity: dict, session: str, tokens: int) -> None:
    """Persist the renewed session's actual backend usage separately from probes."""
    request = json.loads(private_read(Path(continuity['jev_request'])))
    path = root() / 'runs' / f'{request["run_id"]}.json'
    data = json.loads(private_read(path))
    record = data['record']
    if record['measurement'].get('observation_session'):
        return
    record['measurement']['observation_session'] = session
    if continuity.get('jev_candidate_session') == session:
        record['measurement']['actual_session_tokens_after'] = tokens
        before = record['measurement'].get('live_input_tokens_before') or record.get('tokens_before')
        ratio = 100 * (before - tokens) / before if before else None
        verified = ratio is not None and ratio >= record['policy']['min_reduction_ratio'] * 100
        record['measurement']['actual_reduction_pct'] = ratio
        record['application']['status'] = 'verified' if verified else 'resumed-without-net-reduction'
        record['outcome'] = 'applied' if verified else None
    else:
        record['measurement']['fallback_usage'] = {'input_tokens': tokens, 'session_id': session}
        record['application']['status'] = 'fallback-observed'
        record['outcome'] = 'fallback'
    save(record, data['original_rollout'], data['candidate_rows'])


def deliver(path: Path) -> bool:
    """Return True after candidate resume; False leaves ordinary clear to caller.

    Identity changes raise instead of clearing a different foreground session.
    A failed candidate startup restores the original session before fallback.
    """
    continuity = load_record(path)
    request = json.loads(private_read(Path(continuity['jev_request'])))
    validate_source(path, continuity, request)
    criteria, policy = configuration()
    source = Path(request['transcript'])
    original = source.read_text()
    rows = [json.loads(line) for line in original.splitlines()]
    record = benchmark_record(request['run_id'], criteria, policy, [],
        source={'rollout_path': str(source), 'rollout_sha256': digest(original)}, request_metrics=[])
    record.update(trigger='context-renewal', session_id=request['session_id'],
                  threshold_tokens=200000)
    record['application'] = {'status': 'preparing', 'live_application_supported': True}
    candidate_rows = None
    session = str(uuid.uuid4())
    try:
        history = history_from_rows(rows)
        scores, metrics = scoring.score(history, criteria, policy)
        candidate, decisions = prune(history, scores, policy)
        candidate_rows = probe.clone_rows(rows, candidate, session)
        record['decisions'] = decisions
        record['jev'] = {'requests': len(metrics), 'request_metrics': metrics,
            'model': sorted({m['model'] for m in metrics}),
            'input_tokens': sum(m['input_tokens'] for m in metrics),
            'latency_ms': sum(m['latency_ms'] for m in metrics)}
        if candidate == history:
            record.update(fallback_reason='unchanged-candidate')
        else:
            before, after, details = probe.measure(rows, candidate, request['run_id'], Path(request['codex_home']))
            record.update(measurement(before, after, policy))
            live_counts = [r["payload"]["info"]["last_token_usage"]["input_tokens"] for r in rows
                if r["type"] == "event_msg" and r["payload"].get("type") == "token_count"
                and r["payload"].get("info")]
            denominator = max(before["input_tokens"], live_counts[-1] if live_counts else 0)
            gate_ratio = (before["input_tokens"] - after["input_tokens"]) / denominator
            record["gate_reduction_pct"] = 100 * gate_ratio
            if gate_ratio < policy["min_reduction_ratio"]:
                record.update(decision="fallback", fallback_reason="under-reduction-gate")
            record["measurement"]["gate_denominator_tokens"] = denominator
            record["measurement"]["live_input_tokens_before"] = live_counts[-1] if live_counts else None
            record['measurement'].update(details, source='codex-exec-resume-token-count',
                cache_hits_before=before['cached_input_tokens'], cache_hits_after=after['cached_input_tokens'],
                baseline_resume_usage=before, candidate_resume_usage=after,
                gate_execution='backend-copied-resumes-before-live-application',
                tokens_after_semantics='isolated-candidate-resume-input')
        record['application'] = {'status': 'prepared' if record['decision'] == 'apply' else 'fallback',
                                 'live_application_supported': True}
        save(record, original, candidate_rows)
    except Exception as error:
        # Third-party/network/provider failures all select ordinary renewal.
        # Persist only the error class: exception strings can contain secrets.
        record.update(decision='fallback', fallback_reason=f'preparation-{type(error).__name__}')
        record['application'] = {'status': 'fallback', 'live_application_supported': True}
        try:
            save(record, original, candidate_rows)
        except (OSError, ValueError):
            print('Jev recovery storage unavailable; using ordinary renewal.', file=sys.stderr)
    validate_source(path, continuity, request)
    current = load_record(path)
    if not current or current.get('jev_request') != continuity['jev_request'] or current.get('status') != 'pending':
        raise RenewalInterrupted('codex-renewal-record-replaced')
    if source.read_text() != original:
        # New work supersedes the continuity payload on both apply and fallback.
        record.update(decision='fallback', fallback_reason='source-advanced-during-preparation')
        record['application']['status'] = 'cancelled-source-advanced'
        try:
            cancel_current(path, continuity)
            save(record, original, candidate_rows)
        except Exception as error:
            print(f'Jev cancellation evidence unavailable: {type(error).__name__}.', file=sys.stderr)
        raise RenewalInterrupted('codex-renewal-source-advanced')
    if record['decision'] != 'apply':
        return False
    try:
        candidate_path = transport.register_rollout(Path(request['codex_home']), candidate_rows, session)
        record['application'].update(status='resuming', candidate_session=session,
            candidate_path=str(candidate_path), candidate_history_sha256=digest(json.dumps(candidate, sort_keys=True)))
        save(record, original, candidate_rows)
        dump_json(path, {**continuity, 'jev_candidate_session': session})
        if not transport.swap(request, session, CONTINUE):
            raise ValueError('codex-candidate-startup-unconfirmed')
        # Herdr's conversation fingerprint proves this pane loaded the new UUID;
        # verify its persisted replacement before marking the swap applied.
        loaded = [json.loads(line) for line in candidate_path.read_text().splitlines()]
        replacements = [row['payload'].get('replacement_history') for row in loaded if row['type'] == 'compacted']
        if not replacements or replacements[-1] != candidate:
            raise ValueError('codex-candidate-history-mismatch')
        record['application'].update(status='resumed', pane_id=request['pane_id'],
                                     terminal_id=request['terminal_id'])
        # Actual net reduction is observed by the resumed session's Stop hook.
        record['outcome'] = None
        try:
            save(record, original, candidate_rows)
        except (OSError, ValueError):
            print('Jev resumed; application observation could not be persisted.', file=sys.stderr)
        return True
    except Exception as error:
        record.update(decision='fallback', fallback_reason=f'resume-{type(error).__name__}')
        record['application']['status'] = 'resume-failed'
        save(record, original, candidate_rows)
        current = load_record(path) or continuity
        current.pop('jev_candidate_session', None)
        dump_json(path, current)
        try:
            transport.validate_original(request)
        except (ValueError, OSError):
            if not transport.wait_for(lambda: transport.shell_ready(request), seconds=10) or not transport.launch(request, request['session_id'], ''):
                raise ValueError('codex-renewal-recovery-required') from None
            transport.run_herdr(['agent', 'wait', request['pane_id'], '--until', 'idle', '--until', 'done', '--timeout', '60000'])
        return False
