"""Live Codex scoring with the shared production state/request budgets."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .jev_codex import CALLS, collect_pairs, locked_indices, lock_reason, normalized_pair

STATE_CONTEXT = (
    'A coding assistant history is being compacted. `history` runs oldest first, '
    'with tool results omitted and long text abridged. Each target supplies its exact invocation and a contiguous result chunk. Score the named call and '
    'whether this result chunk contains material needed for the unfinished task; a high score on any chunk retains the complete result. Keep governing instructions and '
    'required evidence; archived originals are recoverable, but some tool actions '
    'cannot be reproduced.'
)


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def estimate_tokens(text: str) -> int:
    """Same production fitter estimate as vendor state.ts; never a savings gate."""
    total = 0.0
    for piece in re.findall(r'[A-Za-z]+|\d+|[^\sA-Za-z\d]', text):
        if piece[0].isascii() and piece[0].isdigit():
            total += len(piece) / 2
        elif piece[0].isascii() and piece[0].isalpha():
            total += 1 + (len(piece) - 1) // 6
        else:
            total += len(piece) * 0.9
    return math.ceil(total)


def short(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1] + '…'


def fit_state(history: list[dict], policy: dict) -> dict:
    entries = []
    users = []
    for index, item in enumerate(history):
        if item['type'] == 'message':
            text = '\n'.join(p.get('text', '') for p in item.get('content', []))
            if item.get('role') == 'user':
                users.append(text)
            entries.append({'i': index, 'role': item['role'], 'text': text})
        elif item['type'] in CALLS:
            entries.append({'i': index, 'role': 'assistant', 'text': '',
                            'tool_calls': [{'id': item['call_id'], 'tool': item['name'],
                                'input': item.get('arguments', item.get('input', ''))}]})
    state = {'context': STATE_CONTEXT, 'goal': '\n'.join(short(x, 500) for x in users[-3:]),
             'history': entries}
    fits = lambda: estimate_tokens(encoded(state)) <= policy['max_state_tokens']
    if fits():
        return state
    for cap in (1000, 200, 60):
        for entry in entries:
            for call in entry.get('tool_calls', []):
                call['input'] = short(str(call['input']), cap)
        if fits():
            return state
    pinned = locked_indices(history, policy['preserve_recent_messages'])
    order = sorted(entries, key=lambda e: e['i'] in pinned)
    for entry in order:
        text = entry['text']
        if len(text) > 590:
            entry['text'] = text[:400] + f'\n[… {len(text) - 550} chars omitted …]\n' + text[-150:]
            if fits():
                return state
    for entry in order:
        if entry['i'] in pinned:
            continue
        entry['text'] = ''
        if fits():
            return state
    # Keep all call identities and recent task text. If they cannot fit, use
    # ordinary renewal instead of judging with an unbounded request.
    state['history'] = [e for e in entries if e['text'] or e.get('tool_calls')]
    if not fits():
        raise ValueError('jev-state-budget-exceeded')
    return state


def questions(call: dict, result: dict, criteria: dict, names: list[str] | None = None) -> dict:
    _, output = normalized_pair(call, result)
    included = criteria if names is None else {name: criteria[name] for name in names}
    return {f'{name}_{call["call_id"]}': {
        'type': 'noul',
        'instructions': f'Target: tool call {call["call_id"]} ({call["name"]}, {len(output["text"])} result chars). {wording}',
        'criteria': {'true': wording, 'false': 'The proposition is false; this material can be pruned according to the stated retention contract.'},
    } for name, wording in included.items()}


def request(body: dict) -> dict:
    req = urllib.request.Request('https://api.typesafe.ai/v1/systemone',
        data=encoded(body).encode(), headers={'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + os.environ['TYPESAFE_API_KEY'].strip()})
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(f'jev-http-{error.code}') from None


def scoring_batches(history: list[dict], criteria: dict, policy: dict) -> list[dict]:
    locked = locked_indices(history, policy['preserve_recent_messages'])
    pairs = [(history[a], history[b]) for a, b in collect_pairs(history)
             if lock_reason(history[a], a, b, locked, policy) is None]
    if not pairs:
        return []
    # Reserve half the state budget for exact target content. Full tool results
    # are covered by successive chunks, never judged from their length alone.
    state = fit_state(history, {**policy, 'max_state_tokens': policy['max_state_tokens'] // 2})
    batches = []
    def body(targets, qs):
        return {'model': 'jev-latest', 'state': {**state, 'targets': targets}, 'questions': qs}
    def fits(value):
        return (estimate_tokens(encoded(value['state'])) <= policy['max_state_tokens']
                and estimate_tokens(encoded(value)) <= policy['max_request_tokens'])
    current_targets, current_questions = [], {}
    for call, result in pairs:
        invocation, output = normalized_pair(call, result)
        text = output['text']
        offset = 0
        first_chunk = True
        while offset < len(text) or (offset == 0 and not text):
            target = {'call_id': call['call_id'], 'call': invocation,
                      'result_offset': offset, 'result_total_chars': len(text),
                      'result_is_error': output['isError'], 'result': ''}
            # The invocation is identical across a pair's chunks, so keepCall
            # is only asked once; keepResult must still see every chunk.
            names = list(criteria) if first_chunk else [name for name in criteria if name != 'keepCall']
            qs = questions(call, result, criteria, names)
            if not fits(body([target], qs)):
                raise ValueError('jev-target-invocation-budget-exceeded')
            low, high = 0, len(text) - offset
            while low < high:
                middle = (low + high + 1) // 2
                target['result'] = text[offset:offset + middle]
                if fits(body([target], qs)):
                    low = middle
                else:
                    high = middle - 1
            if text and low == 0:
                raise ValueError('jev-target-result-budget-exceeded')
            target['result'] = text[offset:offset + low]
            combined = body([*current_targets, target], {**current_questions, **qs})
            # Keep each call's chunks in separate requests so every response
            # directly scores the exact chunk that was transmitted.
            duplicate = any(t['call_id'] == call['call_id'] for t in current_targets)
            if current_targets and (duplicate or not fits(combined)):
                batches.append(body(current_targets, current_questions))
                current_targets, current_questions = [], {}
            current_targets.append(target)
            current_questions.update(qs)
            offset += low
            first_chunk = False
            if not text:
                break
    if current_targets:
        batches.append(body(current_targets, current_questions))
    return batches


def round_batches(batches: list[dict], criteria: dict) -> list[list[tuple[str, dict, list[tuple[dict, dict]]]]]:
    """Regroup planned batches by each call's chunk occurrence (0, 1, ...).

    A single planned batch can combine chunks from different calls at
    different occurrences (e.g. one pair's last chunk packed with another
    pair's first). Splitting by occurrence lets `score` stop requesting a
    call's later occurrences once an earlier one already crosses the keep
    threshold, without touching still-needed chunks packed alongside it.
    """
    seen: dict[str, int] = {}
    rounds: list[list[tuple[str, dict, list[tuple[dict, dict]]]]] = []
    for batch in batches:
        buckets: dict[int, list[tuple[dict, dict]]] = {}
        for target in batch['state']['targets']:
            call_id = target['call_id']
            occurrence = seen.get(call_id, 0)
            seen[call_id] = occurrence + 1
            qs = {f'{name}_{call_id}': batch['questions'][f'{name}_{call_id}']
                  for name in criteria if f'{name}_{call_id}' in batch['questions']}
            buckets.setdefault(occurrence, []).append((target, qs))
        for occurrence, items in buckets.items():
            while len(rounds) <= occurrence:
                rounds.append([])
            rounds[occurrence].append((batch['model'], batch['state'], items))
    return rounds


def score(history: list[dict], criteria: dict, policy: dict) -> tuple[dict, list[dict]]:
    rounds = round_batches(scoring_batches(history, criteria, policy), criteria)
    def judge(body):
        start = time.monotonic()
        response = request(body)
        if not isinstance(response, dict) or not response.get('model'):
            raise ValueError('jev-invalid-model')
        usage = response.get('usage', {}).get('input_tokens')
        if type(usage) is not int or usage <= 0:
            raise ValueError('jev-invalid-usage')
        answers = {}
        for key in body['questions']:
            value = response.get('answers', {}).get(key, {}).get('noul')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError('jev-invalid-score')
            answers[key] = value
        metric = {'model': response['model'], 'input_tokens': usage,
            'latency_ms': round(1000 * (time.monotonic() - start)),
            'state_tokens_estimate': estimate_tokens(encoded(body['state'])),
            'request_tokens_estimate': estimate_tokens(encoded(body)),
            'request_sha256': hashlib.sha256(encoded(body).encode()).hexdigest(),
            'targets': [{'call_id': t['call_id'], 'offset': t['result_offset'],
                         'chars': len(t['result'])} for t in body['state']['targets']],
            'scores': answers}
        return answers, metric
    scores, metrics, resolved = {}, [], set()
    for round_group in rounds:
        bodies = []
        for model, state, items in round_group:
            items = [(target, qs) for target, qs in items if target['call_id'] not in resolved]
            if not items:
                continue
            merged_questions = {}
            for _, qs in items:
                merged_questions.update(qs)
            bodies.append({'model': model, 'state': {**state, 'targets': [target for target, _ in items]},
                           'questions': merged_questions})
        if not bodies:
            continue
        # A call's next occurrence depends on this round's answers, so rounds
        # run in sequence; different calls within a round still run concurrently.
        with ThreadPoolExecutor(max_workers=4) as pool:
            for answers, metric in pool.map(judge, bodies):
                metrics.append(metric)
                for target in metric['targets']:
                    call_id = target['call_id']
                    aggregate = scores.setdefault(call_id, {name: 0 for name in criteria})
                    for name in criteria:
                        key = f'{name}_{call_id}'
                        if key in answers:
                            aggregate[name] = max(aggregate[name], answers[key])
                    if aggregate['keepResult'] >= policy['keep_threshold']:
                        resolved.add(call_id)
    return scores, metrics
