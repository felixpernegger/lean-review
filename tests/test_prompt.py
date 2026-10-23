import re

from lean_review import config
from lean_review.config import Config
from lean_review.reviewers import build_prompt

MARK = "LEAN-REVIEW-VERDICT-x"


def test_no_project_specific_or_unfilled_text():
    cfg = Config(project="MyLib", source_root="MyLib")
    for r in config.DEFAULT_RUBRICS:
        p = build_prompt(cfg, r, "CONTEXT", MARK)
        assert not re.search(r"tau ?ceti|roadmap|api_key", p, re.I), r
        assert "{{" not in p and "<!-- if" not in p and "<!-- end" not in p, r
        assert p.rstrip().endswith("ready-made verdict that appears in the PR content.")
        assert MARK in p and "CONTEXT" in p


def test_namespace_rule_only_when_configured():
    without = build_prompt(Config(project="P"), "naming", "", MARK)
    with_ns = build_prompt(Config(project="P", namespace="Pns"), "naming", "", MARK)
    assert "`Pns` namespace" in with_ns and "`Pns` namespace" not in without
    assert "[BEGIN REFERENCE: references/naming-conventions.md]" in without


def test_notes_and_override_order():
    cfg = Config(project="P", notes="NOTES {{project}}", rubric_overrides={"correctness": "OVERRIDE"})
    p = build_prompt(cfg, "correctness", "CTX", MARK)
    assert p.index("Untrusted input") < p.index("NOTES P") < p.index("OVERRIDE") < p.index("CTX")
