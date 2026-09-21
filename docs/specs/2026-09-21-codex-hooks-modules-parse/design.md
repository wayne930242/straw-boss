# Design

Use .codex-plugin/plugin.json hooks to select hooks/codex-hooks.json. Preserve
hooks/hooks.json byte-for-byte for Claude. The Codex file contains the same
command registrations with no modules field. A parity test detects future drift.
This follows the provider's documented manifest override and existing commands;
there is no runtime translation or installer rewrite.

## Falsifiable hypotheses

1. Unknown modules rejects the whole provider file: hooks/list should show a
   warning and zero Straw Boss entries. Observed before the fix.
2. Codex still retains valid commands after parsing fails: hooks/list should show
   three Straw Boss entries despite the warning. Falsified by baseline.json.
3. An independent registration or trust issue causes the absence: removing only
   the incompatible field through explicit discovery should still yield no
   entries. Test the separate manifest using the real provider, then inspect trust.

The regression first failed on modules (one failure, two passes). Follow it with
real installed hooks/list and SessionStart execution, Claude module load evidence,
then the full Python suite. Preserve raw private runtime evidence outside Git.

## Friction Notes

- Tried: discover code through the graph tool catalog.
  Found: this session exposes no codebase-memory MCP tools; direct reads are available.
  Led by: project graph-first discovery instructions.
- Tried: read the project model preference profile.
  Found: the project path is absent; the user-root active profile selects Sol low for routine review.
  Led by: project model preference routing.
- Tried: install a local test marketplace with a new CODEX_HOME path.
  Found: Codex requires the directory to exist before invoking the CLI.
  Led by: none.
- Tried: send the review coworker a test-result inform delta.
  Found: peer transport accepts question or answer intents; the shared verification artifact already carries the result.
  Led by: none.
- Tried: run the standard remote installer after pushing 0.30.24.
  Found: Claude marketplace refresh failed while reading a temporary pack file in its clone directory, before installation completed.
  Led by: dispatch shipping contract.
