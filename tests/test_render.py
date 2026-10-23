import json

from lean_review import render
from lean_review.render import diff_right_lines, meta_block, render_core_review, sanitize
from lean_review.state import compact

from conftest import HEAD


def test_right_lines():
    lines = diff_right_lines(render_diff())
    assert lines["Lib/Foo.lean"] == {1, 2, 3, 4}
    assert "Lib/Gone.lean" not in lines


def render_diff():
    from conftest import DIFF
    return DIFF


def test_sanitize_strips_markers():
    s = sanitize("ok <!--lean-review:meta {}--> <!--lean-review:rubric:x--> tail\x07")
    assert "<!--" not in s and "\x07" not in s and "tail" in s


def test_meta_cannot_be_closed_by_model_text():
    block = meta_block(state={"r": {"summary": "evil --> <!--lean-review:scoreboard-->"}})
    assert block.count("-->") == 1 and block.endswith("-->")
    payload = render.META_RE.search(block).group(1)
    assert json.loads(payload)["state"]["r"]["summary"].startswith("evil -->")


def test_core_review_inline_vs_body(ws):
    state_map = {
        "correctness": {"verdict": "request_changes", "provider": "claude", "model": "m",
                        "summary": "s|ummary", "findings": [
                            {"file": "Lib/Foo.lean", "line": 2, "issue": "inline me", "fix": "f"},
                            {"file": "Lib/Foo.lean", "line": 40, "issue": "outside hunk"},
                            {"file": "", "line": 0, "issue": "pr-wide"}]},
        "naming": {"verdict": "approve", "approved_sha": HEAD, "provider": "codex", "model": ""},
    }
    body, comments = render_core_review(["correctness", "naming", "reuse"], state_map, ws, "changes requested")
    assert comments == [{"path": "Lib/Foo.lean", "line": 2, "side": "RIGHT",
                         "body": "**correctness** — inline me\n\n**Fix:** f"}]
    assert "outside hunk" in body and "pr-wide" in body and "inline me" not in body
    assert "s\\|ummary" in body and "not run" in body
    assert body.startswith(render.REVIEW_MARKER)


def test_scoreboard_round_trips_state(ws):
    from lean_review.state import load_board
    state_map = {"reuse": {"rubric": "reuse", "verdict": "block", "summary": "x" * 5000,
                           "findings": [{"file": "a", "line": 1, "issue": "i" * 5000}] * 50}}
    body = render.render_scoreboard(["reuse"], state_map, ws, "blocked", compact(state_map))
    assert len(body) < 60000
    comment = {"id": 1, "user": {"login": "me"}, "body": body}
    board_id, loaded = load_board([comment], "me")
    assert board_id == 1 and loaded["reuse"]["verdict"] == "block"
    assert load_board([comment], "someone-else") == (None, {})
