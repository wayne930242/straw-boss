"""Review regressions at the real copy CLI boundary, using synthetic history."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from straw_boss.jev_codex import configuration
from straw_boss.jev_storage import criteria_version

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/jev-codex-copy.py"


@pytest.fixture
def copy_case(tmp_path):
    history = [{"type": "message", "role": "user", "content": []},
               {"type": "function_call", "call_id": "x", "name": "exec", "arguments": "{}"},
               {"type": "function_call_output", "call_id": "x", "output": "synthetic private content"}]
    history += [{"type": "message", "role": "assistant", "content": []} for _ in range(7)]
    source, scores, output = tmp_path / "history.json", tmp_path / "scores.json", tmp_path / "copy"
    source.write_text(json.dumps(history))
    scores.write_text(json.dumps({"criteria_version": criteria_version(configuration()[0]),
                                 "scores": {"x": {"keepCall": 0, "keepResult": 0}}}))
    command = [sys.executable, str(SCRIPT), "--history", str(source), "--scores", str(scores),
               "--output-dir", str(output)]
    return history, scores, output, command


@pytest.mark.parametrize("bad", [[], 42, "invalid", None])
@pytest.mark.parametrize("container", [False, True])
def test_malformed_score_shapes_write_unchanged_fallback(copy_case, bad, container):
    history, scores, output, command = copy_case
    data = json.loads(scores.read_text())
    data["scores"] = bad if container else {"x": bad}
    scores.write_text(json.dumps(data))
    result = subprocess.run(command, env={**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}, capture_output=True)
    assert result.returncode == 0 and result.stdout == result.stderr == b""
    assert json.loads((output / "candidate.json").read_text()) == history
    assert json.loads((output / "recovery.json").read_text())["original_history"] == history
    record = json.loads((output / "benchmark.jsonl").read_text())
    assert record["decision"] == "fallback" and record["fallback_reason"] == "missing-or-invalid-jev-score"


def load_cli(monkeypatch, command):
    spec = importlib.util.spec_from_file_location("jev_copy_review", SCRIPT)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    monkeypatch.setenv("STRAW_BOSS_JEV", "1")
    monkeypatch.setenv("TYPESAFE_API_KEY", "fixture")
    monkeypatch.setattr(sys, "argv", command[1:])
    return cli


def test_directory_replacement_between_writes_keeps_all_files_together(copy_case, tmp_path, monkeypatch):
    history, _, output, command = copy_case
    cli = load_cli(monkeypatch, command)
    moved, redirect = tmp_path / "pinned", tmp_path / "redirect"
    redirect.mkdir()
    original_open = os.open
    swapped = False

    def swap_after_open(path, flags, *args, **kwargs):
        nonlocal swapped
        fd = original_open(path, flags, *args, **kwargs)
        if Path(path).name == "candidate.json":
            output.rename(moved)
            output.symlink_to(redirect, target_is_directory=True)
            swapped = True
        return fd

    monkeypatch.setattr(os, "open", swap_after_open)
    assert cli.main() == 0 and swapped
    assert list(redirect.iterdir()) == []
    assert {p.name for p in moved.iterdir()} == {"candidate.json", "recovery.json", "benchmark.jsonl"}
    assert json.loads((moved / "recovery.json").read_text())["original_history"] == history


def test_directory_replacement_before_open_rejects_link(copy_case, tmp_path, monkeypatch):
    _, _, output, command = copy_case
    cli = load_cli(monkeypatch, command)
    redirect = tmp_path / "redirect"
    redirect.mkdir()
    original_mkdir = os.mkdir

    def swap_after_mkdir(path, *args, **kwargs):
        original_mkdir(path, *args, **kwargs)
        if Path(path).name == output.name:
            output.rename(tmp_path / "original")
            output.symlink_to(redirect, target_is_directory=True)

    monkeypatch.setattr(os, "mkdir", swap_after_mkdir)
    with pytest.raises(OSError):
        cli.main()
    assert list(redirect.iterdir()) == []


def test_group_writable_parent_is_rejected(copy_case, tmp_path):
    _, _, output, command = copy_case
    tmp_path.chmod(0o770)
    result = subprocess.run(command, env={**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}, capture_output=True)
    assert result.returncode != 0 and not output.exists()


@pytest.mark.parametrize("field", ["keepCall", "keepResult"])
@pytest.mark.parametrize("value", [10**400, -(10**400)], ids=["huge-positive", "huge-negative"])
def test_huge_json_integer_uses_cli_fallback(copy_case, field, value):
    history, scores, output, command = copy_case
    data = json.loads(scores.read_text())
    data["scores"]["x"][field] = value
    scores.write_text(json.dumps(data))
    result = subprocess.run(command, env={**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}, capture_output=True)
    assert result.returncode == 0 and result.stdout == result.stderr == b""
    assert json.loads((output / "candidate.json").read_text()) == history
    assert json.loads((output / "recovery.json").read_text())["original_history"] == history
    record = json.loads((output / "benchmark.jsonl").read_text())
    assert record["fallback_reason"] == "missing-or-invalid-jev-score" and record["decisions"] == []


def test_intermediate_symlink_swap_before_open_is_rejected(copy_case, tmp_path, monkeypatch):
    _, _, _, command = copy_case
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True, mode=0o700)
    alternate = tmp_path / "alternate"
    (alternate / "parent").mkdir(parents=True, mode=0o700)
    command[-1] = str(parent / "copy")
    cli = load_cli(monkeypatch, command)
    original_open = os.open
    swapped = False

    def swap_before_open(path, *args, **kwargs):
        nonlocal swapped
        # Exercise both the former full-path open and component-relative open.
        if not swapped and (Path(path) == parent or (Path(path).name == ancestor.name and "dir_fd" in kwargs)):
            ancestor.rename(tmp_path / "original-ancestor")
            ancestor.symlink_to(alternate, target_is_directory=True)
            swapped = True
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap_before_open)
    with pytest.raises(OSError):
        cli.main()
    assert swapped and not (alternate / "parent/copy").exists()


def test_writable_intermediate_ancestor_is_rejected(copy_case, tmp_path):
    _, _, _, command = copy_case
    ancestor = tmp_path / "untrusted"
    parent = ancestor / "private-parent"
    parent.mkdir(parents=True, mode=0o700)
    ancestor.chmod(0o777)
    command[-1] = str(parent / "copy")
    result = subprocess.run(command, env={**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}, capture_output=True)
    assert result.returncode != 0 and not (parent / "copy").exists()


def test_sticky_ancestor_with_private_parent_is_supported(copy_case, tmp_path):
    _, _, _, command = copy_case
    ancestor = tmp_path / "sticky"
    parent = ancestor / "private-parent"
    parent.mkdir(parents=True, mode=0o700)
    ancestor.chmod(0o1777)
    command[-1] = str(parent / "copy")
    result = subprocess.run(command, env={**os.environ, "STRAW_BOSS_JEV": "1", "TYPESAFE_API_KEY": "fixture"}, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert (parent / "copy/benchmark.jsonl").is_file()


def test_pinned_intermediate_ancestor_survives_replacement(copy_case, tmp_path, monkeypatch):
    _, _, _, command = copy_case
    ancestor = tmp_path / "ancestor"
    parent = ancestor / "parent"
    parent.mkdir(parents=True, mode=0o700)
    alternate = tmp_path / "alternate"
    (alternate / "parent").mkdir(parents=True, mode=0o700)
    command[-1] = str(parent / "copy")
    cli = load_cli(monkeypatch, command)
    original_open = os.open
    swapped = False

    def swap_after_open(path, *args, **kwargs):
        nonlocal swapped
        fd = original_open(path, *args, **kwargs)
        if not swapped and Path(path).name == ancestor.name and "dir_fd" in kwargs:
            ancestor.rename(tmp_path / "original-ancestor")
            ancestor.symlink_to(alternate, target_is_directory=True)
            swapped = True
        return fd

    monkeypatch.setattr(os, "open", swap_after_open)
    assert cli.main() == 0 and swapped
    assert not (alternate / "parent/copy").exists()
    assert {p.name for p in (tmp_path / "original-ancestor/parent/copy").iterdir()} == {
        "candidate.json", "recovery.json", "benchmark.jsonl"}
