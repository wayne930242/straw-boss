Status: approved
Approved at: 2026-09-04T13:50:11+08:00
Approved from: user reply "好，都幫修"

# Observable contract

1. `bash scripts/install.sh` registers or refreshes the GitHub marketplace
   source and leaves no dependency on the source checkout's absolute path.
2. `bash scripts/install.sh --local` explicitly registers the current checkout
   for development.
3. An existing local or mismatched marketplace is rebound to the selected
   source; an already-correct remote marketplace is updated in place.
4. A marketplace query failure stops that provider before marketplace mutation;
   a plugin-state query failure stops it before plugin mutation.
5. Existing plugins are still replaced on every installer run, including a
   same-version run, and the reported version must match both manifests.
6. Every `localFiles` entry is required by default. A missing required source
   blocks dispatch before any local file is copied and identifies its
   app-relative path without exposing contents.
7. A missing `localFiles` entry is skipped only when it explicitly declares
   `optional: true`; copied and skipped paths are reported.
8. Sensitive local files require the caller's explicit approval before the copy
   command can succeed.

## Compatibility and non-goals

- Existing `localFiles` entries without `optional` remain valid and become
  required, matching their documented purpose as files a fresh worktree needs.
- The installer continues preserving Claude plugin data during replacement.
- This change does not distribute local secrets, migrate per-machine dispatch
  state, commit, push, install the modified plugin, or create a hosted release.

## Applied standards and evidence

- `docs/roles.md` remains authority for dispatch ownership and lifecycle.
- `skills/init/references/apps-config-schema.md` owns project configuration.
- `scripts/install.sh` and `tests/test_install_script.py` establish the existing
  provider installation precedent.

## Reality anchor

Fake provider CLIs exercise remote, local, source-rebinding, refresh, and query
failure paths. A temporary real Git repository and `git worktree` exercise the
public local-file copy command. The full suite, shell validation, manifest
validation, and diff review are the completion checkpoint.
