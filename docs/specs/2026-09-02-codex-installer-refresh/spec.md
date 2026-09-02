Status: approved
Approved at: 2026-09-02T13:40:55+08:00
Approved from: user reply "要"

# Observable contract

1. A fresh Codex installation adds the plugin once.
2. An existing Codex installation is removed and added again on every installer
   run, even when Codex already reports the manifest version.
3. An existing Claude installation is uninstalled with its persistent data
   preserved, then installed again on every installer run. A missing Claude
   user-scope installation is installed once; project and local installations
   do not stand in for user scope.
4. If either provider's installed-plugin state cannot be read, the installer
   exits before adding or removing that provider's plugin.
5. The installer exits unsuccessfully when either available provider does not
   report the manifest version after installation.

## Reality anchor

Fake-CLI regression tests prove both same-version provider paths replace their
installed plugin. The complete test suite and shell validation must pass. After
delivery, two consecutive real installer runs must leave Claude and Codex at the
release version; the second run must visibly replace both providers again, and
each installed cache must match the checkout content.
