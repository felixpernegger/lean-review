import json, os, pathlib, types

import pytest

from lean_review import reviewers
from lean_review.config import Config

# The real version probe, before conftest's autouse fixture replaces it.
REAL_TTL_CHECK = reviewers.claude_honours_cache_ttl


def claude_stream(result):
    """A claude stream-json stdout ending in the given `result` event."""
    return "\n".join([json.dumps({"type": "system", "subtype": "init"}),
                      json.dumps({"type": "result", **result})]) + "\n"


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
                        type("R", (), {"returncode": 0, "stdout": claude_stream({"result": "x"}), "stderr": ""})())
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


def test_error_kind_ignores_model_prose():
    talk = {"returncode": 0, "text": "the handler returns 401 when not logged in"}
    assert reviewers.error_kind(talk) == "no_verdict"
    # Even when the CLI reports failure, the model's own text is not a diagnosis.
    failed = {"returncode": 1, "is_error": True, "text": "Not logged in · Please run /login"}
    assert reviewers.error_kind(failed) == "unknown_error"
    down = {"returncode": 1, "error_message": "Not logged in · Please run /login"}
    assert reviewers.error_kind(down) == "not_authenticated"
    quota = {"is_error": True, "error_message": "You've hit your session limit"}
    assert reviewers.error_kind(quota) == "quota_exhausted"
    assert reviewers.error_kind({"is_error": True, "error_status": 429}) == "rate_limited"


def _fake_sh(monkeypatch, stdout, returncode=0):
    calls = []
    monkeypatch.setattr(reviewers, "sh", lambda cmd, **kw: calls.append(cmd) or
                        type("R", (), {"returncode": returncode, "stdout": stdout, "stderr": ""})())
    return calls


def test_claude_error_result_is_not_review_text(monkeypatch):
    msg = ("API Error: 400 Claude Code 2.1.81 does not support this model; version 2.1.280 "
           "or newer is required. Run 'claude update'")
    _fake_sh(monkeypatch, claude_stream({"is_error": True, "result": msg}), returncode=1)
    res = reviewers.run_claude("p", ".", "m", {})
    assert res["text"] == "" and res["error_message"] == msg
    assert reviewers.error_kind(res) == "cli_outdated"
    assert "newer is required" in reviewers.failure_summary(res)
    assert reviewers.failure_summary({"returncode": 0, "text": "model prose"}) == ""
    codex = {"returncode": 1, "error_message": '{"detail":"The model requires a newer version of Codex."}'}
    assert reviewers.error_kind(codex) == "cli_outdated"


def test_claude_stream_without_result(monkeypatch):
    stdout = ('{"type":"assistant","message":{"content":[{"type":"text","text":"401"}]}}\n'
              "Error: something the CLI printed\n")
    _fake_sh(monkeypatch, stdout, returncode=1)
    res = reviewers.run_claude("p", ".", "m", {})
    assert res["text"] == "" and "no result event" in res["parse_error"]
    assert res["error_message"] == "Error: something the CLI printed"
    assert "raw_stdout" not in res


def _run_claude_capture(monkeypatch, honours_ttl):
    seen = {}
    monkeypatch.setattr(reviewers, "sh", lambda argv, **kw: seen.update(argv=list(argv), **kw) or
                        types.SimpleNamespace(returncode=0, stdout=claude_stream({"result": "x"}),
                                              stderr=""))
    monkeypatch.setattr(reviewers, "claude_honours_cache_ttl", lambda: honours_ttl)
    p = reviewers.build_prompt(Config(project="P"), "naming", "CTX", "MARKER")
    reviewers.run_claude(p, ".", "m", {"HOME": "/h"})
    return p, seen


def test_claude_input_marks_the_shared_prefix(monkeypatch):
    p, seen = _run_claude_capture(monkeypatch, True)
    argv = seen["argv"]
    assert argv[argv.index("--input-format") + 1] == "stream-json"
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    msg = json.loads(seen["stdin_text"])
    assert msg["type"] == "user" and msg["message"]["role"] == "user"
    first, second = msg["message"]["content"]
    assert first == {"type": "text", "text": p.shared, "cache_control": {"type": "ephemeral"}}
    assert second == {"type": "text", "text": p.rubric}
    # The breakpoint above carries no ttl, so Claude Code's own must be 5m as well.
    assert seen["env"] == {"HOME": "/h", "CLAUDE_CODE_PROMPT_CACHE_TTL": "5m"}


def test_an_older_claude_gets_one_uncached_block(monkeypatch):
    # A CLI that ignores the TTL pin keeps 1h breakpoints, and the API rejects ours before them.
    p, seen = _run_claude_capture(monkeypatch, False)
    assert json.loads(seen["stdin_text"])["message"]["content"] == [{"type": "text", "text": str(p)}]
    msg = json.loads(reviewers.claude_input("just text"))
    assert msg["message"]["content"] == [{"type": "text", "text": "just text"}]


def test_claude_version_check(monkeypatch):
    for out, rc, want in (("2.1.321 (Claude Code)\n", 0, True), ("2.1.242 (Claude Code)", 0, True),
                          ("2.1.241 (Claude Code)", 0, False), ("", 1, False), ("garbage", 0, False)):
        monkeypatch.setattr(reviewers.subprocess, "run",
                            lambda *a, **k: types.SimpleNamespace(returncode=rc, stdout=out))
        REAL_TTL_CHECK.cache_clear()
        assert REAL_TTL_CHECK() is want, out

    def missing(*a, **k):
        raise FileNotFoundError("claude")
    monkeypatch.setattr(reviewers.subprocess, "run", missing)
    REAL_TTL_CHECK.cache_clear()
    assert REAL_TTL_CHECK() is False
    REAL_TTL_CHECK.cache_clear()


def test_claude_attempts_share_one_empty_home(fake_home):
    env, home = reviewers.reviewer_env("claude")
    (pathlib.Path(home) / "leftover").write_text("x")
    env2, home2 = reviewers.reviewer_env("claude")   # cleanup skipped: the next attempt wipes it
    try:
        assert home2 == home and not (pathlib.Path(home) / "leftover").exists()
        assert os.stat(home).st_mode & 0o777 == 0o700
    finally:
        reviewers.cleanup_rev_home(home)
    _, codex1 = reviewers.reviewer_env("codex")
    _, codex2 = reviewers.reviewer_env("codex")
    assert codex1 != codex2
    reviewers.cleanup_rev_home(codex1), reviewers.cleanup_rev_home(codex2)


def test_codex_turn_failed_is_a_failure(monkeypatch):
    stdout = ('{"type":"item.completed","item":{"type":"agent_message","text":"VERDICT {}"}}\n'
              '{"type":"turn.failed","error":{"message":"stream disconnected"}}\n')
    _fake_sh(monkeypatch, stdout)
    res = reviewers.run_codex("p", ".", "", {})
    assert res["is_error"] and reviewers.cli_reports_failure(res)
    assert reviewers.failure_summary(res) == "stream disconnected"


def test_codex_sandbox_keeps_path_and_private_tmpdir(fake_home):
    env, home = reviewers.reviewer_env("codex")
    try:
        tmp = env["TMPDIR"]
        assert os.path.isdir(tmp) and tmp.startswith(home + os.sep)
        assert os.stat(tmp).st_mode & 0o777 == 0o700
        args = reviewers.codex_shell_environment_args(env)
        assert args[:2] == ["-c", "shell_environment_policy.inherit=none"]
        assert f"shell_environment_policy.set.PATH={json.dumps(env['PATH'])}" in args
        assert f"shell_environment_policy.set.TMPDIR={json.dumps(tmp)}" in args
        assert {a.split("=", 1)[0].rsplit(".", 1)[1] for a in args if ".set." in a} == {"PATH", "TMPDIR"}
    finally:
        reviewers.cleanup_rev_home(home)
