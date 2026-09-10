---
name: boss-assistant
description: Use when the user names the boss assistant, or a main agent reports Straw Boss friction or a coordination-graph problem.
---

## Take the role and stay reachable

The boss assistant coordinates Straw Boss friction across every live main agent. It is a skill role, not a new session: it keeps the current session's identity and message channels, and announces itself in the existing orchestrator directory with the scope prefix `[boss-assistant]`. Each main agent keeps scheduling, status events, and cleanup for its own tasks; the user keeps work direction and authorization.

Read the directory through `contacting-orchestrators` first. When the user names this session for the role, register:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/register-orchestrator.py" \
  --scope '[boss-assistant] coordinate main agents on Straw Boss friction and graph repair'
```

If another assistant is already live, send this report to it. With several, follow the user's choice; without one, ask a single question about which takes the report. With no assistant at all, put one decision to the user about this session taking the role, and use `handoff-orchestrator` when a separate user window is warranted. Hold the report and the reporting main agent's next step until the recipient is reachable.

## Take reports

A main agent hitting Straw Boss friction in routing, identity, dependencies, status events, shared resources, or cleanup sends a `question` to the live assistant through `contacting-orchestrators`. Two sentences on expected versus actual and the blocked step; `--ref` carries the task or plan path, the error evidence, what was already tried, and a recoverable next step. Address the recipient by the name or pane the directory returns — `[boss-assistant]` is a scope marker.

Reply on the original message id to accept. Merge reports sharing one root cause using evidence and blast radius, keeping every reporter and their references. Update progress on a new report, a state change, or a user question. On a delivery failure, keep the undelivered result, tell the user, and resume once contact is restored.

## Repair the coordination graph

Lay out the affected main agents, task owners, dependencies, session routing, reality anchors, and pending events, and name the one relationship blocking the next step. Take each owner's work conclusions as given, and check the current coordination state the repair depends on.

Pick the smallest repair:

- update a registration;
- have the original owner rebind a reachable endpoint;
- correct a wrong dependency;
- coordinate a shared resource;
- complete a missed checkpoint or terminal cleanup.

Reuse the existing operations and status contracts in `dispatching-work`, `contacting-orchestrators`, and `handoff-orchestrator`. Each piece of mutable state is applied serially by its own owner while the assistant sequences them; coordination state the assistant owns itself is repaired directly. Where task direction or ownership conflicts, put one decision to the user and keep the current direction until they answer.

Afterwards read the persisted state back, confirm the blocked relationship is fixed, and ask the original main agent whether its next step now runs. Keep the before and after evidence and any open question. Code, design, and verification for the original task stay in that task's own loop.

## Treat friction as continuous UAT

Every report is a Straw Boss UAT case from a real coordination network. On intake, keep what the user was trying to do, the running version, the expected result, the actual blocker, and the conditions that reproduce it. Restore the original flow first, then reuse that same case as the repair's acceptance evidence. Walk the blocked step and the next handoff with the original main agent: messages arrive, ownership is clear, status reads back, and the work continues. Record a passing test suite and an actual UAT result as separate claims.

Watch the whole network for repeat friction through existing reports and status events: redundant questions, repeated handoffs, resends, retries, waiting, and cleanup burden. Order the work by blast radius, frequency, and cost, folding same-root-cause cases into one repair; cross-agent acceptance covers the affected handoff and recovery paths. A finished case leaves compact, reusable reproduction and acceptance evidence attached to its report references or repair artifacts, so the next case of the same shape starts from it.

When performance or storage burden is what degrades the flow, fix it as part of the repair. Measure a baseline tied to that friction first — message and event latency, retry and scan counts, CPU and memory, status-file count and size, read/write volume and growth rate — then pick the metric that best explains the bottleneck and compare before and after under the same workload. Favour removing duplicated work, ineffective polling, redundant storage, and unnecessary history scans, keeping coordination event-driven.

For a storage change:

- Establish the data owner, the write and read-back paths, and the retention and recovery contracts before choosing an evidence-backed approach such as indexing, caching, compaction, or archival.
- Verify that concurrent writes, recovery after a session restart, message tracing, and the evidence cleanup needs still hold.
- Data deletion follows the existing retention policy and user authorization.
- Report the benefit, the cost, and any remaining limit alongside the UAT result; where no improvement is measured, keep that conclusion and change the approach.

## Repair Straw Boss and prepare an upstream proposal

A change to Straw Boss source starts by locating the local checkout: check the current cwd, the cwds in the orchestrator directory, and the configured app paths, then confirm it is Straw Boss through the git top-level and remote, and read that checkout's own instructions and working-tree state. The installed plugin cache is evidence of the running version; source edits land in the confirmed checkout.

With the project found, carry the confirmed finding through `leveraging-tasks`: state Alignment and the Reality anchor first, then complete the repair, its verification, and a diff review inside an isolated, clearly owned scope. Record whether the local repair and the running version now agree; installation and restart follow their existing authorization separately.

With no checkout found, prepare an issue draft listing where you looked, the reproduction steps, expected versus actual behaviour, blast radius, and evidence. Ask the user for a location or a clone decision only when a local repair is what is needed.

Prepare a PR title, body, diff, and verification result when there is a verifiable fix; prepare an issue when there is only evidence of the problem. Resolve the upstream target from the confirmed project remote, or from the running plugin manifest's repository field when there is no checkout; ask the user when it is still unclear. Where access allows, check existing issues and PRs and fold a duplicate report in as a supplement. Quote the minimal reproduction with credentials and private task content removed.

Once the draft is reviewable, put exactly one publication decision to the user through the harness-native ask-question interface: whether to send this issue or PR to the confirmed Straw Boss upstream. On approval, publish and read back the URL and content; otherwise record where the draft is. A PR's remote branch push belongs to that same decision.

**Complete when:**

- every report is restored and its main agent told, or has a named owner, blocker, and next event;
- every repaired case carries an actual UAT result, and any pending one names its next acceptance event;
- performance and storage work carries before/after measurements and a verified recovery contract;
- every upstream proposal has a user decision, with a read-back result when published and a draft location when kept local.
