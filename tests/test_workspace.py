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


def test_blind_checkouts(tmp_path):
    from lean_review import statements
    from test_statements import ERDOS, new_file_diff
    code = tmp_path / "code"
    (code / "FC").mkdir(parents=True)
    (code / "FC" / "406.lean").write_text(ERDOS)
    (code / "Other.lean").write_text("-- untouched\n")
    (code / ".lake" / "packages" / "mathlib").mkdir(parents=True)
    (code / ".lake" / "packages" / "mathlib" / "M.lean").write_text("/-- doc -/ def m := 1\n")
    (code / workspace.COMPLETE_DIR).mkdir()
    (code / workspace.COMPLETE_DIR / "description.md").write_text("secret prose")
    diff = new_file_diff("FC/406.lean", ERDOS)
    ws = workspace.Workspace(repo="o/r", pr=1, head="h", base="b", merge_base="b", root=code,
                             diff_text=diff, changed=["FC/406.lean"])
    decls = statements.changed_declarations(code, diff, ws.changed)
    workspace.build_blind(ws, decls)
    read = (ws.blind_read / "FC" / "406.lean").read_text()
    assert "Nat.digits 3 n ⊆ [0, 1]" in read and "finitely many" not in read
    assert "erdosproblems" not in read and "Copyright" not in read
    form = (ws.blind_formalize / "FC" / "406.lean").read_text()
    assert "Nat.digits" not in form and "finitely many" not in form
    assert form.count(workspace.REMOVED) == 2 and "erdosproblems.com/406" in form
    for blind in (ws.blind_read, ws.blind_formalize):
        assert not (blind / workspace.COMPLETE_DIR).exists()
        assert (blind / "Other.lean").read_text() == "-- untouched\n"
        assert (blind / ".lake" / "packages" / "mathlib" / "M.lean").is_file()
    # The originals, which the copies hard-link, are untouched.
    assert (code / "FC" / "406.lean").read_text() == ERDOS
    assert (code / workspace.COMPLETE_DIR / "description.md").read_text() == "secret prose"
