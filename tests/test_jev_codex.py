"""Copied-history parity at the adapter boundary; no backend or live writes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from straw_boss.jev_codex import (
    configuration, history_from_rows, measurement, normalized_pair, prune, replacement_rows,
)
from straw_boss.jev_storage import pair_bytes


def fixture_history():
    history = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "task"}]}]
    for key, command in [("contract", "cat /a/.straw-boss/dispatch/task.json"),
                         ("truncate", "check"), ("drop", "old check")]:
        history += [{"type": "function_call", "call_id": key, "name": "exec",
                     "arguments": json.dumps({"cmd": command})},
                    {"type": "function_call_output", "call_id": key, "output": "x" * 900}]
    history += [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": str(i)}]} for i in range(7)]
    return history


def test_policy_locks_and_real_branch_semantics_recovery():
    _, policy = configuration()
    original = fixture_history()
    untouched = copy.deepcopy(original)
    candidate, decisions = prune(original, {
        "contract": {"keepCall": .49, "keepResult": .45},
        "truncate": {"keepCall": .5, "keepResult": .25},
        "drop": {"keepCall": .49, "keepResult": .49},
    }, policy)
    assert original == untouched
    assert decisions[0]["lock_reason"] == "governing_source"
    assert decisions[0]["keepCall"] is None
    assert [d["action"] for d in decisions] == ["keep", "drop_result", "drop_call"]
    assert candidate[4]["output"].startswith("x" * 300 + "\n[fast-jev-compaction truncated 600")
    assert decisions[0]["bytes_before"] == pair_bytes(*normalized_pair(original[1], original[2]))
    assert decisions[2]["bytes_after"] == 0
    assert [x for x in candidate if x["type"] == "message"] == [x for x in original if x["type"] == "message"]
    replacements = {i: item for d in decisions if d["action"] != "keep"
                    for i, item in zip(d["original_indices"], d["original_content"])}
    # Truncated items consume a retained position; dropped items do not.
    dropped = {i for d in decisions if d["action"] == "drop_call" for i in d["original_indices"]}
    iterator = iter(candidate)
    restored = []
    for i in range(len(original)):
        current = None if i in dropped else next(iterator)
        restored.append(replacements.get(i, current))
    assert restored == original and next(iterator, None) is None


@pytest.mark.parametrize("path", ["/tmp/a.contract.md", r"C:\work\AGENTS.md", "CLAUDE.md", "GEMINI.md", "skills/a/SKILL.md"])
def test_shared_governing_patterns(path):
    _, policy = configuration()
    history = fixture_history()
    history[1]["arguments"] = json.dumps({"cmd": "cat " + path})
    candidate, decisions = prune(history, {key: {"keepCall": 1, "keepResult": 1} for key in ("truncate", "drop")}, policy)
    assert decisions[0]["lock_reason"] == "governing_source"
    assert candidate == history


def test_latest_six_and_unpaired_calls_survive_without_scores():
    _, policy = configuration()
    history = fixture_history()[:7]
    history.append({"type": "function_call", "call_id": "pending", "name": "exec", "arguments": "{}"})
    assert prune(history, {}, policy)[0] == history


@pytest.mark.parametrize("input_value", [
    {"cmd": "cd ~/.straw-boss/dispatch && cat task.json"},
    {"cmd": "cat task.json", "workdir": "/home/user/.straw-boss/dispatch"},
])
def test_policy_v3_relative_dispatch_inputs(input_value):
    _, policy = configuration()
    history = fixture_history()
    history[1]["arguments"] = json.dumps(input_value)
    _, decisions = prune(history, {key: {"keepCall": 1, "keepResult": 1} for key in ("truncate", "drop")}, policy)
    assert decisions[0]["lock_reason"] == "governing_source"


def test_bare_filename_without_source_identity_remains_a_known_limit():
    _, policy = configuration()
    history = fixture_history()
    history[1]["arguments"] = json.dumps({"cmd": "cat task.json"})
    _, decisions = prune(history, {key: {"keepCall": .1, "keepResult": .1} for key in ("contract", "truncate", "drop")}, policy)
    assert decisions[0]["lock_reason"] is None


def test_truncate_preserves_images_and_limits_aggregate_text():
    _, policy = configuration()
    history = fixture_history()
    image = {"type": "input_image", "image_url": "data:image/png;base64,example"}
    history[4]["output"] = [{"type": "input_text", "text": "a" * 200}, image,
                            {"type": "input_text", "text": "b" * 200}]
    candidate, _ = prune(history, {"truncate": {"keepCall": .5, "keepResult": .2},
                                  "drop": {"keepCall": 1, "keepResult": 1}}, policy)
    assert candidate[4]["output"][1] == image
    assert candidate[4]["output"][0]["text"] == "a" * 200
    assert candidate[4]["output"][2]["text"].startswith("b" * 100 + "\n[fast-jev")


@pytest.mark.parametrize("score", [None, float("nan"), -1, 1.1, True])
def test_invalid_score_fails_instead_of_dropping(score):
    _, policy = configuration()
    with pytest.raises(ValueError, match="invalid-jev-score"):
        prune(fixture_history(), {"truncate": {"keepCall": score, "keepResult": .2}}, policy)


def test_backend_gate_and_cache_requirement():
    _, policy = configuration()
    before = {"input_tokens": 1000, "cached_input_tokens": 0}
    assert measurement(before, {"input_tokens": 900, "cached_input_tokens": 0}, policy)["decision"] == "apply"
    assert measurement(before, {"input_tokens": 901, "cached_input_tokens": 0}, policy)["decision"] == "fallback"
    for usage in [{"input_tokens": 900}, {"input_tokens": 900, "cached_input_tokens": 1}]:
        with pytest.raises(ValueError, match="zero-cache"):
            measurement(before, usage, policy)


def test_replacement_discards_old_ancestors_and_later_resume_appends():
    rows = [{"timestamp": "now", "type": "response_item", "payload": {"type": "message", "text": "old-only"}}]
    history = fixture_history()
    replaced = replacement_rows(rows, history)
    assert history_from_rows(replaced) == history
    assert rows[0]["payload"]["text"] == "old-only"
    replaced.append({"type": "response_item", "payload": {"type": "message", "text": "new turn"}})
    assert history_from_rows(replaced) == history + [{"type": "message", "text": "new turn"}]


@pytest.mark.parametrize("enabled,key", [("0", "present"), ("1", ""), ("1", " ")])
def test_opt_in_missing_key_silence_before_argument_parsing(tmp_path, enabled, key):
    script = Path(__file__).resolve().parents[1] / "scripts/jev-codex-copy.py"
    run = subprocess.run([sys.executable, str(script)], env={**os.environ,
        "STRAW_BOSS_JEV": enabled, "TYPESAFE_API_KEY": key, "STRAW_BOSS_HOME": str(tmp_path)}, capture_output=True)
    assert run.returncode == 0 and run.stdout == run.stderr == b""
    assert list(tmp_path.iterdir()) == []


def test_copy_cli_private_recovery_and_candidate_only_benchmark(tmp_path):
    from straw_boss.jev_storage import criteria_version
    criteria, _ = configuration()
    history = tmp_path / "history.json"
    history.write_text(json.dumps(fixture_history()))
    scores = tmp_path / "scores.json"
    scores.write_text(json.dumps({"criteria_version": criteria_version(criteria), "scores": {
        "truncate": {"keepCall": .5, "keepResult": .2}, "drop": {"keepCall": .1, "keepResult": .1}}}))
    output = tmp_path / "copy"
    script = Path(__file__).resolve().parents[1] / "scripts/jev-codex-copy.py"
    command = [sys.executable, str(script), "--history", str(history), "--scores", str(scores), "--output-dir", str(output)]
    env = {**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}
    run = subprocess.run(command, env=env, capture_output=True)
    assert run.returncode == 0, run.stderr
    record = json.loads((output / "benchmark.jsonl").read_text())
    assert record["outcome"] is None and record["tokens_after"] is None
    assert record["application"]["live_application_supported"] is False
    assert record["jev"]["requests"] == 0
    assert json.loads((output / "recovery.json").read_text())["original_history"] == fixture_history()
    assert (output.stat().st_mode & 0o777) == 0o700
    assert all((path.stat().st_mode & 0o777) == 0o600 for path in output.iterdir())
    assert subprocess.run(command, env=env, capture_output=True).returncode != 0
    scores.write_text(json.dumps({"criteria_version": "stale", "scores": {}}))
    fallback = tmp_path / "fallback"
    command[-1] = str(fallback)
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    assert json.loads((fallback / "candidate.json").read_text()) == fixture_history()
    assert json.loads((fallback / "benchmark.jsonl").read_text())["fallback_reason"] == "criteria-version-mismatch"
