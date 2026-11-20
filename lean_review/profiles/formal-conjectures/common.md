### What this repository is

{{project}} records the formal statements of open conjectures and known results; it does not prove
them. A research statement's proof is `sorry` by design, so a `sorry` there is never a finding. The
statement itself is the product: a misformalized statement is the most serious defect a PR can
have, because it silently records the wrong problem, and anyone who later proves or disproves it
has solved something else.

Layout:

- `FormalConjectures/<Source>/…`: problem files, one problem per file (its variants and special
  cases share the file). Sources include `ErdosProblems/` (`N.lean`, namespace `ErdosN`), `OEIS/`
  (`N.lean`, namespace `OeisAN`), `Wikipedia/`, `Paper/`, `Arxiv/<id>/`, `GreensOpenProblems/`,
  `Mathoverflow/`, `Kourovka/`, `OptimizationConstants/`, `Books/`.
- `FormalConjecturesForMathlib/`: generic definitions and their lemmas, laid out like Mathlib.
  Nothing there may use `sorry`, and its statements are proved.
- `FormalConjecturesUtil/`: the attributes and linters.

Conventions every angle may rely on:

- Every statement has exactly one category: `research open` (no accepted solution), `research
  solved` (a proof is known: a formal proof here or elsewhere, or a widely accepted informal one),
  `textbook` (a special case or ingredient of a research problem), `API` (basic theory around a
  new definition) or `test` (a unit test of a definition, such as its first terms).
- A yes/no question carries `@[question]` and states the proposition asked about, negated with `¬`
  only when the answer is known to be no. A question that asks for a value carries
  `@[question value]` and mentions a `def <theorem>.answer : T := sorry` declared before it. The
  old `answer(sorry)` form is deprecated.
- Names: a single problem is `erdos_N`; a multi-part problem `erdos_N.parts.i`, `.parts.ii`, …;
  estimate questions `.lower_bound` / `.upper_bound`; variants and special cases from the source
  `<main>.variants.<name>`. OEIS term tests are `a_0`, `a_1`, … right after the sequence `a`.
- Proofs longer than a few lines do not belong in problem files: a solved problem links its proof
  with `@[formal_proof using … at "…"]`.
- Problem statements are not an API: renaming or restating one needs no deprecated alias.

Enforced by CI and the repository's linters, so do not report them: the copyright header;
imports (a problem file imports only `FormalConjecturesUtil`); that a module docstring exists;
every declaration inside a namespace; at least one `AMS` subject, in ascending order; exactly one
category; a docstring on every research and textbook statement; the `∃ x, P x → Q` pattern;
`opaque`, `axiom` and `def … := sorry` stubs (except `….answer`); the `formal_proof` syntax and its
Palomar link; `\[ \]` and `\( \)` in docstrings; `open Classical`.
