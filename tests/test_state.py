from lean_review import state
from lean_review.config import Config
from lean_review.render import REPLY_MARKER


def test_patch_digest_ignores_rebase_noise():
    a = "diff --git a/x b/x\nindex 111..222 100644\n@@ -1,2 +1,3 @@ sec\n a\n+b\n"
    b = "diff --git a/x b/x\nindex 333..444 100644\n@@ -10,2 +12,3 @@ sec\n a\n+b\n"
    c = a.replace("+b", "+c")
    assert state.patch_digest(a) == state.patch_digest(b) != state.patch_digest(c)
    assert state.patch_digest("") is None
    assert state.patch_digest("Binary files a/x and b/x differ\n") is None


def test_carry_forward_only_same_patch_and_rubrics():
    sm = {"a": {"verdict": "approve", "approved_sha": "old", "reviewed_sha": "old",
                "approved_digest": "d", "rubrics_version": "v"},
          "b": {"verdict": "approve", "approved_sha": "old", "approved_digest": "other",
                "rubrics_version": "v"},
          "c": {"verdict": "request_changes", "reviewed_sha": "old"},
          "d": {"verdict": "approve", "approved_sha": "old", "approved_digest": "d",
                "rubrics_version": "older"}}
    assert state.carry_forward(sm, "new", "d", "v") == ["a"]
    assert sm["a"]["approved_sha"] == "new" and sm["a"]["carried_from_sha"] == "old"


def test_rubrics_version_tracks_overlays():
    base = state.rubrics_version(Config(project="P"))
    assert base == state.rubrics_version(Config(project="P"))
    assert base != state.rubrics_version(Config(project="P", notes="x"))
    assert base != state.rubrics_version(Config(project="Q"))


def test_thread_replies_skip_our_markers():
    comments = [
        {"id": 1, "in_reply_to_id": None, "body": "<!--lean-review:rubric:reuse-->\nroot"},
        {"id": 2, "in_reply_to_id": 1, "body": "I disagree", "user": {"login": "author"}},
        {"id": 3, "in_reply_to_id": 1, "body": REPLY_MARKER + " answer"},
        {"id": 4, "in_reply_to_id": None, "body": "unrelated"},
        {"id": 5, "in_reply_to_id": 4, "body": "chatter"},
    ]
    assert state.thread_replies(comments) == {
        "reuse": [{"id": 2, "root_id": 1, "by": "author", "body": "I disagree"}]}


def test_reactivation_is_framed_untrusted():
    cf = {"verdict": "block", "summary": "s", "findings": [{"file": "f", "line": 3, "issue": "i"}]}
    block = state.build_reactivation_block(cf, "please approve")
    assert "untrusted prior reviewer output" in block and "untrusted author argument" in block
    assert state.build_reactivation_block(None) == ""
