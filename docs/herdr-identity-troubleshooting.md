# Missing Herdr pane identity

Registration requires `HERDR_PANE_ID` in the process running the command. A
visible Herdr pane, matching working directory, or focused terminal does not
establish which pane owns that process.

If registration reports a missing inherited pane id while the agent appears
inside Herdr, stop repeating registration or opening sessions with the same
launch path. Check the launcher and the environment passed to the agent and
its tool shell. The observation alone does not identify which component
omitted the variable.

## Collect evidence from the failing process

In the agent's PowerShell tool shell, run these read-only commands:

```powershell
Get-Item Env:HERDR_PANE_ID, Env:HERDR_ENV, Env:CODEX_THREAD_ID -ErrorAction SilentlyContinue
herdr status
herdr agent list
```

Record the installed Straw Boss version and the exact registration error.
Share only the relevant pane record; omit unrelated workspaces and private
task content. If sandbox access blocks the Herdr socket, use the harness's
normal approval path for the read-only commands. A socket access failure is
different from a missing environment variable.

Compare the launcher, agent process, and tool-shell environments to find the
boundary where the pane id disappears. Never fill in an assumed id from the
focused pane, a terminal title, or cwd. Preserve existing dispatches and do
not restart shared services just to retry registration.

## Distinguish registration from message delivery

The missing-pane check runs before registration writes a directory record.
An absent `agent_session` in Herdr is a separate observation: registration
supports a terminal fingerprint for Codex, while later transport performs
its own sender and session checks. Diagnose the exact refused step rather
than treating all identity observations as one failure.

After a verified integration change, confirm the command process inherits
the correct pane id and retry official registration from that process. Then
exercise formal dispatch, completion notification, and dependent artifact
handoff. Passing standalone hook callbacks does not establish that these
Herdr routes work.
