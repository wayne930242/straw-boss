# Agent communication contract verification

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| Authenticate live sender and receiver | CLI integration tests reject the wrong sender pane/session and reused receiver sessions before prompting. |
| Enforce role and intent | Peer redirect is rejected; worker/main and peer question/answer routes pass through separate allowlists. |
| Correlate peer replies | Round-trip test records the generated question id; a forged or unknown reply id is rejected. |
| Protect status ownership and content | A worker cannot write another live worker's status, and blank notes are rejected before persistence. |
| Keep user-owned discussion direct | Generated contract, active communication skills, lifecycle skill, and coordination references state direct-user handling with a headless-only relay. |
| Keep Herdr workers independent | Generated contract, canonical roles, `CONTEXT.md`, and the auto-injected orchestrator skill apply **own the loop, not the work** and accept user–worker decisions. |
| Keep work definition worker-owned | Active dispatch skills and the generated contract assign only the user requirement, requested outcome, and necessary integrated context; the worker and user choose specification, design, implementation, and verification method. |
| Bound main-agent intervention | Main-to-worker prompts carry explicit user direction, cross-task facts, or coordinator-owned action results; work-content conflicts return to the user. |
| Notify terminal outcomes | CLI integration tests prove both `done` and `failed` persist before prompting the validated main-agent Herdr endpoint; delivery failure keeps recoverable status and is surfaced. |
| Support one direct coworker | Public-facade tests authenticate the parent, reuse its exact worktree and tab, default to review-only, normalize explicit writable paths, reject a second active coworker and recursive nesting, and confirm launch receipts. |
| Notify parent and root coordinator | Coworker terminal tests prove parent-first and root-second notification; root notification is still attempted if parent delivery fails. |
| Start Codex with a shell-safe contract reference | Launcher tests prove the Herdr argument is one short contract-path pointer with no multiline contract, backtick, or newline; a disposable real-Herdr probe reached interactive readiness and cleaned up its pane. |
| Keep Herdr workers in the coordinator tab | Launcher integration tests prove main-pane lookup, same-tab pane split, shared-tab receipts, no tab command, and fail-closed cleanup if Herdr returns another tab. |
| Keep live messages concise | Messages over two sentences are rejected before delivery; identity, intent, and correlation are rendered once by transport. |
| Move detail out of prose | Repeatable `--ref` values reach the prompt and status state, while the delivery ledger retains only their count and hashes. |
| Keep communication skills concise | `asking-peer-agents` is 47 lines and `notifying-main-agent` is 57 lines; generic lifecycle prose remains in the generated contract. |
| Keep coworker instructions concise | `bringing-coworker` is 49 lines and calls one public facade rather than restating write, launch, confirm, placement, or notification mechanics. |
| Prevent overlapping parallel work | Task-authoring guidance requires non-overlapping requirement scopes or an explicit dependency. |

## Commands

```text
python3 -m unittest discover -s tests
56 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed

python3 scripts/dispatch-coworker.py --help
python3 scripts/dispatch-task.py write --help
python3 scripts/report-task-status.py --help
python3 scripts/run-straw-boss-script.py --help
all passed
```

Verified on 2026-08-26.
