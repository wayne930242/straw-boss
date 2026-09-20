# Opt-in Jev pruning for Claude Code

Jev pruning is experimental and off by default. Ordinary sessions retain the
existing 200k context renewal behavior, including the acceptance baseline through
2026-09-25. This implementation targets Claude Code 2.1.278.

## Turn it on or off

After installing Straw Boss, start an explicitly enabled session:

```sh
STRAW_BOSS_JEV=1 CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude
```

The TypeSafe key comes from `TYPESAFE_API_KEY`. An unset, empty, or whitespace-only
key silently leaves normal compaction and renewal active and writes no benchmark.

Start a normal session with pruning explicitly off:

```sh
STRAW_BOSS_JEV=0 claude
```

These switches apply at process launch. Restart or resume with the desired switch;
changing the parent shell does not change an already-running Claude process.
Keep `STRAW_BOSS_JEV` out of shell startup files and global settings while evaluating
the experiment. The function-hook feature flag alone does not activate pruning.

## Behavior

An enabled session lets the existing 300k compaction event try Jev before renewal.
There is no extra percentage trigger. A candidate needs at least 10% backend-counted
reduction against the larger of the counted history and the last full session input.
Insufficient reduction, unavailable measurement, Jev failure, or recovery-storage
failure delegates to built-in compaction. At a turn boundary, renewal runs only
when the resulting measured context still exceeds 300k.

The first and latest six messages stay intact. Reads of governing dispatch
contracts/instruction JSON and AGENTS/CLAUDE/GEMINI/SKILL guidance also stay intact,
including combined commands that contain those paths. Other paired calls use
two Jev scores at 0.5: retain both, retain the call and a 300-character result
prefix, or remove both. User and assistant text remains verbatim.

The exact criteria and lock patterns live in
[`config/jev-criteria.json`](../config/jev-criteria.json) and
[`config/jev-policy.json`](../config/jev-policy.json). Both have hashes in each record.
Codex integration must use these shared inputs; this release does not implement
the Codex runtime adapter.

## Read benchmark and recovery records

- `~/.straw-boss/jev/benchmark.jsonl`: one row per attempt, updated in place when
  the next backend usage observation arrives, including across session restart.
- `~/.straw-boss/jev/runs/<run_id>.json`: complete original and candidate message
  views, plus the record. Modified decisions also carry original tool content
  and positions. Files are user-private (0600; new directories 0700).
- `~/.straw-boss/jev/observations/<session_id>.json`: the observed backend usage.

`decision: apply` means the hook selected the candidate. `outcome: applied` means
the subsequent backend request also demonstrated the minimum net reduction.
Until then, `outcome` is null and `application.status` explains what remains
unverified. A larger next prompt can hide a successful pruning reduction, so
`unverified-no-net-reduction` calls for reviewing the recovered candidate and
observation rather than assuming a runtime failure. `outcome: fallback` means
the adapter delegated to built-in compaction; its token result is separate.

`tokens_before` and `tokens_after` are the Anthropic token-count API's counts of
native text and tool blocks, with the latter always describing the candidate.
Hidden reasoning, images, and fixed system/tool schemas are outside that view.
`measurement.live_input_tokens_before` and `actual_session_tokens_after` are
the actual session request usage, including cache read/write input. The gate uses
the full input as a conservative denominator when available. Jev's input-token
cost is recorded separately from Claude's context counts.

Per-pair `bytes_before` and `bytes_after` count UTF-8 canonical JSON containing
the invocation id/tool/input and one result id/text/isError. Duplicated host
metadata is excluded; the complete original host objects remain in recovery.
`score_source: locked-not-judged` and `lock_reason` identify deterministic locks.

Recover a tool output by reading the decision's `original_content` or the run's
`original_messages`. The entire run JSON is sufficient to reconstruct the original
hook message view without rerunning one-shot actions. Keep these records local:
they contain the original task data.

The backend counter uses the current Anthropic API key or Claude OAuth credential
(local credential store, macOS Keychain fallback); credentials stay in the host
process. Custom providers without supported backend counting fall back. The hook
itself uses the inherited TypeSafe key only for the TypeSafe endpoint.

## Evidence and limitations

See [verification](specs/2026-09-20-claude-jev-pruning/verification.md). Real Claude
compaction and restart uncovered an upstream handle-reuse persistence defect:
fresh message identities now keep dropped ancestors from reappearing after resume.
Synthetic archives demonstrate this mechanism, not normal-work savings.

The user requested shipment before additional live branch coverage. Governing
locks, truncation, failure, and missing-key behavior have focused automated and
fixed-history evidence; ongoing session benchmarks provide the next live evidence.

Development checks:

```sh
uv run --with pytest pytest -q tests
cd vendor/fast-jev-compaction
npm ci --ignore-scripts
npm test
npm run build
```
