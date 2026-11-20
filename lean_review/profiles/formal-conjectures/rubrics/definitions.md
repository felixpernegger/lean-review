# Definitions and their test statements

You judge the definitions the PR introduces or changes. Uses `request_changes`. Whether a
statement using a definition is faithful belongs to the faithfulness angles; whether a definition
duplicates existing material belongs to reuse.

In this repository a definition needs no extensive API: no simp set, no full characteristic
interface. A definition should be **general and useful** in the way a Mathlib definition is, and
**checked by test statements** that show it computes what it should.

## What to check

- **Natural and general.** The definition captures the standard notion at its natural level of
  generality, the one the literature uses, rather than a shape tailored to make one statement easy
  to write. Its arguments have the natural types. A notion that is a special case of an existing
  one is stated through it.
- **Faithful on its own.** It matches the notion it names, including degenerate inputs: 0, 1, the
  empty set, an empty sum, a trivial group. A junk value it can produce (division by zero,
  truncated subtraction, `sInf ∅`, `ncard` of an infinite set) is either harmless where it is used
  or guarded.
- **Test statements.** Each new definition of a sequence, function or predicate comes with
  `@[category test]` statements next to it. They show the first few terms or values (about five for
  a sequence; for OEIS, `a_0`, `a_1`, … matching the b-file, placed right after the definition), a
  degenerate case, and, for a predicate, one input where it holds and one where it fails. Each test
  is proved where feasible, ideally by `decide`, `rfl`, `norm_num` or `simp`. Prefer a computable
  definition, so that tests close by `rfl` or `decide`. Ask for a computable definition when a
  small change gives one. A test left as `sorry` is acceptable only when a proof is out of reach.
  `native_decide` is allowed only in tests, and the PR should say why it is needed.
- **API only where it earns its place.** Ask for a lemma about a definition only when its agreement
  with a standard formulation is not obvious. For example, ask for an `API` statement proving that
  a bespoke encoding is equivalent to the textbook definition.
- **Placement.** A generic definition another problem could use belongs in
  `FormalConjecturesForMathlib/`, at the path Mathlib would use, with its lemmas proved (no
  `sorry`). A definition specific to one problem stays in its problem file. Extensive examples
  belong in the problem file, not in `FormalConjecturesForMathlib/`.
- **No placeholders.** No `def foo : Type := sorry`, `opaque`, or definition whose body is a hole.
  A `….answer := sorry` is not a placeholder.
- **Minimal.** A one-use definition that only names an expression from the statement, and makes it
  no clearer, is better inlined.

## Verdict

- `request_changes` for a definition that is unnatural or tailored, wrong on degenerate inputs,
  missing its test statements (or with tests that do not exercise it), non-computable where a
  computable form is easy, in the wrong place, or a placeholder. Show the test statements or the
  definition you want.
- `approve` when each new definition is natural, placed correctly and exercised by tests, or when
  the PR adds or changes no definitions.
