from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "read-apps-config.py"


class AppsConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        # The script canonicalizes its repo root, and macOS hands out
        # temporary directories under the /var -> /private/var symlink.
        self.repo = Path(temporary.name).resolve() / "repo with spaces"
        self.canonical = self.repo / ".straw-boss" / "apps.json"
        self.legacy = self.repo / ".claude" / "straw-boss" / "apps.json"
        self.canonical.parent.mkdir(parents=True)
        self.legacy.parent.mkdir(parents=True)

    def read(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo-root", str(self.repo)],
            capture_output=True, text=True, timeout=10, cwd=ROOT,
        )

    def test_reads_both_layouts_and_preserves_unknown_fields(self) -> None:
        payload = {"apps": [{"name": "web", "custom": True}], "future": [1]}
        for path in (self.canonical, self.legacy):
            with self.subTest(path=path):
                path.write_text(json.dumps(payload))
                result = self.read()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {
                    "path": str(path), "legacy": path == self.legacy,
                    "config": payload,
                })
                self.assertEqual(json.loads(path.read_text()), payload)
                path.unlink()

    def test_canonical_wins_even_if_legacy_is_invalid(self) -> None:
        self.canonical.write_text('{"apps": []}')
        self.legacy.write_text("{")
        result = self.read()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], str(self.canonical))

    def test_missing_has_distinct_exit_code_and_does_not_write(self) -> None:
        result = self.read()
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn(str(self.canonical), result.stderr)
        self.assertIn(str(self.legacy), result.stderr)
        self.assertFalse(self.canonical.exists())
        self.assertFalse(self.legacy.exists())

    def test_invalid_canonical_never_falls_back(self) -> None:
        self.legacy.write_text('{"apps": []}')
        for contents in (b"{", b"[]", b'{"apps": null}', b"\xff"):
            with self.subTest(contents=contents):
                self.canonical.write_bytes(contents)
                result = self.read()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn(str(self.canonical), result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_legacy_is_an_error(self) -> None:
        self.legacy.write_text("{")
        result = self.read()
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.legacy), result.stderr)

    def test_directory_and_broken_symlink_are_errors_not_missing(self) -> None:
        self.legacy.write_text('{"apps": []}')
        self.canonical.mkdir()
        result = self.read()
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.canonical), result.stderr)
        self.canonical.rmdir()
        self.canonical.symlink_to(self.repo / "missing.json")
        result = self.read()
        self.assertEqual(result.returncode, 1)
        self.assertIn(str(self.canonical), result.stderr)


if __name__ == "__main__":
    unittest.main()
