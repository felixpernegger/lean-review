from lean_review import post
from lean_review.render import BOARD_MARKER


class FakeGH:
    def __init__(self, fail=()):
        self.calls, self.fail = [], set(fail)

    def __call__(self, method, endpoint, payload=None, failures=None, action=""):
        self.calls.append((method, endpoint, payload))
        if (method, endpoint) in self.fail or (method in self.fail and payload and payload.get("comments")):
            if failures is not None:
                failures.append(action)
            return None
        return {"id": 99, "html_url": "u"}


def board(id_, login, ts):
    return {"id": id_, "user": {"login": login}, "updated_at": ts, "body": BOARD_MARKER + " x"}


def test_scoreboard_edits_ours_and_collapses_dupes(monkeypatch):
    gh = FakeGH()
    monkeypatch.setattr(post, "gh_api", gh)
    monkeypatch.setattr(post, "gh_paginate", lambda e: [board(1, "me", "1"), board(2, "me", "2"),
                                                        board(3, "mallory", "3")])
    assert post.upsert_scoreboard("o/r", 7, "B", None, "me", []) == 2
    assert ("PATCH", "/repos/o/r/issues/comments/2", {"body": "B"}) in gh.calls
    assert ("DELETE", "/repos/o/r/issues/comments/1", None) in gh.calls
    assert not any("/3" in c[1] for c in gh.calls)        # never touches a foreign comment


def test_scoreboard_creates_when_none_ours(monkeypatch):
    gh = FakeGH()
    monkeypatch.setattr(post, "gh_api", gh)
    monkeypatch.setattr(post, "gh_paginate", lambda e: [board(3, "mallory", "3")])
    assert post.upsert_scoreboard("o/r", 7, "B", 3, "me", []) == 99
    assert [c[0] for c in gh.calls] == ["POST"]


def test_review_falls_back_without_inline(monkeypatch):
    gh = FakeGH(fail={"POST"})
    monkeypatch.setattr(post, "gh_api", gh)
    failures = []
    resp = post.post_review("o/r", 7, "h", "BODY", [{"path": "p", "line": 3, "body": "c"}], failures)
    assert resp == {"id": 99, "html_url": "u"} and failures == []
    assert gh.calls[0][2]["comments"] and gh.calls[0][2]["event"] == "COMMENT"
    assert gh.calls[1][2]["comments"] == [] and "`p:3` — c" in gh.calls[1][2]["body"]


def test_find_own_review_matches_head_and_author(monkeypatch):
    from lean_review.render import REVIEW_MARKER, meta_block
    def review(login, head, url):
        return {"user": {"login": login}, "html_url": url,
                "body": f"{REVIEW_MARKER}\nbody\n{meta_block(kind='review', head_sha=head)}"}
    reviews = [review("me", "old", "u-old"), review("me", "h", "u-mine"),
               review("mallory", "h", "u-foreign"),
               {"user": {"login": "me"}, "html_url": "u-plain", "body": "a human review"}]
    monkeypatch.setattr(post, "gh_paginate", lambda e: reviews)
    assert post.find_own_review("o/r", 1, "h", "me") == "u-mine"
    assert post.find_own_review("o/r", 1, "new", "me") is None
    assert post.find_own_review("o/r", 1, "h", "nobody") is None
