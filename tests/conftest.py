"""Every test starts with a temporary home, including native Windows callers."""

import pytest


@pytest.fixture(autouse=True)
def isolated_user_home(tmp_path, monkeypatch):
    home = tmp_path / "user-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # Explicit provider roots inherited from a live agent must not escape the
    # home sandbox. Individual tests can supply their own temporary roots.
    for name in ("CODEX_HOME", "CLAUDE_CONFIG_DIR", "STRAW_BOSS_HOME"):
        monkeypatch.delenv(name, raising=False)
