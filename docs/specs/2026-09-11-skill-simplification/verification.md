# Verification

Review base: `5d7c1ac9064e21c67b4ecff0b70d84f48f731f98` (`HEAD` and `origin/main` at review time). The change is the working-tree diff plus this specification folder.

| Requirement | Evidence | Result |
|---|---|---|
| One responsibility per skill | `work-on` returns targets; `boss-say` owns decomposition/scheduling; `dispatching-work` owns briefs and wrap-up; `choosing-graph` owns graph/anchor/review policy. Owner-link tests resolve each path. | pass |
| Proportional initialization | `init` reuses known configuration, loads app instructions for bounded discovery, and links to readiness before optional dispatch. Root bootstrap precedes summary sync. | pass |
| Unresolved decisions and event-driven scheduling | The scheduler reuses tasks/dependencies and established lifecycle modes, counts `--in-flight`, gates candidates with `--ready`, retains checkpoint slots, and peeks only for questions or discrepancies. | pass |
| Concise, actionable prose and valid references | All 15 entrypoints and all 6 references reviewed; local Markdown file/section links pass. Skill main-text word count falls from 15,552 to 5,353; total skill/reference words from 25,150 to 9,089. | pass |
| Lifecycle invariants remain reachable | Scenario review below; generated-contract tests and lifecycle tests exercise identity, status, notification, recovery, and archive behavior. | pass |
| Compatible names and CLI interfaces | All 15 names remain; executable scripts are unchanged. Obsolete prose assertions now inspect rule owners and named references. | pass |

## Scenario review

| Scenario | Instruction path and observed contract |
|---|---|
| Single bounded task | `boss-say` → target instructions; source changes reach `shipping-task`; `choosing-graph` keeps single-loop free of a dispatch plan. |
| Independent/dependent tasks | One `boss-say` scheduler applies the cap and ready set; only a `done` prerequisite unblocks a dependent task. |
| Existing init configuration; Herdr unavailable | Confirmed choices are reused, local configuration/sync can complete, and optional dispatch waits for readiness. |
| User or authorization checkpoint | `dispatching-work` retains the worker and slot and points to the worker pane. |
| Coordinator checkpoint | The owner replies through `reply-to-worker.py`; user work decisions return to the user. |
| Terminal programming task | Wrap-up checks the completion reference/review, closes its worker, releases remaining locks, and archives; the git lifecycle owner removes the worktree and updates the ticket. |
| Same-task continuation | The existing instruction and pane remain available before wrap-up; the next phase reports through the same instruction. |
| Closed worker without terminal status | Explicit recovery validates main-agent identity and unreachability; evidence determines the outcome. |
| Coworker completion | The parent integrates and uses the same wrap-up owner, retaining the shared tab and its own instruction. |
| Orchestrator handoff | The receiver establishes owner/graph/anchor before accepting and reuses the transferred approval. |

## Checks

- Skill instruction tests: 37 passed.
- Dispatch lifecycle contract tests: 26 passed.
- Full regression suite: `python3 -m unittest discover -s tests` — 324 passed in 149.268 seconds.
- `git diff --check`: passed.

Standards review: pass; no remaining findings. Source-changing ownership, approved scope, concise positive instructions, and named references are satisfied.

Spec review: pass; no remaining findings. The review corrected repeat wrap-up handling by explicitly reusing a completed result.

This is document/contract verification and local regression evidence. Live Herdr UAT, installation, commits, pushes, and publication were not performed.
