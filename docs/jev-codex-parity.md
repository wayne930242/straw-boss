# Codex Jev copied-history parity

Codex 0.155.1 supports the shared criteria, policy, gate calculation and
benchmark through a copied-history adapter. Runtime parity with the Claude
function hook is currently unachievable: Codex's public PreCompact output does
not replace in-memory history. The user's parity requirement preceded discovery
of that limitation. Existing Codex compaction and renewal remain unchanged.

## Explicit copy operation

Use a response-item array exported from an isolated rollout and a score file:

```json
{
  "criteria_version": "sha256:0717ecfc2a1cd44198a52958c4538c78a3e0b7d9d4338af4e47e217ac5663ebe",
  "scores": {
    "example-call-id": { "keepCall": 0.5, "keepResult": 0.2 }
  }
}
```

Scores must cover every unlocked complete pair. Rule-locked pairs need no score.
A stale criteria version or invalid pair score records a fallback and keeps the
original candidate unchanged; it does not invoke live built-in compaction.
The command reads the current canonical criteria and policy from `config/`.
With `TYPESAFE_API_KEY` already in the process environment:

```sh
STRAW_BOSS_JEV=1 python3 scripts/jev-codex-copy.py \
  --history /private/replay/history.json \
  --scores /private/replay/scores.json \
  --output-dir /private/replay/new-candidate
```

The output directory must be new. It contains `candidate.json`, lossless
`recovery.json`, and `benchmark.jsonl`, with modes 0700/0600. These artifacts
contain original history, not just metrics. The command consumes existing replay
scores and makes no Jev or Codex backend call. Its benchmark identifies that
source, leaves unmeasured token counts null, and reports candidate-only status.

`STRAW_BOSS_JEV=0`, an unset key, an empty key, or a whitespace-only key returns
silently before argument parsing, without creating files. Activation is local
to that command. It does not install a live compaction hook or change shell
startup files, so no session restart is needed to run this copy command.

## Replay and gate interfaces

`scripts/straw_boss/jev_codex.py` exposes history extraction, pair validation,
rule locks, candidate construction, and fresh compacted replacement records.
`measurement()` accepts backend input usage only when both measurements carry
explicit zero cached input tokens; a reduction of at least 10% selects apply.
`scripts/straw_boss/jev_codex_benchmark.py` preserves the shared schema-v2 fields
and distinguishes that gate decision from a diagnostic copied resume and actual
live application. Actual-session and built-in fallback usage remain null.

`jev_codex_judge.judge_pairs()` reproduces round 2's request envelope with current
criteria. It requires `tiktoken` and `TYPESAFE_API_KEY`; tokenization only bounds
the Jev judging view and never measures savings. This is the controlled regression
interface: it preserves the old 32k request check and can probe rule-locked pairs
for score comparison. It is not the Claude production fitter's 25k state / 30k
request batching implementation. Ordinary candidate construction applies locks
without consulting those probe scores.

The recorded four-point run and scripts are preserved at
`~/.straw-boss/evidence/jev-codex-parity-round3/`. See its `result.md`,
`per-pair.csv`, `resume-transcripts.md`, `benchmark.jsonl`, `verification.json`,
and `persistence/verification.json`. Rerunning the full experiment makes paid
Jev and Codex requests and requires new isolated homes. The evidence scripts
identify the exact source cuts and preserve every cached attempt separately.

## Identification and representation limits

Policy v3 matches the serialized invocation input. It covers an absolute dispatch
path, `cd ~/.straw-boss/dispatch && cat task.json`, a serialized workdir ending in
that dispatch directory, and named AGENTS/CLAUDE/GEMINI/SKILL files. A bare
`cat task.json` with no serialized source identity, aliases, symlinks, variable
expansion and arbitrary shell indirection remain identification limits. The lock
is a deterministic rule over identified inputs, not universal provenance protection.

Codex locks the first text message and latest six text messages together with
intervening tool exchanges, retaining round 2's conservative recency boundary.
Claude pins its own native SessionMessage units; the providers do not have
identical message granularity. All Codex user/assistant and reasoning items remain
verbatim. Retained image blocks remain in order; normalized byte accounting counts
visible text once and excludes image payloads, matching the shared text projection.
Raw host originals remain available in recovery.

Live compaction-event replacement, automatic built-in fallback after a gate miss,
and subsequent compaction-window renewal ordering remain provider gaps. An offline
gate decision or a copied `codex resume` is not evidence that those live paths ran.
