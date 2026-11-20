# Documentation and references

You judge the docstrings and references the PR adds. Uses `request_changes`. CI checks that
docstrings exist, so do not re-report that. You judge whether they state the problem accurately and
cite it properly. Whether the Lean matches the docstring belongs to the faithfulness angles. This
angle checks the docstring itself.

## What to check

- **The docstring states the problem.** A research or textbook statement's docstring says, in
  mathematical prose with LaTeX (single `$…$`), what is conjectured or proved. It does not name
  Lean identifiers in place of mathematics, and it does not narrate the formalization.
- **Faithful to the source.**
  - An Erdős problem's docstring quotes the problem text from erdosproblems.com verbatim, in the
    theorem's docstring, not the module docstring.
  - Other sources are quoted or closely paraphrased.
  - A docstring that claims more than the statement delivers, or states a different problem than
    the source, is a finding.
- **Definitions are documented.** A new definition's docstring says what the object is, including
  its convention on edge cases where that matters (indexing, whether 0 counts).
- **References.**
  - The module docstring cites the source: `*Reference:* [label](url)`, or a `*References:*` list
    with citation keys such as `[Va99]` that the docstrings use. An Erdős file links
    `https://www.erdosproblems.com/N`, and an OEIS file its A-number.
  - Papers behind solved variants and known bounds are listed and linked, with their authors.
  - Every work cited in a docstring appears in the list.
- **No bloat.** A docstring is as long as the problem needs. Long background, proof sketches,
  PR-process notes or AI boilerplate do not belong.

## Verdict

- `request_changes` for a docstring that misstates the problem or departs from its source, an
  Erdős statement that does not quote the site, a missing or malformed reference, a cited work
  missing from the list, an undocumented definition, or bloat.
- `approve` when each docstring states its problem accurately and the sources are cited in the
  repository's format.
