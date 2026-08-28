---
name: bringing-coworker
description: Bring one interactive coworker into a dispatched worker's current Herdr tab and exact worktree. Use from an in-progress worker when the user asks to pull in a colleague or a rule requires a human-facing second-agent review.
---

# Bring a coworker

## 1. Scope the second opinion

Give the coworker one outcome that can run beside your current task. Default to
review-only. A writing task names a disjoint repo-relative `--writable-path`
scope.

Complete when the task is independently useful and its write scope is disjoint.

## 2. Start beside you

Use your canonical instruction path from the dispatch contract:

```bash
uv run --script "$HOME/.straw-boss/bin/run-straw-boss-script.py" \
  --origin-root "${CLAUDE_PLUGIN_ROOT:-$PWD}" --prefer-installed \
  --script dispatch-coworker.py -- \
  --parent-instruction-path <your-instruction-path> \
  --slug <unique-slug> [--name <short-name>] \
  --agent-kind claude|codex --task "<user requirement and integrated context>" \
  [--writable-path <repo-relative-path>]...
```

The command authenticates your session, opens the coworker in this tab and
worktree, injects its contract, and confirms delivery. Omit `--name` for a
`<app>-coworker` handle derived automatically. Complete when it returns the
coworker's pane and instruction path.

## 3. Work with the user

Point the user to the coworker pane. The coworker and user decide feedback and
choose the specification, design, implementation, and the verification method
inside the anchor you scoped for it; continue on your disjoint scope.

Complete when the coworker reports `done` or `failed`; parent and root
coordinator receive that terminal event automatically.

## 4. Integrate and close

Review the reported result, integrate the conclusion, close only the coworker
pane, then run `wrap-up-task.py --app <app> --slug <slug>`. The shared tab and
your own instruction remain active.

Complete when the pane is closed and the coworker instruction is archived.
