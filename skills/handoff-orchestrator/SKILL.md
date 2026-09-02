---
name: handoff-orchestrator
description: Move one approved work scope to a new orchestrator in an independent Herdr tab, then end the source orchestrator's ownership of that scope.
---

# Hand off one orchestrator scope

## 1. Get approval

Present one ask-question decision naming the scope that moves and any work this
orchestrator retains. A new tab is created only after the user approves.

## 2. Carry continuity

Pass only goal and scope, confirmed decisions and user terms, current state and
evidence, next action, and exclusions. Omit empty fields and conversation text.

## 3. Launch and transfer

Run `handoff-orchestrator.py` with `--user-approved`, this pane, cwd, provider,
and the continuity fields. The script creates and labels an independent tab,
starts the receiving orchestrator, prompts it to invoke `boss-say` and then
accept, and verifies the handshake after that route is established. It retries
once; final failure closes the
new tab and leaves ownership here.

## 4. Leave the scope

On acceptance, report the new tab and transferred scope compactly. Continue only
the scope passed through `--retains`. When none is retained, let the launcher
close this pane after it emits the accepted result.

**Complete when:** the receiver accepted and this orchestrator left the scope,
or the failed new tab is closed and ownership remains here.
