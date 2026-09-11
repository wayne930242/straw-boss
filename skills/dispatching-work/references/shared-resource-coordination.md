# Shared-resource coordination

`claim-resource.py` coordinates resources shared by concurrent tasks under one user account on one machine.
Locks live in `~/.straw-boss/locks/`; cross-user or cross-machine access needs resource-side coordination.
The worker resolves actual app-local resource identities; the main agent carries known cross-task constraints.

## Ports

For a configurable port, claim immediately before starting the server:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" claim-port \
  --app "<app>" --key "<absolute-worktree-path>" --holder "<app>--<slug>" \
  --requester-instruction-path "<instruction-path>" --note "dev server for <slug>"
```

The script derives candidates from a stable hash of `--key`, within `--base`/`--range` (defaults 3000/500), trying up to `--max-attempts` (default 5).
Bind the returned `port`.
Choose a different band or attempt limit if app configuration or observed contention requires it.
`claim-port` tries alternatives and returns failure when exhausted; fixed ports use `wait` below.

Port resources use `port--<app>--<port-number>`.
The script probes IPv4 availability before claiming; `held_externally: true` means the probe found a listener.
The actual server bind still verifies availability after the claim.
Claim once, run the server, then release; a repeated claim sees an existing lock or the caller's own listener as contention.

For a frontend human or pseudo-human checkpoint, the main agent claims before dispatch, using the instruction stem or checkout path as `--key`.
Put the returned number in the brief and choose a TTL covering the task's lifetime.
The worker binds that assigned number using the existing claim.

A fixed port retains its required value, including when another service's origin/CORS configuration constrains it.
Use `wait` on that exact port resource.

## Shared database and fixed-port locks

For shared database migrations, derive a stable DB identity from the actual target (such as host and database).
Resource names become filenames and accept `A-Za-z0-9._-`; use `--` as the component separator.

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" wait \
  --resource "db-migration--<db-identity>" --holder "<app>--<slug>" \
  --requester-instruction-path "<instruction-path>" \
  --ttl-seconds <expected-hold-duration> --note "<reason>"
```

For a fixed port, substitute `port--<app>--<port-number>`.
The script owns waiting and progress reporting.
Omit `--max-wait-seconds` to follow the current holder's TTL; set it when the task needs an earlier failure deadline.

Set TTL from the expected protected operation's duration.
A claim is reclaimable after its TTL; the result reports `ttl_seconds` and `note_to_holder`.
If `reclaimed_stale: true`, inspect the prior holder's dispatch before using a shared DB.
A still-`in-progress` holder requires resolving whether it is still using the resource; expiry alone does not establish that its process stopped.

## Release and inspect

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" release \
  --resource "<resource-id>" --holder "<app>--<slug>"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" list --prefix "port--"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" list --prefix "db-migration--"
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/claim-resource.py" status --resource "<resource-id>"
```

Release after protected use.
`list`/`status` return the holder, instruction path, age, and expiry across this user's main agents.
Use this registry to resolve assignments.
`gc` removes expired locks when cleanup is needed.
A forced release overrides holder validation and requires evidence that the lock is expired or user confirmation that the holder has stopped.

## Releasing every lock on a wrapped-up instruction

[dispatching-work wrap-up](../SKILL.md#wrap-up) releases every remaining lock associated with the instruction before archiving, for `done`, `failed`, and `cancelled`.
Include both the main agent's dispatch-time port claim and any worker-held lock whose release is unconfirmed.
Check the registry to verify release.

## Contention messages

A contended result identifies the holder instruction.
Use [asking-peer-agents](../../asking-peer-agents/SKILL.md) for an ETA when needed.
A peer reply supplies information; resource access still requires a successful claim.
