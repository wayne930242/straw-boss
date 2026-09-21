Status: approved
Approved at: 2026-09-21
Approved from: Canonical dispatched task authorizes repair, independent review, bump, push and installation; subsequent user update selects f253dc7 / 0.30.24 as the base.

# Contract

- Codex coworkers inherit the immediate parent's effective execution tier from Codex and Claude parents.
- Review-only contracts retain their repository write scope while execution permissions allow coordination commands at the inherited tier.
- Narrower parent launch overrides remain narrower in the child. Unknown parent permissions resolve conservatively.
- Coworker raw arguments cannot override the inherited permission ceiling.
- Parent/root notification routing and authenticated session checks retain their existing behavior.

Reality anchor: failing facade integration test, permission regressions, full pytest suite; a live coworker report where available. Checkpoint: fresh-context review before shipping.

Non-goals: model preference redesign, sandbox escape mechanisms, changing top-level dispatch override behavior.
