import pytest

from lean_review import config
from lean_review.config import Config, ConfigError, parse, render_template


def test_defaults():
    cfg = Config()
    assert cfg.mode == "core"
    assert cfg.rubrics == config.DEFAULT_RUBRICS
    assert "scope" not in cfg.rubrics
    for r in cfg.rubrics:
        assert cfg.rubric_text(r)


def test_parse_and_validate():
    cfg = parse('project = "MyLib"\nmode = "scoreboard"\nrubrics = ["correctness"]\nmathlib = false\n')
    assert (cfg.project, cfg.mode, cfg.rubrics, cfg.mathlib) == ("MyLib", "scoreboard", ["correctness"], False)
    for bad in ('mode = "daemon"', 'unknown = 1', 'mathlib = "yes"', 'rubrics = ["Bad Name"]',
                'source_root = "../x"', 'notes = "sneak"'):
        with pytest.raises(ConfigError):
            parse(bad)


def test_scope_rubric_is_gone():
    with pytest.raises(ConfigError):
        Config(rubrics=["scope"]).rubric_text("scope")


def test_overlays_local(tmp_path):
    (tmp_path / ".lean-review.toml").write_text('project = "P"\nrubrics = ["correctness", "house-style"]\n')
    (tmp_path / ".lean-review" / "rubrics").mkdir(parents=True)
    (tmp_path / ".lean-review" / "common.md").write_text("No deprecated aliases.")
    (tmp_path / ".lean-review" / "rubrics" / "house-style.md").write_text("# House style")
    (tmp_path / ".lean-review" / "rubrics" / "correctness.md").write_text("# Replaced")
    cfg = config.load_local(tmp_path / ".lean-review.toml")
    assert cfg.notes == "No deprecated aliases."
    assert cfg.rubric_text("house-style") == "# House style"
    assert cfg.rubric_text("correctness") == "# Replaced"


def test_load_remote_reads_base(monkeypatch):
    seen = []
    files = {".lean-review.toml": 'project = "Remote"\n',
             ".lean-review/common.md": "notes",
             ".lean-review/rubrics": [{"name": "extra.md", "type": "file"},
                                      {"name": "../evil.md", "type": "file"}],
             ".lean-review/rubrics/extra.md": "# Extra"}

    def fake(repo, path, ref):
        seen.append(ref)
        return files.get(path)

    monkeypatch.setattr(config, "_gh_contents", fake)
    cfg = config.load_remote("o/r", "basesha")
    assert cfg.project == "Remote" and cfg.notes == "notes"
    assert cfg.rubric_overrides == {"extra": "# Extra"}
    assert set(seen) == {"basesha"}


def test_template():
    text = "A {{project}}.\n<!-- if namespace -->\nns {{namespace}}\n<!-- end -->\nZ"
    assert render_template(text, {"project": "P", "namespace": "N"}) == "A P.\nns N\nZ"
    assert render_template(text, {"project": "P", "namespace": ""}) == "A P.\nZ"
