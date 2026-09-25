"""The Pi package manifest loads exactly the Pi host's skills and extensions."""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PI_SKILLS = {"boss-say", "work-on", "choosing-graph", "shipping-task", "reporting-to-user", "dispatching-work"}
PI_EXTENSIONS = {"dispatch-recovery.ts", "pane-balance.ts"}
RESOLVE = """
const [managerModule, settingsModule, root, agentDir] = process.argv.slice(1);
const { DefaultPackageManager } = await import(managerModule);
const { SettingsManager } = await import(settingsModule);
const manager = new DefaultPackageManager({
  cwd: agentDir, agentDir, settingsManager: SettingsManager.create(agentDir, agentDir),
});
const paths = await manager.resolveExtensionSources([root], { temporary: true });
console.log(JSON.stringify({
  skills: paths.skills.filter((item) => item.enabled).map((item) => item.path),
  extensions: paths.extensions.filter((item) => item.enabled).map((item) => item.path),
}));
"""


def pi_core() -> Path | None:
    binary = shutil.which("pi")
    if not binary:
        return None
    for parent in Path(binary).resolve().parents:
        core = parent / "dist/core"
        if (core / "package-manager.js").is_file():
            return core
    return None


class PiPackageManifestTests(unittest.TestCase):
    def test_manifest_lists_the_pi_host_resources(self) -> None:
        manifest = json.loads((ROOT / "package.json").read_text())["pi"]
        skills = {Path(entry).name for entry in manifest["skills"]}
        extensions = {Path(entry).name for entry in manifest["extensions"]}
        self.assertEqual(skills, PI_SKILLS)
        self.assertEqual(extensions, PI_EXTENSIONS)
        for entry in manifest["skills"]:
            self.assertTrue(entry.startswith("./pi/skills/"), entry)
            self.assertTrue((ROOT / entry / "SKILL.md").is_file(), entry)
        for entry in manifest["extensions"]:
            self.assertTrue((ROOT / entry).is_file(), entry)

    def test_package_version_matches_the_plugin_manifests(self) -> None:
        version = json.loads((ROOT / "package.json").read_text())["version"]
        for manifest in ("plugin.json", ".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            self.assertEqual(json.loads((ROOT / manifest).read_text())["version"], version, manifest)

    @unittest.skipUnless(pi_core(), "Pi is not installed")
    def test_pi_resolves_exactly_the_pi_host_resources(self) -> None:
        core = pi_core()
        with tempfile.TemporaryDirectory() as agent_dir:
            result = subprocess.run(
                ["node", "--input-type=module", "-e", RESOLVE,
                 (core / "package-manager.js").as_uri(), (core / "settings-manager.js").as_uri(),
                 str(ROOT), agent_dir],
                capture_output=True, text=True, check=True,
            )
        resolved = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual({Path(path).parent.name for path in resolved["skills"]}, PI_SKILLS)
        for path in resolved["skills"]:
            self.assertTrue(Path(path).resolve().is_relative_to(ROOT / "pi/skills"), path)
        self.assertEqual({Path(path).name for path in resolved["extensions"]}, PI_EXTENSIONS)


if __name__ == "__main__":
    unittest.main()
