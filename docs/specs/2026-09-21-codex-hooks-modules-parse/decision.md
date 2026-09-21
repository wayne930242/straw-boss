# Decision

Restore installed Codex hooks while preserving Claude Jev module loading.
The dispatch owns authorization for implementation, fresh-context review, version
bump, push, and installation. Baseline: a41bf1d, version 0.30.23.

| Question | Answer | Basis | Status |
|---|---|---|---|
| Which provider changes? | Codex gets a provider-specific hook manifest; Claude retains its existing discovery file. | Dispatch requires both providers to work. | grounded |
| Does parsing disable hooks? | Codex 0.155.1 hooks/list reports the modules error and zero Straw Boss hooks. | Private evidence: ~/.straw-boss/evidence/codex-hooks-modules-parse/baseline.json | grounded |
| How is discovery overridden? | Set hooks in .codex-plugin/plugin.json to a separate file. | [Official hooks documentation](https://developers.openai.com/codex/hooks#plugin-bundled-hooks) | grounded |
| Can command definitions drift? | A regression compares complete command registrations across providers. | Existing commands work with Codex's CLAUDE_PLUGIN_ROOT compatibility variable. | grounded |
| Is the launch timeout in scope? | Report a causal link only if observed. | Dispatch explicitly separates the timeout from parsing. | grounded |

Core rules: English artifacts, Traditional Chinese communication, solo main,
review before shipping, preserve both providers. No open user-owned decisions.
