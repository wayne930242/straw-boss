# Plan mechanics

[boss-say](../../boss-say/SKILL.md#plan-and-schedule) owns planning and scheduling.
This reference defines its persisted formats, queries, and app-rooted task preparation.
Single-task launch syntax lives in [dispatch mechanics](dispatch-mechanics.md).

## Plan file

The main agent writes `~/.straw-boss/plans/<plan-slug>/plan.json` from resolved tasks and dependencies.
Create sibling `status/` and `artifacts/` directories at the same time.

```json
{
  "plan_id": "p-<slug>",
  "created_at": "2026-09-11T10:00:00+08:00",
  "status": "planning",
  "tasks": [
    {"task_id": "t1", "app": "api", "description": "Required outcome", "depends_on": [], "status": "planned"},
    {"task_id": "t2", "app": "web", "description": "Dependent outcome", "depends_on": ["t1"], "status": "planned"}
  ]
}
```

`plan.status` moves from `planning` to `in-progress` to `done` once every task is terminal.
Each task moves from `planned` to `dispatched` to `done`/`failed`/`cancelled`.
`dispatch-task.py write` records dispatch and `wrap-up-task.py` synchronizes terminal status.
The main agent owns plan mutations.

## Cross-task artifacts

When a dependent task requires its prerequisite's output, name a file under `artifacts/<task-id>-<label>.<ext>`.
Put the exact path in both briefs: the producer writes it, the consumer reads it as required input.
A dependency edge alone carries ordering, not file content.

## Status directory

Each worker reports through `report-task-status.py --instruction-path <path>`.
A plan task's status lives in `status/<task-id>.json`; the standalone equivalent is the instruction's `.status.json` sibling.

```json
{"status": "done", "note": "Outcome and evidence", "timestamp": "2026-09-11T10:30:00+08:00"}
```

Terminal values are `done`, `failed`, and coordinator-authored `cancelled`.
Checkpoints `awaiting-authorization`, `awaiting-user-input`, and `awaiting-main-agent` remain `dispatched` in the plan and hold their slot.
Worker status is single-writer except for the explicit cancellation and closed-worker recovery operations.
[Handle events](../SKILL.md#handle-events) defines the response to each status.

## Read plan state

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <slug> --task <task-id>
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <slug> --not-done
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <slug> --in-flight
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/read-plan-status.py" --plan <slug> --ready
```

- `--task`: one task's status.
- `--not-done`: all unfinished tasks, including the planned queue.
- `--in-flight`: dispatched tasks with non-terminal status; use for slot accounting.
- `--ready`: planned tasks whose prerequisites are all `done`; use as the scheduler's candidates.

## Monitor plan status

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/watch-plan-status.py" --plan <slug>
```

Run one watcher through the harness's supported background/monitor facility.
It emits each valid status-file content revision and, on startup, the current persisted states for recovery.
Malformed or partial JSON is retried on the next scan.
Live transport notifications supplement this persisted scheduling signal.

Send events to [boss-say's scheduler](../../boss-say/SKILL.md#plan-and-schedule).
Terminal cleanup uses [dispatching-work wrap-up](../SKILL.md#wrap-up), followed by the item's [git lifecycle completion](../../shipping-task/SKILL.md#complete-the-lifecycle) when applicable.
Stop the watcher when every plan task is terminal; it does not stop itself.

## Same-task continuation

Before wrap-up, check for a later phase of the same logical task already established by the user or plan.
Keep that instruction and pane for continuation.
A different task receives a fresh dispatch.

For Claude, compact first:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent control \
  --message "/compact <focus>"
```

Then continue using the same instruction; Codex uses only this call:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/send-dispatch-message.py" \
  --instruction-path <path> --to worker --intent redirect \
  --message "Continue from the referenced instruction." --ref "<next-phase artifact>"
```

The artifact contains the next phase and `report-task-status.py --instruction-path <path>`.
The watcher observes the later rewrite of the same status file.

## Worktree ownership

The main agent creates and verifies each team-mode worktree with plain git, including apps with their own git workflow skill.
Resolve `<app_dir>` from the app configuration.

```bash
git -C "<app_dir>" worktree add "<app_dir>-<slug>" -b "<branch>" "<base_branch>"
git -C "<app_dir>-<slug>" rev-parse --show-toplevel
```

Require the returned top-level path to be the new worktree.
If a repository using `extensions.worktreeConfig` resolves to the primary checkout, inspect the worktree's actual git directory and merge these overrides into its `config.worktree`, preserving existing settings:

```ini
[core]
    worktree = <absolute-worktree-path>
    bare = false
```

Verify the top-level path again.
A failed repair remains a dispatch blocker.
The verified path becomes instruction `repo_root`; the launcher creates its worker pane in the coordinator's shared tab.

### Local files

Read declared `localFiles` through the [apps configuration](../../init/references/apps-config-schema.md).
Copy only after worktree verification:

```bash
uv run --script "${CLAUDE_PLUGIN_ROOT}/scripts/copy-local-files.py" \
  --repo-root "<repo-root>" --app "<app>" --worktree "<absolute-worktree-path>"
```

A missing entry is an error by default: stop before launching the worker and report its path and note.
Skip a missing source only when that exact entry has `optional: true`.
Add `--allow-sensitive` only with user authorization covering the sensitive entries.
The script validates the list before copying and reports copied/skipped paths without exposing file contents.

### Moving base and removal

When parallel tasks target the same moving base or the remote base advanced, have the worker refresh through the app's established merge/rebase workflow before pushing or opening the MR, resolve conflicts, and verify the resulting change.
Otherwise the app owns its usual pre-push sequence.

After [dispatch cleanup](../SKILL.md#wrap-up), the git lifecycle owner removes the worktree:

```bash
git -C "<app_dir>" worktree remove "<absolute-worktree-path>"
```

Plain git owns worktree creation/removal; the launcher and wrap-up flow own worker panes.
The coordinator's shared tab stays open.
