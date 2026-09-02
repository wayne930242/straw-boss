# Design

## Smallest approach

Determine existence by matching the plugin ID in each provider's installed list
rather than inferring it from the version value. Add a missing plugin once;
otherwise replace it regardless of whether the reported version is current,
different, empty, or absent. Claude uses uninstall with `--keep-data` followed
by install; Codex uses remove followed by add. Each provider's version probe
remains the post-install failure boundary.

Claude's presence and version probes require both the plugin ID and `user`
scope, matching the scope mutated by the installer. Other scopes are ignored.

Each presence probe prints only `present` or `absent`. Command or JSON failures
stay nonzero and stop the installer before that provider's plugin mutation; an
unexpected successful value is also rejected.

This uses Codex's public plugin commands and does not derive internal cache
paths or add content-hash policy to the installer. The explicit installer run
may briefly leave the plugin absent if re-adding fails, but `set -e` makes that
failure visible and this is the same replacement boundary already used for
version changes.

## Verification shape

The fake Codex CLI records commands and models plugin state. A same-version
fixture must observe remove followed by add. Real delivery then runs the
checkout installer twice at the bumped version and compares installed content
with the checkout.
