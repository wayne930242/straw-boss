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
| Bound main-agent intervention | Main-to-worker prompts carry explicit user direction, cross-task facts, or coordinator-owned action results; work-content conflicts return to the user. |
| Notify terminal outcomes | CLI integration tests prove both `done` and `failed` persist before prompting the validated main-agent Herdr endpoint; delivery failure keeps recoverable status and is surfaced. |
| Keep Herdr workers in the coordinator tab | Launcher integration tests prove main-pane lookup, same-tab pane split, shared-tab receipts, no tab command, and fail-closed cleanup if Herdr returns another tab. |
| Keep live messages concise | Messages over two sentences are rejected before delivery; identity, intent, and correlation are rendered once by transport. |
| Move detail out of prose | Repeatable `--ref` values reach the prompt and status state, while the delivery ledger retains only their count and hashes. |
| Keep communication skills concise | `asking-peer-agents` is 47 lines and `notifying-main-agent` is 57 lines; generic lifecycle prose remains in the generated contract. |
| Prevent overlapping parallel work | Task-authoring guidance requires distinct deliverables or an explicit dependency. |

## Commands

```text
python3 -m unittest discover -s tests
49 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed

python3 scripts/send-dispatch-message.py --help
python3 scripts/report-task-status.py --help
python3 scripts/reply-to-worker.py --help
all expose the expected repeatable --ref interface
```

Verified on 2026-08-26.
