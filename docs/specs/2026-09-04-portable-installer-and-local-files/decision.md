# Portable installer and local worktree files

## Outcome

Keep normal Straw Boss installations independent of the checkout path that ran
the installer, and make missing worktree-local files fail at the point where
their absence can still be explained clearly.

## Decision record

| Question | Answer | Basis | Status |
| --- | --- | --- | --- |
| What source does the installer use by default? | The repository's GitHub marketplace source. | Current manual installation already uses this source; the user approved fixing every reported path issue. | confirmed |
| How does a developer intentionally use checkout content? | `bash scripts/install.sh --local`. | The user approved retaining local installation only as an explicit development mode. | confirmed |
| What happens to a marketplace registered to the wrong source? | Rebind it to the selected source; refresh an already-correct remote source in place. | Avoid stale absolute paths without deleting a working remote registration before a network refresh. | grounded |
| How are absent `localFiles` interpreted? | Required unless that entry says `optional: true`; required absence blocks dispatch. | The user approved explicit required/optional behavior and clear errors. | confirmed |
| How are local files copied? | A dedicated script validates every entry before copying and reports only paths, never contents. | An executable seam is needed for credible worktree verification and consistent failure behavior. | grounded |

No consequential decisions remain open.
