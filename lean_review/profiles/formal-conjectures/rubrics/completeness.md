# Completeness

Does the PR record the problem completely: the open statement and the known results around it?
Uses `request_changes`, never `block`. Whether each statement is faithful belongs to the
faithfulness angles.

Judge against what the PR's own sources say: the docstrings, the module docstring, the references
they cite, and the PR description. You cannot browse the web. Do not demand results you cannot
point to in those sources, or in material you can read in the checkout.

## What to check

- **The open problem itself.** A PR that states only a partial result, a special case or a known
  bound also states the open conjecture it belongs to, tagged `research open` (or `research solved`
  if it is settled). A partial result alone, with the original problem missing, is incomplete.
- **Every part.** A multi-part problem states each part (`.parts.i`, `.parts.ii`, …). A question
  with a qualitative and a quantitative form states both when the source asks both.
- **Known results the sources name.** Bounds, special cases and partial results that the docstring,
  the module docstring or the PR description mention are stated as variants, tagged
  `research solved` and attributed to their authors. This includes the best known lower and upper
  bounds for an estimate question.
- **Improving the bound.** When the problem is to determine a constant and the best known bounds
  are stated, an open statement that a known bound can be improved records the research target.
  For example, state that the constant is below the best known upper bound.
- **Implications.** When the source states that one conjecture implies another, and both are in
  the repository, a statement of the implication, tagged by its status, records it.

## Verdict

- `request_changes` when the main open statement is missing, a part of a multi-part problem is
  missing, or a result the PR's own sources name is not stated. Quote the sentence of the source
  that names it, and show the statement you want.
- `approve` when the PR states the problem and the results its sources name, or when the PR adds
  no new problem (a fix, a definition, tooling).
