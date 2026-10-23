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
