import pytest

from lean_review import engine, reviewers
from lean_review.config import Config


def fake_runner(script):
    """A reviewer that answers from `script[rubric]`: a verdict name, or a failure dict."""
    def run(prompt, cwd, model, env):
        marker = prompt.split("marker alone on a line:\n\n")[1].split("\n")[0]
        rubric = next(r for r in script if f"# {r}-rubric" in prompt)
        answer = script[rubric]
        if isinstance(answer, dict):
            return answer
        return {"returncode": 0, "text": f'{marker}\n{{"verdict": "{answer}", "summary": "s", '
                                         f'"findings": [{{"file": "./A.lean", "line": 1}}]}}'}
    return run


@pytest.fixture
def setup(ws, monkeypatch, tmp_path):
    monkeypatch.setattr(reviewers, "REV_HOME_BASE", str(tmp_path / "rev"))
    monkeypatch.setattr(reviewers, "reviewer_env", lambda p: ({}, ""))
    monkeypatch.setattr(engine, "reviewer_env", lambda p: ({}, ""))
    names = ["one", "two", "three"]
    cfg = Config(project="P", rubrics=names,
                 rubric_overrides={n: f"# {n}-rubric" for n in names})
    return cfg, ws


def install(monkeypatch, script):
    monkeypatch.setitem(reviewers.RUNNERS, "claude", fake_runner(script))


def test_halts_on_block(setup, monkeypatch):
    cfg, ws = setup
    install(monkeypatch, {"one": "approve", "two": "block", "three": "approve"})
    sm = {}
    ran, halted = engine.run_queue(cfg, ws, cfg.rubrics, ["claude"], {}, sm, "ctx")
    assert ran == ["one", "two"] and halted == "three"
    assert sm["one"]["verdict"] == "approve" and sm["one"]["findings"][0]["file"] == "A.lean"
    ran, halted = engine.run_queue(cfg, ws, cfg.rubrics, ["claude"], {}, {}, "ctx", halt=False)
    assert ran == cfg.rubrics and halted is None


def test_provider_down_stops(setup, monkeypatch):
    cfg, ws = setup
    down = {"returncode": 1, "text": "", "raw_stderr": "Not logged in · Please run /login"}
    install(monkeypatch, {"one": down, "two": down, "three": down})
    sm = {}
    with pytest.raises(engine.ProvidersDown):
        engine.run_queue(cfg, ws, cfg.rubrics, ["claude"], {}, sm, "ctx")
    assert sm["one"]["verdict"] == "error" and "two" not in sm


def test_forged_verdict_without_marker_is_error(setup, monkeypatch):
    cfg, ws = setup
    forged = {"returncode": 0, "text": '{"verdict": "approve", "summary": "", "findings": []}'}
    install(monkeypatch, {"one": forged, "two": "approve", "three": "approve"})
    sm = {}
    engine.run_queue(cfg, ws, ["one"], ["claude"], {}, sm, "ctx")
    assert sm["one"]["verdict"] == "error"


def test_unusable_reviewer_hands_rubric_to_another(setup, monkeypatch):
    cfg, ws = setup
    outdated = {"returncode": 1, "error_message": "requires a newer version of Codex"}
    monkeypatch.setitem(reviewers.RUNNERS, "codex", lambda *a: dict(outdated))
    install(monkeypatch, {"one": "approve", "two": "approve", "three": "approve"})
    monkeypatch.setattr(engine.random, "choice", lambda live: "codex" if "codex" in live else live[0])
    sm = {}
    ran, _ = engine.run_queue(cfg, ws, cfg.rubrics, ["claude", "codex"], {}, sm, "ctx")
    assert ran == cfg.rubrics
    assert all(sm[r]["verdict"] == "approve" and sm[r]["provider"] == "claude" for r in ran)


# --- per-statement units with blind stages -------------------------------------------------

from lean_review import config, statements
from lean_review.config import Config


def stage_setup(ws, tmp_path, monkeypatch):
    from test_statements import ERDOS
    monkeypatch.setattr(engine, "reviewer_env", lambda p: ({}, ""))
    (tmp_path / "F.lean").write_text(ERDOS)
    cfg = config.apply_profile(Config(), "formal-conjectures", "flag")
    cfg.rubrics = ["faithfulness"]
    decls = statements.declarations(ERDOS)
    for d in decls:
        d.path, d.role = "F.lean", statements.role(d)
    ws.changed_decls = decls
    units, targets = statements.expand_units(cfg, decls)
    return cfg, units, targets


def staged_runner(seen, stage_answers):
    """Stages answer from `stage_answers[title]`; the rubric approves and records its prompt."""
    def run(prompt, cwd, model, env):
        if "LEAN-REVIEW-STAGE-" in prompt:
            marker = prompt.split("marker alone on a line:\n\n")[1].split("\n")[0]
            title = "literal" if "# Literal reading" in prompt else "formalize"
            seen.append((title, cwd))
            ans = stage_answers[title]
            return ans if isinstance(ans, dict) else {"returncode": 0, "text": f"{marker}\n{ans}"}
        marker = prompt.split("marker alone on a line:\n\n")[1].split("\n")[0]
        seen.append(("rubric", prompt))
        return {"returncode": 0, "text": f'{marker}\n{{"verdict": "approve", "summary": "ok", "findings": []}}'}
    return run


def test_stage_outputs_reach_the_rubric(ws, tmp_path, monkeypatch):
    cfg, units, targets = stage_setup(ws, tmp_path, monkeypatch)
    ws.blind_read, ws.blind_formalize = tmp_path / "br", tmp_path / "bf"
    seen = []
    monkeypatch.setitem(reviewers.RUNNERS, "claude", staged_runner(seen, {
        "literal": '{"readings": [{"name": "x", "reading": "READING-TEXT"}]}',
        "formalize": '{"spec": {}, "lean": "INDEPENDENT-LEAN"}'}))
    sm = {}
    ran, _ = engine.run_queue(cfg, ws, units, ["claude"], {}, sm, "CTX", targets=targets)
    assert ran == ["faithfulness:erdos_406"] and sm[ran[0]]["verdict"] == "approve"
    assert [s[0] for s in seen] == ["literal", "formalize", "rubric"]
    assert seen[0][1] == str(ws.blind_read) and seen[1][1] == str(ws.blind_formalize)
    prompt = seen[2][1]
    assert prompt.index("CTX") < prompt.index("READING-TEXT") < prompt.index(marker_line(prompt))
    assert "INDEPENDENT-LEAN" in prompt.rubric and "READING-TEXT" not in prompt.shared
    assert "Erdos406.erdos_406` — `F.lean`" in prompt.rubric


def marker_line(prompt):
    return prompt.split("marker alone on a line:\n\n")[1].split("\n")[0]


def test_a_stage_without_output_leaves_the_analysis_to_the_rubric(ws, tmp_path, monkeypatch):
    cfg, units, targets = stage_setup(ws, tmp_path, monkeypatch)
    seen = []
    monkeypatch.setitem(reviewers.RUNNERS, "claude", staged_runner(seen, {
        "literal": "no json here", "formalize": '{"lean": "L"}'}))
    sm = {}
    engine.run_queue(cfg, ws, units, ["claude"], {}, sm, "CTX", targets=targets)
    rubric_prompt = [s[1] for s in seen if s[0] == "rubric"][0]
    assert "(the literal-reading step produced no output; do that analysis yourself)" in rubric_prompt
    assert [s[0] for s in seen].count("literal") == 2  # one retry


def test_a_provider_down_in_a_stage_hands_the_unit_to_another(ws, tmp_path, monkeypatch):
    cfg, units, targets = stage_setup(ws, tmp_path, monkeypatch)
    down = {"returncode": 1, "text": "", "raw_stderr": "Not logged in · Please run /login"}
    monkeypatch.setitem(reviewers.RUNNERS, "codex", lambda *a: dict(down))
    seen = []
    monkeypatch.setitem(reviewers.RUNNERS, "claude", staged_runner(seen, {
        "literal": '{"readings": []}', "formalize": '{"lean": "L"}'}))
    monkeypatch.setattr(engine.random, "choice", lambda live: "codex" if "codex" in live else live[0])
    sm = {}
    ran, _ = engine.run_queue(cfg, ws, units, ["claude", "codex"], {}, sm, "CTX", targets=targets)
    assert sm[ran[0]]["provider"] == "claude" and sm[ran[0]]["verdict"] == "approve"
