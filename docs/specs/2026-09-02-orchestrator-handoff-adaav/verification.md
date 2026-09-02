# Verification

## Requirement evidence

| Requirement | Evidence | Result |
|---|---|---|
| A new orchestrator window requires explicit user approval | `handoff-orchestrator.py` rejects a launch without `--user-approved`; integration test proves no Herdr call occurs | Pass |
| The source and receiver are the real Herdr panes | Both sides match `HERDR_PANE_ID` and the caller process ancestry against live Herdr foreground processes; spoof and real-pane tests cover the boundary | Pass |
| The receiver routes through `boss-say` before acceptance | The prompt exposes only the handoff file; the receiver-bound acceptance requires and persists the owner, graph, and anchor established by the `boss-say` handoff branch, and the source validates all three | Pass |
| Continuity is bounded and contains only executable state | Exact-key tests verify required fields, omitted empties, retained work mapped to exclusions, no transcript, and rejection above 1,600 characters | Pass |
| Acceptance transfers ownership and source scope ends | Accepted integration tests verify receiver identity, retained-scope behavior, and source-pane close only after acceptance | Pass |
| No retained work closes the source pane automatically | Integration test verifies the accepted result is emitted before `pane close` and source close is retried | Pass |
| Failed acceptance retries once and cleans the new tab | Tests verify two prompts, tab cleanup, source retention, and explicit persisted `cleanup-failed` recovery when Herdr cleanup cannot finish | Pass |
| Naming failure does not block handoff | Tab rename is attempted twice; the handoff still reaches accepted state with one warning | Pass |
| ADAAV stays lightweight | Authority and injected-stance tests verify one silent ordering, no response-template requirement, and the 1,800-character priming budget | Pass |

## Checks

- Focused handoff and provider lifecycle tests: pass.
- Full `python3 -m unittest discover -s tests`: pass.
- Real Herdr caller-process validation on the current pane: pass.
- `git diff --check`, Python compilation, and plugin validation: pass.
- Fresh-context adversarial review: final disposition recorded after the last implementation pass.
