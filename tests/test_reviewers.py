import os

import pytest

from lean_review import reviewers


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / ".credentials.json").write_text("{}")
    (home / ".claude" / "CLAUDE.md").write_text("personal")
    (home / ".codex").mkdir()
    (home / ".codex" / "auth.json").write_text("{}")
    (home / ".codex" / "AGENTS.md").write_text("personal")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(reviewers, "REV_HOME_BASE", str(tmp_path / "rev"))
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setenv(k, "secret")
    return home


@pytest.mark.parametrize("provider,cred,personal", [
    ("claude", ".claude/.credentials.json", ".claude/CLAUDE.md"),
    ("codex", ".codex/auth.json", ".codex/AGENTS.md"),
])
def test_clean_room(fake_home, provider, cred, personal):
    env, home = reviewers.reviewer_env(provider)
    try:
        assert env["HOME"] == home and home != str(fake_home)
        assert os.path.exists(os.path.join(home, cred))
        assert not os.path.exists(os.path.join(home, personal))
        assert not {"ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GH_TOKEN", "GITHUB_TOKEN"} & set(env)
    finally:
        reviewers.cleanup_rev_home(home)
    assert not os.path.exists(home)


def test_cleanup_refuses_foreign_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(reviewers, "REV_HOME_BASE", str(tmp_path / "rev"))
    victim = tmp_path / "rev-important"
    victim.mkdir()
    reviewers.cleanup_rev_home(str(victim))
    assert victim.exists()


FORBIDDEN = {"Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "WebSearch", "Task"}


def test_claude_has_no_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(reviewers, "sh", lambda cmd, **kw: calls.append(cmd) or
                        type("R", (), {"returncode": 0, "stdout": '{"result": "x"}', "stderr": ""})())
    out = reviewers.run_claude("p", ".", "m", {})
    cmd = calls[0]
    tools = cmd[cmd.index("--tools") + 1:cmd.index("--allowedTools")]
    assert set(tools) == set(reviewers.REVIEW_TOOLS) and not FORBIDDEN & set(tools)
    assert out["text"] == "x"


def test_codex_read_only(monkeypatch):
    calls = []
    stdout = '{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n'
    monkeypatch.setattr(reviewers, "sh", lambda cmd, **kw: calls.append(cmd) or
                        type("R", (), {"returncode": 0, "stdout": stdout, "stderr": ""})())
    assert reviewers.run_codex("p", ".", "", {})["text"] == "done"   # "" = no -m
    cmd = calls[0]
    assert cmd[cmd.index("-s") + 1] == "read-only" and "-m" not in cmd


def test_kiro_needs_exact_model():
    for bad in ("", "auto", "Auto-router"):
        with pytest.raises(ValueError):
            reviewers.exact_kiro_model(bad)
    assert reviewers.exact_kiro_model(" gpt-5.6-sol ") == "gpt-5.6-sol"
    assert reviewers.KIRO_TOOLS == "read,grep,glob"


def test_error_kind_ignores_model_prose_on_success():
    talk = {"returncode": 0, "text": "the handler returns 401 when not logged in"}
    assert reviewers.error_kind(talk) == "no_verdict"
    down = {"returncode": 1, "text": "Not logged in · Please run /login"}
    assert reviewers.error_kind(down) == "not_authenticated"
    quota = {"is_error": True, "text": "You've hit your session limit"}
    assert reviewers.error_kind(quota) == "quota_exhausted"


def test_outdated_cli_is_diagnosed():
    res = {"returncode": 1, "is_error": True, "raw_stderr": "",
           "text": "API Error: 400 Claude Code 2.1.81 does not support this model; version 2.1.280 "
                   "or newer is required. Run 'claude update'"}
    assert reviewers.error_kind(res) == "cli_outdated"
    assert "newer is required" in reviewers.failure_summary(res)
    assert reviewers.failure_summary({"returncode": 0, "text": "model prose"}) == ""
    codex = {"returncode": 1, "error_message": '{"detail":"The model requires a newer version of Codex."}'}
    assert reviewers.error_kind(codex) == "cli_outdated"
