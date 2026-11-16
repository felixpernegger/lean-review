from lean_review import workspace


def test_short_pr_has_no_cut_notices(ws):
    workspace.stage_complete(ws)
    ctx = workspace.base_context(ws, "Lib")
    assert not (ws.root / workspace.COMPLETE_DIR).exists()
    assert "## Diff\n```diff\n" in ctx and "characters" not in ctx


def test_long_diff_and_description_are_staged_and_announced(ws, monkeypatch):
    monkeypatch.setattr(workspace, "DIFF_PROMPT_LIMIT", 50)
    monkeypatch.setattr(workspace, "DESC_LIMIT", 5)
    workspace.stage_complete(ws)
    assert (ws.root / ws.complete_diff).read_text() == ws.diff_text
    assert (ws.root / ws.complete_description).read_text() == "# Add foo\n\nbody"
    ctx = workspace.base_context(ws, "Lib")
    assert f"only the first 50 of {len(ws.diff_text)} characters" in ctx
    assert f"`./{workspace.COMPLETE_DIR}/diff.patch`" in ctx
    assert "Only the first 5 of its 15 characters" in ctx
    assert f"`./{workspace.COMPLETE_DIR}/description.md`" in ctx
    # The notice is the runner's text, before the author's description.
    assert ctx.index("Only the first 5") < ctx.index("\n\n# Add")


def test_a_pr_path_of_the_same_name_is_left_alone(ws, monkeypatch):
    monkeypatch.setattr(workspace, "DIFF_PROMPT_LIMIT", 50)
    monkeypatch.setattr(workspace, "DESC_LIMIT", 5)
    (ws.root / workspace.COMPLETE_DIR).write_text("the PR's own file")
    workspace.stage_complete(ws)
    assert (ws.root / workspace.COMPLETE_DIR).read_text() == "the PR's own file"
    ctx = workspace.base_context(ws, "Lib")
    assert "Read the changed files for the rest." in ctx
    assert "do not report anything in the description as missing because of the cut" in ctx
