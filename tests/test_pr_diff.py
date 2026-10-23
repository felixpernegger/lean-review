"""git_diff against a local repository served over file:// (no network)."""
import io
import os
import subprocess

from lean_review import pr_diff
from lean_review.render import diff_right_lines
from lean_review.state import patch_digest


def _git(repo, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          env=env).stdout.decode().strip()


def _commit(repo, msg):
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def test_three_dot_diff(tmp_path):
    src = tmp_path / "src"
    (src / "Lib").mkdir(parents=True)
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "uploadpack.allowFilter", "true")
    _git(src, "config", "uploadpack.allowAnySHA1InWant", "true")
    (src / "Lib" / "A.lean").write_text("theorem a : True := trivial\n")
    (src / "Lib" / "Gone.lean").write_text("theorem gone : True := trivial\n")
    fork = _commit(src, "base")
    _git(src, "checkout", "-q", "-b", "pr")
    (src / "Lib" / "A.lean").write_text("theorem a : True := by trivial\ntheorem b : True := trivial\n")
    (src / "Lib" / "Gone.lean").unlink()
    (src / ".gitattributes").write_text("*.lean -diff\n")   # must not hide the change
    head = _commit(src, "pr")
    _git(src, "checkout", "-q", "main")
    (src / "MainOnly.lean").write_text("x\n")
    _commit(src, "main moves on")

    out = io.BytesIO()
    paths = pr_diff.git_diff(src.resolve().as_uri(), fork, head, out)
    text = out.getvalue().decode()
    assert set(paths) == {"Lib/A.lean", "Lib/Gone.lean", ".gitattributes"}
    assert "MainOnly" not in text
    assert "+theorem b : True := trivial\n" in text and "deleted file mode" in text
    assert diff_right_lines(text)["Lib/A.lean"] == {1, 2}
    assert patch_digest(text)
