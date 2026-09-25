"""Pi dispatch recovery: the `dispatch_control` helper and the extension's Node tests."""

import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "pi/scripts/pi-dispatch.py"
SPEC = importlib.util.spec_from_file_location("pi_dispatch", HELPER)
DISPATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISPATCH)


class DispatchCliTest(unittest.TestCase):
    def test_roll_call_reattach_and_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            agent = home / ".pi/agent"
            ledger = agent / "dispatch-ledger/owner.json"
            ledger.parent.mkdir(parents=True)
            child = home / "child.jsonl"
            child.write_text("")
            ledger.write_text(json.dumps([{
                "id": "child-1", "name": "worker", "task": "Task", "cwd": str(home),
                "sessionFile": str(child), "paneId": "w1:p2", "status": "running",
            }]))
            bin_dir = home / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "herdr"
            fake.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path(os.environ['HERDR_TEST_LOG']).open('a') as out:
    out.write(json.dumps(args) + '\\n')
if args[:2] == ['pane', 'process-info']:
    processes = [{'name': 'zsh'}] if args[-1] == 'w1:p3' else []
    print(json.dumps({'result': {'process_info': {'foreground_processes': processes}}}))
elif args[:2] == ['tab', 'create']:
    Path(os.environ['HERDR_TEST_LOG']).with_suffix('.handoff').write_text(next(
        value.split('=', 1)[1] for index, value in enumerate(args) if index > 0 and args[index - 1] == '--env' and value.startswith('PI_HANDOFF_ID=')
    ))
    print(json.dumps({'result': {'root_pane': {'pane_id': 'w1:p3'}}}))
elif args[:2] == ['agent', 'start']:
    transfer_id = Path(os.environ['HERDR_TEST_LOG']).with_suffix('.handoff').read_text()
    ready = Path(os.environ['PI_CODING_AGENT_DIR']) / 'handoffs' / f'{transfer_id}.ready'
    ready.write_text('receiver')
    print(json.dumps({'result': {}}))
elif args[:2] == ['pane', 'run']:
    pass
else:
    print(json.dumps({'result': {}}))
""")
            fake.chmod(0o755)
            log = home / "herdr.log"
            env = {**os.environ, "HOME": str(home), "PI_CODING_AGENT_DIR": str(agent),
                   "PI_SESSION_ID": "owner", "HERDR_ENV": "1", "HERDR_WORKSPACE_ID": "w9", "HERDR_TEST_LOG": str(log),
                   "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"]}

            def call(*args):
                return subprocess.run(["python3", str(HELPER), *args],
                                      env=env, check=True, capture_output=True, text=True).stdout

            self.assertIn("child-1 | running", call("roll-call"))
            self.assertIn("Resumed worker in w1:p2", call("reattach", "child-1"))
            self.assertIn("active dispatches: 1", call("handoff", "--cwd", str(home), "--summary", "Continue the task"))
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertTrue(any(args[:2] == ["pane", "run"] and "PI_SUBAGENT_SESSION" in args[-1] for args in calls))
            self.assertTrue(any(args[:2] == ["tab", "create"] and "PI_HANDOFF_ID=" in " ".join(args) for args in calls))
            self.assertTrue(any(args[:2] == ["tab", "create"] and args[args.index("--workspace") + 1] == "w9" for args in calls))
            self.assertTrue(any(args[:2] == ["agent", "start"] and "--kind" in args for args in calls))
            self.assertTrue(any(args[:2] == ["agent", "prompt"] and "Continue the task" in args[-1] for args in calls))
            self.assertEqual(json.loads(ledger.read_text())[0]["status"], "transferred")
            transfers = list((agent / "handoffs").glob("*.json"))
            self.assertEqual(len(transfers), 1)
            self.assertEqual(json.loads(transfers[0].read_text())["dispatches"][0]["status"], "running")


class HandoffCommitTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.agent = self.home / "agent"
        self.ledger = self.agent / "dispatch-ledger"
        self.handoffs = self.agent / "handoffs"
        self.ledger.mkdir(parents=True)
        self.owner_file = self.ledger / "owner.json"
        self.owner_file.write_text(json.dumps([{
            "id": "worker", "name": "worker", "task": "Finish", "cwd": str(self.home),
            "sessionFile": str(self.home / "child.jsonl"), "status": "running",
        }]))
        for name, value in (("AGENT_DIR", self.agent), ("LEDGER_DIR", self.ledger), ("HANDOFF_DIR", self.handoffs)):
            patcher = patch.object(DISPATCH, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(DISPATCH.uuid, "uuid4", return_value=SimpleNamespace(hex="transfer"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_handoff(self, fail=None):
        original_write = DISPATCH.write_json

        def write(path, data):
            if fail == "prepare" and path == self.handoffs / "transfer.json":
                raise OSError("prepare failed")
            if fail == "commit" and path == self.handoffs / "transfer.json" and data.get("state") == "committed":
                raise OSError("commit failed")
            if fail == "ledger" and path == self.owner_file:
                raise OSError("ledger view failed")
            return original_write(path, data)

        def start(_name, _pane):
            (self.handoffs / "transfer.ready").write_text("receiver")

        with patch.object(DISPATCH, "write_json", side_effect=write), \
             patch.object(DISPATCH, "new_pane", return_value="test:pane"), \
             patch.object(DISPATCH, "start_receiving_agent", side_effect=start), \
             patch.object(DISPATCH, "herdr", return_value={}), redirect_stdout(io.StringIO()) as output:
            if fail in ("prepare", "commit"):
                with self.assertRaises(OSError):
                    DISPATCH.handoff("owner", str(self.home), "Continue")
            else:
                DISPATCH.handoff("owner", str(self.home), "Continue")
            return output.getvalue()

    def test_prepare_failure_retains_owner(self):
        self.run_handoff("prepare")
        self.assertEqual(json.loads(self.owner_file.read_text())[0]["status"], "running")
        self.assertFalse((self.handoffs / "transfer.json").exists())

    def test_commit_failure_retains_owner(self):
        self.run_handoff("commit")
        self.assertEqual(json.loads(self.owner_file.read_text())[0]["status"], "running")
        self.assertFalse((self.handoffs / "transfer.json").exists())

    def test_ledger_view_failure_keeps_committed_owner(self):
        output = self.run_handoff("ledger")
        self.assertIn("active dispatches: 1", output)
        self.assertEqual(json.loads((self.handoffs / "transfer.json").read_text())["state"], "committed")
        self.assertEqual(json.loads(self.owner_file.read_text())[0]["status"], "running")
        with redirect_stdout(io.StringIO()) as inventory:
            DISPATCH.roll_call("owner")
        self.assertIn("worker | transferred", inventory.getvalue())
        with self.assertRaises(ValueError):
            DISPATCH.reattach("owner", "worker")

    def test_committed_handoff_keeps_receiver_session_marker(self):
        self.run_handoff()
        self.assertEqual((self.handoffs / "transfer.ready").read_text(), "receiver")

    def test_reattach_preserves_concurrent_ledger_update(self):
        updated = threading.Event()
        worker = None

        def update_status():
            with DISPATCH.lock_ledger("owner"):
                records = DISPATCH.read_ledger("owner")
                records[0]["status"] = "done"
                DISPATCH.write_json(self.owner_file, records)
            updated.set()

        def create_pane(_cwd, _label):
            nonlocal worker
            worker = threading.Thread(target=update_status)
            worker.start()
            self.assertTrue(updated.wait(2))
            return "test:pane"

        with patch.object(DISPATCH, "new_pane", side_effect=create_pane), \
             patch.object(DISPATCH, "herdr", return_value={}), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "changed while opening"):
                DISPATCH.reattach("owner", "worker")
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(json.loads(self.owner_file.read_text())[0]["status"], "done")


class HandoffReceiverStartTest(unittest.TestCase):
    def test_poll_interval_defaults_to_production_value(self):
        env = {key: value for key, value in os.environ.items() if key != "PI_DISPATCH_POLL_SECONDS"}
        output = subprocess.run(
            ["python3", "-c", "import importlib.util,sys; s=importlib.util.spec_from_file_location('d', sys.argv[1]); "
             "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.POLL_SECONDS)", str(HELPER)],
            env=env, capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual(output, "0.2")

    def test_handoff_commits_after_receiver_starts(self):
        spec = importlib.util.spec_from_file_location("pi_dispatch", HELPER)
        dispatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dispatch)
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / ".pi/agent"
            dispatch.LEDGER_DIR = agent / "dispatch-ledger"
            dispatch.HANDOFF_DIR = agent / "handoffs"
            dispatch.write_json(dispatch.ledger_path("owner"), [{
                "id": "child-1", "name": "worker", "task": "Task", "cwd": directory,
                "sessionFile": str(Path(directory) / "child.jsonl"), "status": "running",
            }])
            dispatch.new_pane = lambda *_args: "w1:p3"
            calls = []
            starts = 0

            def herdr(*args):
                nonlocal starts
                calls.append(args)
                if args[:2] == ("agent", "start"):
                    self.assertEqual(dispatch.read_ledger("owner")[0]["status"], "running")
                    starts += 1
                    if starts == 1:
                        raise RuntimeError('agent_pane_busy: shell is not ready')
                    transfer = next(dispatch.HANDOFF_DIR.glob("*.json"))
                    transfer.with_suffix(".ready").write_text("receiver")
                return {}

            dispatch.herdr = herdr
            dispatch.handoff("owner", directory, "Continue")
            self.assertEqual(starts, 2)
            self.assertEqual(dispatch.read_ledger("owner")[0]["status"], "transferred")

    def test_uncertain_receiver_start_keeps_original_owner(self):
        spec = importlib.util.spec_from_file_location("pi_dispatch_uncertain", HELPER)
        dispatch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dispatch)
        with tempfile.TemporaryDirectory() as directory:
            agent = Path(directory) / ".pi/agent"
            dispatch.LEDGER_DIR = agent / "dispatch-ledger"
            dispatch.HANDOFF_DIR = agent / "handoffs"
            dispatch.write_json(dispatch.ledger_path("owner"), [{
                "id": "child-uncertain", "name": "worker", "task": "Task", "cwd": directory,
                "sessionFile": str(Path(directory) / "child.jsonl"), "status": "running",
            }])
            dispatch.new_pane = lambda *_args: "w1:p3"
            dispatch.herdr = lambda *_args: (_ for _ in ()).throw(RuntimeError("timeout: startup may continue"))
            with self.assertRaisesRegex(RuntimeError, "timeout: startup may continue"):
                dispatch.handoff("owner", directory, "Continue")
            self.assertEqual(dispatch.read_ledger("owner")[0]["status"], "running")
            self.assertEqual(len(list(dispatch.HANDOFF_DIR.glob("*.json"))), 0)


@unittest.skipUnless(shutil.which("node"), "node is required for the Pi extension tests")
class PiExtensionNodeTests(unittest.TestCase):
    def test_extension_suites_pass(self):
        suites = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests/pi").glob("*.mjs"))
        self.assertTrue(suites)
        result = subprocess.run(
            ["node", "--experimental-strip-types", "--test", *suites],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
