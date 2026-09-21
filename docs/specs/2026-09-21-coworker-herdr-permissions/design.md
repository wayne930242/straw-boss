# Design

The facade stops imposing a read-only sandbox. The existing provider launch seam records the effective permission tier inferred from its resolved arguments. Coworker context uses that immediate-parent field; legacy launches inspect the authenticated parent's Herdr foreground process. Unknown or ambiguous arguments resolve to read-only. The root coordinator tier is not evidence of the parent's effective tier.

The coworker provider boundary owns its permission flags and accepts only bounded model/effort overrides from raw arguments. This prevents aliases, config overrides, and profiles from replacing the inherited ceiling. Top-level dispatch behavior remains compatible.

Red evidence: the existing facade integration test fails because child main_agent_permission_tier is null despite an unrestricted parent. Further tests inspect the actual Herdr start arguments.

Hypotheses: (1) missing child tier predicts null instruction, reproduced; (2) facade read-only default predicts a sandbox override even after inheritance, visible in source and tested through start arguments; (3) missing model/effort causes access failure, rejected because permission flags alone determine the relevant launch behavior.

## Friction Notes

- Tried: query graph discovery tools and project-local model profile.
  Found: this harness exposes no graph tools and the local profile is absent; direct source reads and the user-root profile are available.
  Led by: project code discovery and model routing instructions.
- Tried: guessed coworker module path and shell globs.
  Found: coworker context lives in dispatch-task.py; unmatched zsh globs abort that command.
  Led by: none.

- Tried: adversarial permission inference with compact short options.
  Found: bypass plus -sread-only was inferred as unrestricted, so compact options need normalization before tier inference.
  Led by: verification of the immediate-parent ceiling.

- Tried: infer Claude's default tier from explicit permission flags alone.
  Found: the established Claude default is guarded-write; a real parent-launch-chain regression exposed the missing inference.
  Led by: independent review of the requested inheritance behavior.

Review corrections: normalize compact Codex options, stop at the option terminator, retain Claude's established guarded-write default, and accept only exact effort config values at the coworker boundary. All other provider configuration remains owned by the inherited launch policy.
