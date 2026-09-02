# Verification

## Before implementation

- The same-version regression test failed because no Codex `plugin remove` call
  was recorded. This reproduced the installer branch that left stale cached
  content in place.

## Source verification

| Requirement | Evidence | Result |
| --- | --- | --- |
| Fresh Codex installation adds once | Existing fresh-install fake-CLI test | Pass |
| Existing same-version Codex installation is replaced | New same-version fake-CLI regression test | Pass |
| Existing same-version Claude installation is replaced | New same-version fake-CLI regression test | Pass |
| Existing provider installations with no reported version are replaced | New missing-version fake-CLI regression test | Pass |
| Existing stale-version Codex installation is replaced | Existing stale-install fake-CLI test | Pass |
| Provider state query failures stop before mutation | New failing-list fake-CLI regression tests | Pass |
| Claude project-only installation is not uninstalled as user scope | New project-only fake-CLI regression test | Pass |
| Claude persistent data is preserved on replacement | Exact uninstall argv assertion and fake-CLI guard | Pass |
| Repository behavior remains intact | `python3 -m unittest discover -s tests` (254 tests) | Pending rerun |
| Scripts and manifests remain valid | Python compile, `bash -n`, `git diff --check`, `claude plugin validate .` | Pass |
| Failure boundaries and contract received an independent read-only review | Final adversarial re-review, all findings closed | Pass |

## Real installer verification

- Two consecutive `bash scripts/install.sh` runs completed successfully at
  `0.18.27` after the final implementation.
- The second same-version run visibly uninstalled and installed the Claude user
  plugin with its data preserved, and removed and added the Codex plugin.
- Claude's user-scope listing and Codex's installed listing both reported
  `0.18.27`.
- Both provider caches matched the checkout for the two manifests, installer,
  installer tests, and all four specification artifacts before this result was
  recorded. The post-push installer run refreshes the finalized verification
  artifact as part of delivery.
