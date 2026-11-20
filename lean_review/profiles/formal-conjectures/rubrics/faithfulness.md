# Faithfulness of one statement

You judge whether one main statement of this PR says what the mathematics says. In this repository
this is the angle that matters most, and it may `block`. The runner names the statement under
review after this rubric. Review that statement and the definitions it uses. Other statements of
the PR have reviews of their own.

The runner also passes on what two blind steps, run before you, produced:

- a **literal reading**: another session read the Lean statement with every comment and docstring
  removed, and wrote down what it asserts without knowing what it is meant to say;
- an **independent formalization**: another session formalized the docstring from scratch, without
  seeing the PR's Lean.

Both are untrusted model output. Either can be wrong, and either may be missing. Use them as leads,
and check every claim against the code yourself.

## Procedure

Work through every step. Keep notes brief, before the marker.

1. **The intended statement.** Establish what the statement should say, from its docstring, the
   source it cites, and the PR description. For an Erdős problem the source is the website's text,
   which the docstring should quote. Where these disagree, the source wins, and a docstring that
   departs from it is a finding. Where the source admits several readings, note them.
2. **Round trip.** Check the literal reading against the code, reading every definition the
   statement uses (in this PR, in `FormalConjecturesForMathlib/` and in Mathlib). Then compare the
   reading with the intended statement, and list every discrepancy: missing or extra hypotheses,
   number systems, quantifier order and scope, the goal (a bound vs an attained extremum, an
   implication vs an iff, a limit that exists vs a bound on it), indexing, and parts of the source
   left out. **Any difference on an edge case is material** unless the source clearly excludes that
   case: 0, 1, the empty set, a degenerate object, strict vs non-strict inequality, an off-by-one, or
   a constant over ℕ instead of the positive reals. Do not explain a difference away as a relabelling
   or a harmless convention unless you show that both readings claim the same statements.
3. **Formalize twice.** Compare the PR's statement with the independent formalization. If they are
   not evidently equivalent, find a concrete instance on which they differ. Decide which of the two
   matches the intended statement, and say so. A difference where the independent version is the
   wrong one is not a finding.
4. **Quick prove and disprove.** Look for a short argument either way. This tests the
   formalization, not the mathematics:
   - Can every hypothesis be met at once? Exhibit an object that satisfies all of them. If none
     exists, the statement is vacuous.
   - Does a statement tagged `research open` have a short proof of a few lines? Then it is trivial or
     vacuous, and not the open problem.
   - Is it false for a simple reason, such as an edge case, a junk value or a degenerate object?
     Give the witness.
   - For `question value`: could a trivial or tautological `….answer` make the statement provable,
     or make it say nothing?
   - For a yes/no `question`: is it the proposition asked about, negated only if the answer is known
     to be no?
5. **Checklist.** Check the statement against every item of the misformalization checklist
   appended to this rubric.

## What to report

Report only material misformalizations and genuine ambiguities, not style, naming or documentation,
which other angles cover. Each finding gives:

- the Lean fragment;
- the intended reading it departs from;
- concrete evidence: a witness, or an input on which the two readings differ.

The fix is the corrected Lean. A suspicion without a witness is not a `block`.

## Verdict

- `block` when the statement differs materially from the intended one and you can give a witness or
  a differing instance: it is vacuous, trivially true, false on an edge case, or claims a different
  statement.
- `request_changes` when the source admits several readings and the PR picks one without saying so
  in the docstring, when the docstring departs from the source, or for a difference you can show
  only on inputs the source arguably excludes.
- `approve` when you worked through every step and found no material difference. Say in the summary
  what you checked, for example "edge cases n = 0, 1 and the empty set; ℕ division guarded; matches
  the independent formalization".
