import pathlib

from lean_review import config, statements
from lean_review.config import Config

ERDOS = '''/-
Copyright 2025 The Formal Conjectures Authors.
-/
module

public import FormalConjecturesUtil

/-!
# Erdős Problem 406

*Reference:* [erdosproblems.com/406](https://www.erdosproblems.com/406)
-/

@[expose] public section

namespace Erdos406

/--
Is it true that there are only finitely many powers of $2$ which have only the digits $0$
and $1$ when written in base $3$?
-/
@[category research open, question, AMS 11]
theorem erdos_406 : { n | n.isPowerOfTwo ∧ Nat.digits 3 n ⊆ [0, 1] }.Finite := by
  sorry

/--
If we only allow the digits $1$ and $2$ then $2^{15}$ seems to be the largest such power
of $2$.
-/
@[category research open, AMS 11]
theorem erdos_406.variants.one_two :
    IsGreatest { n | n.isPowerOfTwo ∧ Nat.digits 3 n ⊆ [1, 2] } (2 ^ 15) := by
  sorry

end Erdos406
'''

JUGGLER = '''module

public import FormalConjecturesUtil

/-!
# Juggler conjecture

*Reference:* [Wikipedia](https://en.wikipedia.org/wiki/Juggler_sequence)
-/

@[expose] public section

namespace JugglerConjecture

/--
If the number is even, take the floor of the square root -- not a comment.
theorem fake : False
-/
noncomputable def jugglerStep (n : ℕ) : ℕ :=
  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊

/-- The **Juggler Conjecture**: every positive start reaches $1$. -/
@[category research open, AMS 11 37]
theorem juggler_conjecture (n : ℕ) (hn : n > 0) : ∃ m, jugglerStep^[m] n = 1 := by
  sorry

/-- Example: jugglerStep 36 = 6. -/
@[category test, AMS 11]
theorem jugglerStep_36 : jugglerStep 36 = 6 := by
  unfold jugglerStep
  norm_num [←Real.sqrt_eq_rpow]

end JugglerConjecture
'''

VALUE = '''namespace HadwigerNelson

def hadwiger_nelson.answer : ℕ := sorry

/-- What is the chromatic number of the plane? -/
@[category research open, question value, AMS 5]
theorem hadwiger_nelson : UnitDistancePlaneGraph.chromaticNumber = hadwiger_nelson.answer := by
  sorry

end HadwigerNelson
'''


def new_file_diff(path, text):
    lines = text.rstrip("\n").split("\n")
    return (f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n"
            f"@@ -0,0 +1,{len(lines)} @@\n" + "".join(f"+{l}\n" for l in lines))


def write(root, path, text):
    f = root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text)


def fc_cfg(**kw):
    cfg = config.apply_profile(Config(), "formal-conjectures", "flag")
    for k, v in kw.items():
        setattr(cfg, k, v)
    return cfg


def test_strip_comments_handles_nesting_strings_and_chars():
    src = 'def a := "-- kept /- kept -/" -- gone\n/- outer /- inner -/ still -/\ndef b := \'"\' -- x\n'
    out = statements.strip_comments(src)
    assert '"-- kept /- kept -/"' in out and "gone" not in out and "inner" not in out
    assert "still" not in out and "def b := '\"'" in out and "x" not in out.split("def b")[1]


def test_declarations_of_an_erdos_file():
    ds = statements.declarations(ERDOS)
    assert [(d.kind, d.name, statements.role(d)) for d in ds] == [
        ("theorem", "Erdos406.erdos_406", "main"),
        ("theorem", "Erdos406.erdos_406.variants.one_two", "variant")]
    main = ds[0]
    assert main.category == "research open" and main.question == "yes/no"
    assert main.docstring.startswith("Is it true") and main.code.startswith("/--")
    assert main.code.rstrip().endswith("sorry") and "one_two" not in main.code
    assert ds[1].question == "" and ds[1].attributes == "category research open"
    assert "erdosproblems.com/406" in statements.module_docstring(ERDOS)


def test_keywords_inside_a_docstring_do_not_start_declarations():
    ds = statements.declarations(JUGGLER)
    assert [(d.short, statements.role(d)) for d in ds] == [
        ("jugglerStep", "definition"), ("juggler_conjecture", "main"), ("jugglerStep_36", "test")]
    assert "theorem fake" in ds[0].docstring


def test_value_questions_and_answers():
    ds = statements.declarations(VALUE)
    assert [statements.role(d) for d in ds] == ["answer", "main"]
    assert ds[1].question == "value" and ds[1].attributes == "category research open, question value"


def test_inline_attributes_on_the_keyword_line():
    ds = statements.declarations("@[category test, AMS 11] theorem t : 1 = 1 := rfl\n")
    assert ds[0].short == "t" and ds[0].category == "test"


def test_changed_declarations_new_and_modified(tmp_path):
    write(tmp_path, "FC/406.lean", ERDOS)
    ds = statements.changed_declarations(tmp_path, new_file_diff("FC/406.lean", ERDOS),
                                         ["FC/406.lean"])
    assert [(d.short, d.status) for d in ds] == [("erdos_406", "new"),
                                                 ("erdos_406.variants.one_two", "new")]
    line = ERDOS.split("\n").index("    IsGreatest { n | n.isPowerOfTwo ∧ Nat.digits 3 n ⊆ [1, 2] } (2 ^ 15) := by") + 1
    diff = (f"diff --git a/FC/406.lean b/FC/406.lean\n--- a/FC/406.lean\n+++ b/FC/406.lean\n"
            f"@@ -{line},1 +{line},1 @@\n-    old\n+    new\n")
    ds = statements.changed_declarations(tmp_path, diff, ["FC/406.lean"])
    assert [(d.short, d.status) for d in ds] == [("erdos_406.variants.one_two", "modified")]


def test_a_statement_using_a_changed_definition_counts_as_changed(tmp_path):
    write(tmp_path, "FC/J.lean", JUGGLER)
    line = JUGGLER.split("\n").index("  if Even n then ⌊(n : ℝ) ^ (1/2 : ℝ)⌋₊ else ⌊(n : ℝ) ^ (3/2 : ℝ)⌋₊") + 1
    diff = (f"diff --git a/FC/J.lean b/FC/J.lean\n--- a/FC/J.lean\n+++ b/FC/J.lean\n"
            f"@@ -{line},1 +{line},1 @@\n-  old\n+  new\n")
    ds = statements.changed_declarations(tmp_path, diff, ["FC/J.lean"])
    assert [(d.short, d.role) for d in ds] == [("jugglerStep", "definition"),
                                               ("juggler_conjecture", "main")]
    assert ds[1].status == "uses changed `jugglerStep`"


def test_context_lines_and_deleted_files_do_not_count():
    diff = ("diff --git a/A.lean b/A.lean\n--- a/A.lean\n+++ b/A.lean\n@@ -1,2 +1,3 @@\n"
            " ctx\n+added\n ctx\ndiff --git a/B.lean b/B.lean\n--- a/B.lean\n+++ /dev/null\n"
            "@@ -1 +0,0 @@\n-gone\n")
    assert statements.added_lines(diff) == {"A.lean": {2}}


def decl(short, role, path="F.lean"):
    return statements.Decl(kind="theorem", short=short, name=short, start=1, end=2, code="",
                           role=role, path=path)


def test_expand_units_caps_full_checks_and_chunks_variants():
    logs = []
    mains = [decl(f"m{i}", "main") for i in range(3)]
    variants = [decl(f"v{i}", "variant") for i in range(6)]
    units, targets = statements.expand_units(fc_cfg(full_checks=2), mains + variants, logs.append)
    assert units[:4] == ["faithfulness:m0", "faithfulness:m1", "variant-faithfulness:1",
                         "variant-faithfulness:2"]
    assert units[4:] == ["reuse", "definitions", "completeness", "metadata", "documentation",
                         "proof-quality"]
    assert [d.short for d in targets["variant-faithfulness:1"]] == ["m2", "v0", "v1", "v2", "v3", "v4"]
    assert [d.short for d in targets["variant-faithfulness:2"]] == ["v5"]
    assert any("beyond full_checks=2" in m for m in logs)


def test_expand_units_skips_expanding_rubrics_with_nothing_to_review():
    logs = []
    units, targets = statements.expand_units(fc_cfg(), [decl("d", "definition")], logs.append)
    assert units[0] == "reuse" and targets == {}
    assert "[faithfulness] no changed main statement; skipped" in logs


def test_unit_keys_are_safe_and_unique():
    evil = decl("x«-->»<b>", "main")
    twin_a, twin_b = decl("conjecture", "main", "OEIS/1.lean"), decl("conjecture", "main", "OEIS/2.lean")
    units, _ = statements.expand_units(fc_cfg(rubrics=["faithfulness"]), [evil, twin_a, twin_b])
    assert all("-" not in u.split(":", 1)[1] and "<" not in u for u in units)
    assert len(set(units)) == 3
    assert statements.unit_rubric(units[0]) == "faithfulness"
    assert statements.unit_label("faithfulness:erdos_1") == "faithfulness · erdos_1"


def test_plain_profile_does_not_expand():
    units, targets = statements.expand_units(Config(rubrics=["correctness"]), [decl("m", "main")])
    assert units == ["correctness"] and targets == {}


def test_junk_hints():
    assert "division: rounds down on ℕ/ℤ, and x / 0 = 0" in statements.junk_hints("theorem t : (1 : ℕ) / 0 = 0")
    assert statements.junk_hints("theorem t : True -- a / b") == []
