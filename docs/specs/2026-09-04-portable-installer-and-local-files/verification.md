# Verification

## Requirement evidence

| Requirement | Evidence | Result |
| --- | --- | --- |
| Default installation uses GitHub sources without the checkout path | `test_fresh_install_adds_remote_marketplaces_and_plugins` asserts the exact Claude and Codex add commands and rejects the checkout path in every provider call | pass |
| Local checkout installation is explicit | `test_local_flag_explicitly_uses_checkout_marketplaces` exercises `--local` and observes the exact checkout path for both providers | pass |
| Existing marketplace sources are refreshed or rebound correctly | Fake-CLI tests cover matching remote, stale local, and mismatched remote registrations for both providers | pass |
| State query failures precede the corresponding mutation | Marketplace-list and plugin-list failure tests observe no marketplace or plugin mutation for the failing provider stage | pass |
| Same-version plugin replacement and manifest version checks remain intact | Existing stale, same-version, missing-version, and post-install version tests pass with both manifests at `0.18.31` | pass |
| Missing required local files block all copying and identify paths only | `test_missing_required_file_blocks_all_copies` uses a real temporary Git worktree, observes the named missing path, and proves an available sibling was not copied | pass |
| Explicitly optional local files are skipped and reported | `test_explicitly_optional_missing_file_is_reported_and_skipped` observes successful structured output with the skipped app-relative path | pass |
| Sensitive files require explicit approval | `test_sensitive_file_requires_explicit_copy_approval` proves the first call copies nothing or exposes contents and `--allow-sensitive` enables the copy | pass |
| App-relative paths map correctly into monorepo worktrees | `test_copies_into_nested_app_path_in_monorepo_worktree` proves `apps/web/.env` lands beneath the same nested app path, not at worktree root | pass |
| Copy boundaries reject unsafe or ambiguous destinations | Real-worktree tests reject source escape, existing destinations, and overlapping directory/file destinations before copying | pass |

## Validation summary

- Focused tests: `python3 -m unittest tests.test_copy_local_files tests.test_install_script tests.test_skill_instruction_quality` — 81 passed.
- Complete suite: `python3 -m unittest discover -s tests -p 'test_*.py'` — 274 passed.
- Script validation: `bash -n scripts/install.sh` and Python compilation passed.
- Plugin manifest: `claude plugin validate .` passed.
- Patch hygiene: `git diff --check` passed.

## Review verdict

The installer keeps remote and local modes distinct, preserves the existing
same-version replacement behavior, and does not remove a matching remote
marketplace before refreshing it. The local-file interface centralizes config
validation, Git-root mapping, content-free reporting, sensitive approval, and
preflight failure without expanding the dispatch launcher's responsibilities.

No deviations from the approved contract remain. The repository changes have
not been committed, pushed, or installed; those delivery states are outside
this approved change request.
