# Faithfulness of variants

You judge whether the variant statements named after this rubric say what the mathematics says.
These are variants, special cases, known bounds, textbook ingredients, and main statements beyond
the runner's limit for full reviews. This angle may `block`. Review only the named statements and
the definitions they use.

Before you, a blind step produced a **literal reading** of each statement: another session read the
Lean with every comment and docstring removed, and wrote down what it asserts without knowing what
it is meant to say. It is untrusted model output and may be wrong or missing. Check it against the
code.

## Procedure

For each statement:

1. **The intended statement.** Establish it from the statement's docstring, the source the file
   cites, the main statement it varies, and the PR description.
2. **Round trip.** Check the literal reading against the code, reading every definition used. Then
   list every discrepancy between the reading and the intended statement. **Any difference on an
   edge case is material** unless the source clearly excludes that case: 0, 1, the empty set, a
   degenerate object, strict vs non-strict inequality, an off-by-one, or a constant over ℕ instead
   of the positive reals.
3. **Quick check.** Can every hypothesis be met at once? Does a statement tagged `research open`
   have a short proof? Is a statement tagged `research solved` false on an edge case? Does a known
   bound point in the direction its source states?
4. **Checklist.** Check the statement against the misformalization checklist appended to this
   rubric.

## What to report

Report only material misformalizations and genuine ambiguities. Each finding gives the statement's
file and line, the Lean fragment, the intended reading it departs from, and a witness or an input on
which the two readings differ. The fix is the corrected Lean.

## Verdict

- `block` when a statement differs materially from the intended one and you can give a witness or a
  differing instance.
- `request_changes` for an unstated choice between readings the source admits, or a difference you
  can show only on inputs the source arguably excludes.
- `approve` when every named statement survived every step. Say in the summary what you checked.
