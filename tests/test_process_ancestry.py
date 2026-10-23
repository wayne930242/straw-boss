from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from straw_boss.herdr import session


class ProcessAncestryTests(unittest.TestCase):
    def validate(self, foreground):
        payload = {"result": {"process_info": {
            "pane_id": "repair-pane", "foreground_processes": foreground,
        }}}
        with patch.dict(os.environ, HERDR_PANE_ID="repair-pane"), patch.object(
            session, "run_herdr", return_value=payload
        ):
            session.validate_current_process_in_pane("repair-pane")

    def test_windows_walk_accepts_real_ancestor_without_ps(self):
        with patch.object(session.os, "name", "nt"), patch.object(
            session.os, "getpid", return_value=300
        ), patch.object(session, "_windows_process_parents", return_value={
            300: 200, 200: 100, 100: 0,
        }), patch.object(session, "_windows_process_created", side_effect=lambda pid: pid), patch.object(session.subprocess, "run", side_effect=FileNotFoundError):
            self.validate([{"pid": 100}])

    def test_windows_walk_rejects_unrelated_missing_and_cyclic_ancestors(self):
        for parents in ({300: 200, 200: 0}, {}, {300: 200, 200: 300}):
            with self.subTest(parents=parents), patch.object(
                session.os, "name", "nt"
            ), patch.object(session.os, "getpid", return_value=300), patch.object(
                session, "_windows_process_parents", return_value=parents
            ), patch.object(session, "_windows_process_created", return_value=1):
                with self.assertRaisesRegex(ValueError, "not running inside"):
                    self.validate([{"pid": 999}])

    def test_windows_snapshot_failure_remains_fail_closed(self):
        with patch.object(session.os, "name", "nt"), patch.object(
            session, "_windows_process_parents", side_effect=OSError("denied")
        ):
            with self.assertRaisesRegex(ValueError, "could not validate"):
                self.validate([{"pid": os.getpid()}])

    def test_recycled_parent_pid_cannot_prove_ancestry(self):
        with patch.object(session.os, "name", "nt"), patch.object(
            session.os, "getpid", return_value=300
        ), patch.object(session, "_windows_process_parents", return_value={300: 200, 200: 0}), patch.object(
            session, "_windows_process_created", side_effect=lambda pid: {300: 10, 200: 20}[pid]
        ):
            with self.assertRaisesRegex(ValueError, "not running inside"):
                self.validate([{"pid": 200}])

    def test_unavailable_creation_time_fails_closed(self):
        with patch.object(session.os, "name", "nt"), patch.object(
            session.os, "getpid", return_value=300
        ), patch.object(session, "_windows_process_parents", return_value={300: 200, 200: 0}), patch.object(
            session, "_windows_process_created", side_effect=OSError("denied")
        ):
            with self.assertRaisesRegex(ValueError, "could not validate"):
                self.validate([{"pid": 200}])

    def test_pane_environment_mismatch_rejects_before_process_lookup(self):
        with patch.dict(os.environ, HERDR_PANE_ID="other"), patch.object(
            session, "run_herdr"
        ) as herdr:
            with self.assertRaisesRegex(ValueError, "caller pane mismatch"):
                session.validate_current_process_in_pane("repair-pane")
            herdr.assert_not_called()

    def test_posix_walk_still_accepts_ancestor_and_rejects_unrelated_pid(self):
        for foreground, accepted in ((100, True), (999, False)):
            with self.subTest(foreground=foreground), patch.object(
                session.os, "name", "posix"
            ), patch.object(session.os, "getpid", return_value=300), patch.object(
                session.subprocess, "run", side_effect=[
                    SimpleNamespace(returncode=0, stdout="100"),
                    SimpleNamespace(returncode=0, stdout="1"),
                ]
            ) as run:
                if accepted:
                    self.validate([{"pid": foreground}])
                else:
                    with self.assertRaisesRegex(ValueError, "not running inside"):
                        self.validate([{"pid": foreground}])
                self.assertEqual(run.call_args_list[0].args[0], ["ps", "-o", "ppid=", "-p", "300"])

    @unittest.skipUnless(os.name == "nt", "requires native Windows ctypes")
    def test_native_enumeration_errors_close_snapshot_handle(self):
        import ctypes

        for first_succeeds in (False, True):
            kernel = SimpleNamespace(
                CreateToolhelp32Snapshot=Mock(return_value=123),
                Process32FirstW=Mock(return_value=first_succeeds),
                Process32NextW=Mock(return_value=False),
                CloseHandle=Mock(return_value=True),
            )
            with self.subTest(first_succeeds=first_succeeds), patch.object(
                ctypes, "WinDLL", return_value=kernel
            ), patch.object(ctypes, "get_last_error", return_value=5):
                with self.assertRaises(OSError):
                    session._windows_process_parents()
                kernel.CloseHandle.assert_called_once_with(123)

    @unittest.skipUnless(os.name == "nt", "requires native Windows process APIs")
    def test_native_windows_parent_and_validation_without_ps(self):
        parents = session._windows_process_parents()
        self.assertEqual(parents[os.getpid()], os.getppid())
        with patch.object(session.subprocess, "run", side_effect=FileNotFoundError):
            self.validate([{"pid": os.getppid()}])
            with self.assertRaisesRegex(ValueError, "not running inside"):
                self.validate([{"pid": 0xFFFFFFFF}])


if __name__ == "__main__":
    unittest.main()
