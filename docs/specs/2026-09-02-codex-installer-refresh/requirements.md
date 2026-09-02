# Plugin installer refresh

## Outcome

Keep checkout installation reliable when a provider already reports the target
version. Running the installer must refresh the installed plugin content rather
than treating version equality as proof that its cache matches the checkout.

## Confirmed decisions

- An existing Codex installation is removed and added again on every installer
  run, including when its reported version already matches the manifests.
- A missing Codex installation is added once without a preceding removal.
- An existing Claude installation is uninstalled while preserving its data,
  then installed again on every installer run. A missing installation is added
  once.
- Claude presence and version checks use only the user scope managed by this
  installer; project and local installations do not stand in for it.
- If either provider's installed-plugin state cannot be read, installation
  stops before adding or removing that provider's plugin.
- Installation still fails when the provider does not report the manifest
  version after its update or replacement.
- This delivery bumps, commits, pushes, and installs the patch release. It does
  not create a tag or hosted release.

## Open decisions

- None.
