# The formal-conjectures profile

For [formal-conjectures](https://github.com/google-deepmind/formal-conjectures) and repositories
laid out like it: Lean statements of open conjectures and known results, whose proofs are `sorry`
by design. It is selected with `--profile formal-conjectures`, with `profile = "formal-conjectures"`
in `.lean-review.toml`, or automatically when the PR's base commit has `FormalConjecturesUtil/`.

The statement is the product, so most of the review effort goes into catching misformalizations.

| rubric | runs | sessions | can block? |
|---|---|---|---|
| `faithfulness` | once per changed main statement, up to `full_checks` (default 6) | 3 each | yes, with a witness |
| `variant-faithfulness` | once per batch of up to 6 variants, textbook statements and main statements beyond `full_checks` | 2 each | yes, with a witness |
| `reuse` | once | 1 | yes, on a direct duplicate |
| `definitions` | once | 1 | no |
| `completeness` | once | 1 | no |
| `metadata` | once | 1 | no |
| `documentation` | once | 1 | no |
| `proof-quality` | once | 1 | no |

A **main statement** is a changed theorem tagged `research open` or `research solved` whose name
has no `.variants.` segment (so `.parts.i` and `.lower_bound` count). It is **changed** if the PR
writes one of its lines, or edits a definition in the same file that it uses.

## How the faithfulness review works

It adapts the "C8" pipeline of a study of misformalization detectors on formal-conjectures'
historical misformalizations (statements later fixed by PRs labelled `misformalization`):

1. **Literal reading** (`stages/literal-reading.md`). A session that sees the Lean statement with
   every comment and docstring removed, in a checkout where the changed files are stripped the same
   way, writes down what it literally asserts. It reads every definition the statement uses. This is
   the round-trip detector (C4): in the study it caught 82% of the misformalizations it was shown,
   with 3% false flags, the best single detector. Its false flags came from definitions it could not
   see, which is why this step has read access to the checkout.
2. **Independent formalization** (`stages/independent-formalization.md`). A session that sees only
   the docstring, in a checkout where the PR's new and changed declarations are removed, writes a
   specification and then its own Lean statement. It follows the study's blueprint-plus-checklist
   generator (C2 with the checklist). Comparing two formalizations (C3) was the only detector that
   added coverage beyond the round trip, but it also produced false flags.
3. **Adjudication** (`rubrics/faithfulness.md`). A normal rubric session sees the whole PR, both
   blind outputs, a mechanical scan for junk-value hazards, and the checklist
   (`references/misformalization-checklist.md`). It compares, tries a quick proof and disproof, and
   decides. It is told that any difference on an edge case is material: most of the round trip's
   misses in the study were edge cases it had noticed and then waved away.

The study's mechanical (C5) and prove/disprove (C6) detectors ran Lean. Reviewers here have only
read-only tools, so step 3 does the prove/disprove check by reasoning and must give a witness to
block.

Variants get only steps 1 and 3 (the round trip): the cheapest strong setup in the study.
