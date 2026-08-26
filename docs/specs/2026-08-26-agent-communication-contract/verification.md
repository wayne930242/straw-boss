# Agent communication contract verification

## Acceptance evidence

| Requirement | Evidence |
|---|---|
| Authenticate live sender and receiver | CLI integration tests reject the wrong sender pane/session and reused receiver sessions before prompting. |
| Enforce role and intent | Peer redirect is rejected; worker/main and peer question/answer routes pass through separate allowlists. |
| Correlate peer replies | Round-trip test records the generated question id; a forged or unknown reply id is rejected. |
| Protect status ownership and content | A worker cannot write another live worker's status, and blank notes are rejected before persistence. |
| Keep user-owned discussion direct | Generated contract, active communication skills, lifecycle skill, and coordination references state direct-user handling with a headless-only relay. |
| Keep dispatch prompts concise | `asking-peer-agents` is 47 lines and `notifying-main-agent` is 56 lines; generic lifecycle prose remains in the generated contract. |
| Prevent overlapping parallel work | Task-authoring guidance requires distinct deliverables or an explicit dependency. |

## Commands

```text
python3 -m unittest discover -s tests -v
43 tests passed

python3 -m compileall -q scripts tests
passed

git diff --check
passed
```

Verified on 2026-08-26.
