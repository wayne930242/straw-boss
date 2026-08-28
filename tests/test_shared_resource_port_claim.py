from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def port_is_free(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("0.0.0.0", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def reserve_free_base(count: int, start: int = 45000) -> int:
    """Lowest port at or above `start` with `count` consecutive free ports.

    claim-port probes the real OS port before it ever touches a lock file, so a
    test that asserts on exact assigned numbers needs a band this machine is
    not already sitting on.
    """
    for base in range(start, 65500 - count):
        if all(port_is_free(base + offset) for offset in range(count)):
            return base
    raise AssertionError(f"no run of {count} free ports at or above {start}")


class SharedResourcePortClaimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.locks = self.home / ".straw-boss" / "locks"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_claim(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "claim-resource.py"), *args],
            cwd=ROOT,
            env={**os.environ, "HOME": str(self.home)},
            capture_output=True,
            text=True,
            timeout=30,
        )

    def claim_port(
        self,
        *,
        app: str = "webapp",
        key: str,
        holder: str,
        base: int,
        port_range: int = 1,
        max_attempts: int = 3,
        instruction_path: str = "/home/boss/.straw-boss/dispatch/webapp--task.json",
    ) -> dict[str, object]:
        result = self.run_claim(
            "claim-port",
            "--app",
            app,
            "--key",
            key,
            "--holder",
            holder,
            "--base",
            str(base),
            "--range",
            str(port_range),
            "--max-attempts",
            str(max_attempts),
            "--requester-instruction-path",
            instruction_path,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_claim_port_assigns_a_port_and_records_the_holder(self) -> None:
        base = reserve_free_base(1)
        claimed = self.claim_port(key="/wt/a", holder="webapp--task-a", base=base)

        self.assertTrue(claimed["acquired"])
        self.assertEqual(claimed["port"], base)
        self.assertEqual(claimed["resource"], f"port--webapp--{base}")

        lock = json.loads((self.locks / f"port--webapp--{base}.json").read_text())
        self.assertEqual(lock["holder"], "webapp--task-a")
        self.assertEqual(
            lock["holder_instruction_path"],
            "/home/boss/.straw-boss/dispatch/webapp--task.json",
        )

    def test_same_key_derives_the_same_port_across_separate_claims(self) -> None:
        base = reserve_free_base(60)
        first = self.claim_port(
            key="/wt/stable", holder="webapp--task-a", base=base, port_range=50
        )
        release = self.run_claim(
            "release",
            "--resource",
            str(first["resource"]),
            "--holder",
            "webapp--task-a",
        )
        self.assertEqual(release.returncode, 0, release.stderr)

        second = self.claim_port(
            key="/wt/stable", holder="webapp--task-b", base=base, port_range=50
        )
        self.assertEqual(second["port"], first["port"])

    def test_a_second_worker_on_the_same_key_gets_the_next_port(self) -> None:
        base = reserve_free_base(2)
        first = self.claim_port(key="/wt/shared", holder="webapp--task-a", base=base)
        second = self.claim_port(key="/wt/shared", holder="webapp--task-b", base=base)

        self.assertEqual(first["port"], base)
        self.assertEqual(second["port"], base + 1)
        self.assertTrue((self.locks / f"port--webapp--{base}.json").is_file())
        self.assertTrue((self.locks / f"port--webapp--{base + 1}.json").is_file())

    def test_a_port_bound_outside_the_lock_is_never_assigned(self) -> None:
        base = reserve_free_base(2)
        occupant = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupant.bind(("0.0.0.0", base))
        occupant.listen(1)
        try:
            claimed = self.claim_port(key="/wt/a", holder="webapp--task-a", base=base)
        finally:
            occupant.close()

        self.assertEqual(claimed["port"], base + 1)
        self.assertFalse((self.locks / f"port--webapp--{base}.json").is_file())

    def test_list_reports_which_worker_holds_which_port(self) -> None:
        base = reserve_free_base(2)
        self.claim_port(key="/wt/shared", holder="webapp--task-a", base=base)
        self.claim_port(key="/wt/shared", holder="webapp--task-b", base=base)

        result = self.run_claim("list", "--prefix", "port--")
        self.assertEqual(result.returncode, 0, result.stderr)
        assignments = {
            entry["resource"]: entry["holder"]
            for entry in json.loads(result.stdout)["locks"]
        }
        self.assertEqual(
            assignments,
            {
                f"port--webapp--{base}": "webapp--task-a",
                f"port--webapp--{base + 1}": "webapp--task-b",
            },
        )

    def test_releasing_a_port_returns_it_to_the_next_worker(self) -> None:
        base = reserve_free_base(1)
        self.claim_port(key="/wt/a", holder="webapp--task-a", base=base)
        release = self.run_claim(
            "release",
            "--resource",
            f"port--webapp--{base}",
            "--holder",
            "webapp--task-a",
        )
        self.assertEqual(release.returncode, 0, release.stderr)

        reclaimed = self.claim_port(key="/wt/a", holder="webapp--task-c", base=base)
        self.assertEqual(reclaimed["port"], base)

    def test_an_exhausted_band_fails_loudly_instead_of_assigning_a_held_port(self) -> None:
        base = reserve_free_base(1)
        self.claim_port(key="/wt/a", holder="webapp--task-a", base=base)

        result = self.run_claim(
            "claim-port",
            "--app",
            "webapp",
            "--key",
            "/wt/a",
            "--holder",
            "webapp--task-b",
            "--base",
            str(base),
            "--range",
            "1",
            "--max-attempts",
            "1",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not claim a free port", result.stderr)


if __name__ == "__main__":
    unittest.main()
