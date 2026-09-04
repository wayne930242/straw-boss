from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "copy-local-files.py"


class CopyLocalFilesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name) / "repo"
        self.worktree = Path(self.tempdir.name) / "worktree"
        self.repo.mkdir()
        self.run_git("init", "--quiet")
        self.run_git("config", "user.email", "test@example.com")
        self.run_git("config", "user.name", "Straw Boss Test")
        (self.repo / ".gitignore").write_text(".env\ncerts/\n")
        (self.repo / "README.md").write_text("fixture\n")
        (self.repo / "apps" / "web").mkdir(parents=True)
        (self.repo / "apps" / "web" / "README.md").write_text("nested fixture\n")
        self.write_config([])
        self.run_git("add", ".")
        self.run_git("commit", "--quiet", "-m", "fixture")
        self.run_git("worktree", "add", "--quiet", "-b", "test-worktree", str(self.worktree))

    def run_git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        )

    def write_config(
        self, local_files: list[dict[str, object]], *, app_dir: str = "."
    ) -> None:
        path = self.repo / ".claude" / "straw-boss" / "apps.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "apps": [
                        {
                            "name": "fixture",
                            "dir": app_dir,
                            "match": ["fixture"],
                            "localFiles": local_files,
                        }
                    ]
                }
            )
        )

    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(self.repo),
                "--app",
                "fixture",
                "--worktree",
                str(self.worktree),
                *args,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_copies_declared_file_and_directory_into_real_worktree(self) -> None:
        (self.repo / ".env").write_text("TOKEN=secret-value\n")
        (self.repo / "certs").mkdir()
        (self.repo / "certs" / "client.pem").write_text("certificate-content\n")
        self.write_config([{"path": ".env"}, {"path": "certs"}])

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.worktree / ".env").read_text(), "TOKEN=secret-value\n")
        self.assertEqual(
            (self.worktree / "certs" / "client.pem").read_text(),
            "certificate-content\n",
        )
        self.assertNotIn("secret-value", result.stdout + result.stderr)
        self.assertNotIn("certificate-content", result.stdout + result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"copied": [".env", "certs"], "skipped_optional": []},
        )

    def test_copies_into_nested_app_path_in_monorepo_worktree(self) -> None:
        (self.repo / "apps" / "web" / ".env").write_text("nested\n")
        self.write_config([{"path": ".env"}], app_dir="apps/web")

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.worktree / ".env").exists())
        self.assertEqual(
            (self.worktree / "apps" / "web" / ".env").read_text(), "nested\n"
        )

    def test_missing_required_file_blocks_all_copies(self) -> None:
        (self.repo / ".env").write_text("available\n")
        self.write_config(
            [
                {"path": ".env"},
                {"path": "missing.env", "note": "needed for startup"},
            ]
        )

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required local files", result.stderr)
        self.assertIn("missing.env (needed for startup)", result.stderr)
        self.assertFalse((self.worktree / ".env").exists())

    def test_explicitly_optional_missing_file_is_reported_and_skipped(self) -> None:
        self.write_config(
            [{"path": "optional.env", "optional": True, "note": "extra tooling"}]
        )

        result = self.run_script()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "copied": [],
                "skipped_optional": ["optional.env (extra tooling)"],
            },
        )

    def test_sensitive_file_requires_explicit_copy_approval(self) -> None:
        (self.repo / ".env").write_text("TOKEN=secret-value\n")
        self.write_config([{"path": ".env", "sensitive": True}])

        refused = self.run_script()

        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("require --allow-sensitive", refused.stderr)
        self.assertFalse((self.worktree / ".env").exists())
        self.assertNotIn("secret-value", refused.stdout + refused.stderr)

        approved = self.run_script("--allow-sensitive")

        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertEqual((self.worktree / ".env").read_text(), "TOKEN=secret-value\n")

    def test_rejects_source_paths_outside_the_app(self) -> None:
        self.write_config([{"path": "../outside.env"}])

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes its root", result.stderr)

    def test_refuses_to_overwrite_an_existing_worktree_destination(self) -> None:
        (self.repo / ".env").write_text("source\n")
        (self.worktree / ".env").write_text("destination\n")
        self.write_config([{"path": ".env"}])

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worktree destinations already exist: .env", result.stderr)
        self.assertEqual((self.worktree / ".env").read_text(), "destination\n")

    def test_overlapping_destinations_fail_before_copying(self) -> None:
        (self.repo / "certs").mkdir()
        (self.repo / "certs" / "client.pem").write_text("certificate\n")
        self.write_config([{"path": "certs"}, {"path": "certs/client.pem"}])

        result = self.run_script()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("certs/client.pem overlaps certs", result.stderr)
        self.assertFalse((self.worktree / "certs").exists())
