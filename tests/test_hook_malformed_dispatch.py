"""Malformed dispatch sidecars must not crash unrelated sessions' hooks."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def run_hook(script, payload):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        input=json.dumps(payload), text=True, capture_output=True, timeout=10,
    )


@pytest.mark.parametrize("malformed", [[], None, 7, "unexpected"])
def test_hooks_ignore_unrelated_non_object_dispatch_sidecars(malformed):
    dispatch = Path.home() / ".straw-boss" / "dispatch"
    dispatch.mkdir(parents=True)
    (dispatch / "other.status.json").write_text(json.dumps(malformed))
    archive = dispatch / "archive"
    archive.mkdir()
    (archive / "other.json").write_text(json.dumps(malformed))
    for script in ("orchestrator-priming.py", "dispatched-agent-stop-guard.py"):
        result = run_hook(script, {"session_id": "unrelated-test-session", "source": "startup"})
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr


@pytest.mark.parametrize("malformed", [[], None, {"status": []}, {"status": {}}, {"status": "unknown"}])
def test_active_worker_stays_blocked_with_malformed_report(malformed):
    dispatch = Path.home() / ".straw-boss" / "dispatch"
    dispatch.mkdir(parents=True)
    instruction = {"session_id": "active-test-worker", "status": "in-progress", "task": "Test"}
    (dispatch / "test.json").write_text(json.dumps(instruction))
    (dispatch / "test.status.json").write_text(json.dumps(malformed))
    result = run_hook("dispatched-agent-stop-guard.py", {"session_id": "active-test-worker"})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["decision"] == "block"


def test_valid_worker_contract_and_terminal_report_still_work():
    dispatch = Path.home() / ".straw-boss" / "dispatch"
    dispatch.mkdir(parents=True)
    contract = dispatch / "test.contract.md"
    contract.write_text("Mandatory worker contract")
    instruction = {
        "session_id": "active-test-worker", "status": "in-progress", "task": "Test",
        "contract_path": str(contract),
    }
    (dispatch / "test.json").write_text(json.dumps(instruction))
    (dispatch / "test.status.json").write_text('{"status":"done"}')
    start = run_hook("orchestrator-priming.py", {"session_id": "active-test-worker", "source": "resume"})
    assert start.returncode == 0, start.stderr
    assert start.stdout.strip() == "Mandatory worker contract"
    stop = run_hook("dispatched-agent-stop-guard.py", {"session_id": "active-test-worker"})
    assert stop.returncode == 0, stop.stderr
    assert stop.stdout == ""


def test_default_fixture_home_is_used_by_native_child_and_dispatch_state():
    result = subprocess.run(
        [sys.executable, "-c", "from pathlib import Path; print(Path.home())"],
        capture_output=True, text=True, check=True,
    )
    assert Path(result.stdout.strip()) == Path(os.environ["HOME"])
    assert os.environ["HOME"] == os.environ["USERPROFILE"]
    from straw_boss.dispatch.state import straw_boss_root
    assert straw_boss_root() == Path(os.environ["HOME"]) / ".straw-boss"


def test_lifecycle_fixture_writes_dispatch_only_to_its_own_home():
    import unittest
    from tests.dispatched_agent_lifecycle_support import DispatchedAgentLifecycleFixture

    class Harness(DispatchedAgentLifecycleFixture, unittest.TestCase):
        pass

    harness = Harness()
    harness.setUp()
    try:
        path, _ = harness.write_dispatch(slug="home-isolation-proof")
        assert path.parent == harness.home / ".straw-boss" / "dispatch"
        assert path.is_file()
        assert not (Path.home() / ".straw-boss" / "dispatch" / path.name).exists()
    finally:
        harness.tearDown()
