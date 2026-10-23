import pytest

from lean_review import cli, reviewers
from lean_review.config import Config

H = "h" * 40


def test_scoreboard_queue():
    cfg = Config(rubrics=["green", "stale", "judged", "contested", "errored", "new"])
    sm = {"green": {"verdict": "approve", "approved_sha": H},
          "stale": {"verdict": "approve", "approved_sha": "old"},
          "judged": {"verdict": "request_changes", "reviewed_sha": H},
          "contested": {"verdict": "request_changes", "reviewed_sha": H,
                        "author_replies": [{"id": 9}], "last_reply_seen": 3},
          "errored": {"verdict": "error", "reviewed_sha": H}}
    assert cli.select_scoreboard_queue(cfg, sm, H, False) == ["stale", "contested", "errored", "new"]
    assert cli.select_scoreboard_queue(cfg, sm, H, True) == cfg.rubrics


def test_halt_defaults_by_mode():
    def args(*argv):
        return cli.parse_args(["1", *argv])
    assert cli.should_halt(args(), Config(mode="core")) is False
    assert cli.should_halt(args(), Config(mode="scoreboard")) is True
    assert cli.should_halt(args("--halt"), Config(mode="core")) is True
    assert cli.should_halt(args("--no-halt"), Config(mode="scoreboard")) is False
    with pytest.raises(SystemExit):
        args("--halt", "--no-halt")


def test_pick_providers(monkeypatch):
    monkeypatch.setattr(reviewers, "available", lambda: ["claude", "kiro"])
    assert cli.pick_providers(None) == ["claude"]             # kiro is never auto-drawn
    assert cli.pick_providers("kiro") == ["kiro"]
    with pytest.raises(SystemExit):
        cli.pick_providers("codex")
    with pytest.raises(SystemExit):
        cli.pick_providers("deepseek")


def test_publish_core_conditions(monkeypatch, ws):
    from lean_review import post
    calls = []
    monkeypatch.setattr(post, "current_login", lambda: "me")
    monkeypatch.setattr(post, "post_review", lambda *a: calls.append(a) or {"html_url": "u"})
    monkeypatch.setattr(post, "find_own_review", lambda *a: None)
    args = lambda *argv: cli.parse_args(["7", *argv])
    assert cli.publish_core(args(), "o/r", ws, "B", [], "blocked") is False            # dry run
    assert cli.publish_core(args("--post-unless-approved"), "o/r", ws, "B", [], "approved") is False
    assert cli.publish_core(args("--post-unless-approved"), "o/r", ws, "B", [], "blocked") is True
    monkeypatch.setattr(post, "find_own_review", lambda *a: "u-earlier")
    assert cli.publish_core(args("--post"), "o/r", ws, "B", [], "blocked") is False   # duplicate
    assert cli.publish_core(args("--post", "--repost"), "o/r", ws, "B", [], "blocked") is True
    assert len(calls) == 2
    with pytest.raises(SystemExit):
        args("--post", "--post-unless-approved")
