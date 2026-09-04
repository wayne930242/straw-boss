# Design

## Installer source seam

`scripts/install.sh` exposes one optional flag: no flag selects the two
providers' GitHub marketplace syntax; `--local` selects the checkout root.
Each provider adapter reads its current marketplace descriptor before acting:
an absent source is added, a matching remote source is refreshed through the
provider's update command, a matching local source is kept, and a mismatched
source is removed then added with the selected source. Plugin replacement and
version verification remain behind the same provider adapters.

This keeps source selection in the installer rather than spreading manual
cleanup steps into the README. Removing this logic would force every caller to
inspect and repair provider-specific marketplace state itself.

## Local-file copy seam

Add `scripts/copy-local-files.py` with this interface:

```text
copy-local-files.py --repo-root <root> --app <name> --worktree <path>
                    [--allow-sensitive]
```

The command loads the app from the root `.claude/straw-boss/apps.json`, keeps
every configured path inside the source app and destination worktree, and
preflights the complete list before copying anything. Required absence and
unapproved sensitive entries fail the preflight. Optional absence is returned
in structured output. It maps the source app's path relative to its Git
top-level into the verified worktree, so a monorepo app such as `apps/web`
receives `.env` at `apps/web/.env`; an independently nested repository maps to
the worktree root. Files and directories are the two concrete copy adapters.

The caller knows only the app, source repository, destination worktree, and
whether the user approved sensitive copies. Configuration interpretation,
path containment, all-or-nothing preflight, and content-free reporting stay
local to the script.

## Alternatives and risks

- Keeping copy behavior only in skill prose was rejected because required-file
  failure could not be tested against a real worktree.
- Adding copy logic to the dispatch launcher was rejected because worktree
  preparation precedes dispatch and belongs to the coordinator.
- The script refuses an existing destination rather than overwriting it; a
  coordinator can inspect that conflict without risking tracked or user-created
  worktree content.

## Verification surface

Installer behavior is tested through recorded fake-CLI commands and state.
Local-file behavior is tested only through the public command against temporary
Git worktrees, including files, directories, required absence, optional
absence, sensitive approval, containment, and destination conflicts.
