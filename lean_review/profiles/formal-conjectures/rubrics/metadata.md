# Categories, questions, names and placement

You judge each statement's metadata and where it lives: category, question attributes, AMS
subjects, names, files and namespaces. Uses `request_changes`. CI checks that the attributes exist
and are well-formed, so do not re-report that. You judge whether they are right.

## What to check

- **Category matches the status.**
  - `research open` only when no accepted solution exists.
  - `research solved` when a proof is known: published, accepted informally, or formalized. A
    result taken from a research paper is `research solved`, not `textbook`.
  - Use what the docstrings, references and PR description say about the status. An Erdős problem
    that the site or the docstring reports as solved is not `research open`. A `research solved`
    statement's docstring or module docstring names who solved it.
  - `textbook` only for a special case or ingredient closely tied to a research problem.
  - `API` for basic theory about a new definition; `test` for unit tests of one.
- **Questions.**
  - A yes/no question carries `@[question]`, and its statement is the proposition asked about.
  - When the answer is known to be no, the statement is negated with `¬`, and the category is
    `research solved`.
  - A question that asks for a value carries `@[question value]` and uses a
    `def <theorem>.answer := sorry` declared before it. Once the value is known, the definition
    gives it and the statement is unchanged.
  - A statement that answers a question the source asks, without one of these attributes, is a
    finding. So is the deprecated `answer(sorry)`.
- **`formal_proof`.** A `research solved` statement whose docstring or PR claims a formal proof
  links it with `@[formal_proof using … at "…"]` instead of carrying the proof. A proof
  conditional on another statement uses the `conditional` form.
- **AMS subjects.** The subjects are the main areas of the statement, not just any area it touches.
  Flag only an evidently wrong subject, for example number theory (11) on a pure graph-theory
  statement (05).
- **Names.**
  - Erdős problems: `erdos_N`, `erdos_N.parts.i`, `erdos_N.lower_bound` / `.upper_bound`, and
    `erdos_N.variants.<descriptive_name>`.
  - OEIS: the sequence `a` (or predicate `A`), and term tests `a_0`, `a_1`, ….
  - Elsewhere, the statement's standard name in snake case.
  - Definitions follow Mathlib's naming and capitalisation conventions.
  - Variants are named after their content or their author, not numbered.
- **Files and namespaces.**
  - Each problem lives under the folder of its source: `ErdosProblems/N.lean` with namespace
    `ErdosN`, `OEIS/N.lean` (no leading zeros) with namespace `OeisAN`, `Arxiv/<id>/Name.lean`,
    and CamelCase names under `Wikipedia/` and `Paper/`.
  - A problem from a paper is not filed under `Wikipedia/`.
  - One problem per file, and its variants share that file.
- **Binders and universes.** Implicit binders `{}` where a variable is determined by later
  arguments. A statement quantifying over types states its universe deliberately, not by accident
  through `Type` or a stray `Type*`.

## Verdict

- `request_changes` for a category that contradicts the status, a missing or misused question
  attribute, a claimed formal proof without its link, an evidently wrong AMS subject, a name or file
  against the conventions above, or a universe chosen by accident.
- `approve` when the metadata matches each statement and the conventions.
