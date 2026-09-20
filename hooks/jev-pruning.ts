import type { CoreEngineInterface, Register } from 'claude-code';
import { compact } from '../vendor/fast-jev-compaction/src/compact.js';
import { buildJevRequest, parseJevResponse } from '../vendor/fast-jev-compaction/src/request.js';
import { toSessionMessages } from './jev/messages.js';

type Engine = CoreEngineInterface;

export async function active($: Engine): Promise<boolean> {
  return (await $.env.get('STRAW_BOSS_JEV')) === '1' &&
    !!(await $.env.get('TYPESAFE_API_KEY'))?.trim();
}

export async function host($: Engine, command: string, data: unknown): Promise<any> {
  const result = await $.process.run(['python3', `${$.plugin.root}/scripts/jev-runtime.py`, command], {
    stdin: JSON.stringify(data), timeoutMs: 90_000,
  });
  if (result.exitCode !== 0) {
    let reason = 'host-operation-failed';
    try { reason = JSON.parse(result.stdout).error ?? reason; } catch { /* Use operation code. */ }
    throw new Error(`${command}:${reason}`);
  }
  if (!result.stdout.trim()) throw new Error(`${command}:inactive`);
  return JSON.parse(result.stdout);
}

export const register: Register = (on) => {
  let pendingRun: string | undefined;

  on('session.start', async ($, event, next) => {
    // Clear inherited readiness so an unloaded or child session cannot opt out
    // of the normal renewal behavior through its parent's readiness marker.
    await $.env.set('STRAW_BOSS_JEV_READY_SESSION', undefined);
    await $.env.set('STRAW_BOSS_JEV_WAITING_USAGE', undefined);
    if (await active($)) {
      try {
        const config = await host($, 'config', { session_id: await $.session.id() });
        pendingRun = config.pending?.run_id;
        await $.env.set('STRAW_BOSS_JEV_READY_SESSION', await $.session.id());
      } catch { $.ui.log('Jev unavailable; existing renewal remains active.'); }
    }
    return next(event);
  });

  on('session.compact', async ($, event, next) => {
    if (!(await active($))) return next(event);
    // Precompute installs no history. Its returned candidate may be used much
    // later, so delegate until the engine invokes an actual compaction.
    if (event.trigger === 'precompute' || event.agentId) return next(event);
    const started = Date.now();
    const session = await $.session.id();
    const runId = `${session}-${started}-${Math.random().toString(36).slice(2, 8)}`;
    const metrics: any[] = [];
    const record: any = {
      schema_version: 2, run_id: runId, session_id: session, trigger: event.trigger,
      started_at: new Date(started).toISOString(), tokens_before: null, tokens_after: null,
      context_window: null, criteria_version: null, decisions: [], reduction_pct: null,
      jev: { model: null, requests: 0, input_tokens: 0, latency_ms: 0, request_metrics: metrics },
      outcome: 'fallback', fallback_reason: null,
    };
    let candidate: any;
    let apply = false;
    try {
      const config = await host($, 'config', {});
      record.criteria_version = config.criteria_version;
      record.policy = config.policy;
      record.policy_version = config.policy_version;
      const usage = await $.session.usage();
      record.context_window = usage.context.window;
      const policy = config.policy;
      const key = (await $.env.get('TYPESAFE_API_KEY'))!;
      const result = await compact(event.messages, {
        async ask(state, questions) {
          const start = Date.now();
          record.jev.requests++;
          const metric: any = { request: record.jev.requests, input_tokens: null, latency_ms: null };
          metrics.push(metric);
          try {
            const request = buildJevRequest({ apiKey: key }, state, questions);
            const response = await $.http.fetch(request.url, {
              method: request.method, headers: request.headers, body: request.body,
            });
            // Keep server error bodies out of logs and benchmark records.
            if (!response.ok) throw new Error(`jev-http-${response.status}`);
            const parsed = parseJevResponse(response.status, response.ok, response.text);
            if (!parsed.model || !Number.isFinite(parsed.usage?.input_tokens)) {
              throw new Error('jev-missing-model-or-usage');
            }
            metric.model = parsed.model;
            metric.input_tokens = parsed.usage!.input_tokens!;
            record.jev.model = parsed.model;
            record.jev.input_tokens += metric.input_tokens;
            return parsed;
          } finally {
            metric.latency_ms = Date.now() - start;
            record.jev.latency_ms += metric.latency_ms;
          }
        },
      }, {
        criteria: config.criteria, protectedInputPatterns: policy.protected_input_patterns, keepThreshold: policy.keep_threshold,
        preserveRecentMessages: policy.preserve_recent_messages,
        maxStateTokens: policy.max_state_tokens, maxRequestTokens: policy.max_request_tokens,
        truncateHeadChars: policy.truncate_head_chars,
      });
      candidate = toSessionMessages(event.messages, result.messages);
      record.decisions = result.decisions;
      record.state = { estimated_tokens: result.stats.stateTokens, stage: result.stats.stateStage };
      if (result.decisions.every((d) => d.action === 'keep')) {
        record.fallback_reason = 'no-removable-records';
      } else {
        Object.assign(record, await host($, 'measure', {
          model: await $.session.model(), before: event.messages, after: candidate,
          live_input_tokens: usage.context.tokens,
        }));
        apply = record.gate_reduction_pct >= policy.min_reduction_ratio * 100;
        record.fallback_reason = apply ? null : 'under-reduction-gate';
      }
    } catch (error) {
      record.fallback_reason = error instanceof Error ? error.message : 'jev-failure';
    }
    record.decision = apply ? 'apply' : 'fallback';
    record.outcome = apply ? null : 'fallback';
    record.application = { status: 'awaiting-backend-usage' };
    record.elapsed_ms = Date.now() - started;
    try {
      await host($, 'persist', { record, original_messages: event.messages, candidate_messages: candidate });
    } catch {
      $.ui.log('Jev recovery record unavailable; using built-in compaction.');
      return next(event);
    }
    pendingRun = runId;
    // A manual compaction can end before another backend request. Its old
    // transcript usage cannot trigger renewal while the new window is unmeasured.
    await $.env.set('STRAW_BOSS_JEV_WAITING_USAGE', session);
    if (apply) {
      $.ui.log(`Jev candidate selected: ${record.gate_reduction_pct.toFixed(1)}% backend-count reduction; recovery ${runId}.`);
      return { messages: candidate };
    }
    $.ui.log(`Jev fallback: ${record.fallback_reason}.`);
    return next(event);
  });

  on('turn.complete', async ($, event, next) => {
    if (await active($)) {
      const usage = await $.session.usage();
      if (usage.context.tokens !== undefined) {
        await $.env.set('STRAW_BOSS_JEV_WAITING_USAGE', undefined);
        if (pendingRun) {
          await host($, 'observe', { session_id: await $.session.id(), run_id: pendingRun,
            actual_session_tokens_after: usage.context.tokens, context_window: usage.context.window,
            source: 'first-observed-post-compaction-backend-input', observed_at: new Date().toISOString() });
          pendingRun = undefined;
        }
      }
    }
    return next(event);
  });
};
