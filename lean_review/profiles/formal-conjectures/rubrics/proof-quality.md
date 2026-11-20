# Proofs

You judge the proofs the PR adds. In this repository proofs are not the point: the statements are.
Uses `request_changes`. Correctness is the kernel's job, so you judge whether a proof belongs here
and how it is written.

Count a proof's length in non-blank lines of tactic or term code, without comments.

## What to check

- **Problem files (`FormalConjectures/`).**
  - A `research open` statement has no proof. A sorry-free proof there means the statement is
    trivial; report it, and the faithfulness angle will judge why.
  - A `research solved` statement keeps `sorry` and links its proof with
    `@[formal_proof using … at "…"]`.
  - A proof longer than **10 lines** of any statement (test, API or solved) is a finding. Either
    shorten it, drop it (keep `sorry`, and link it with `formal_proof` if it exists elsewhere), or
    move the lemma it needs into `FormalConjecturesForMathlib/` or upstream.
- **`FormalConjecturesForMathlib/`.** Statements there must be proved. A proof longer than 10 lines
  is a finding: ask to split it into lemmas, or question whether the lemma is needed at all. A
  definition with a small, tested interface beats a long development.
- **Test statements.** Short and robust: `decide`, `rfl`, `norm_num`, `simp`. A test that needs a
  long proof usually means the definition should be computable. Say so.
- **`native_decide`.** Allowed only in `test` statements, never in `FormalConjecturesForMathlib/`
  or in a solved statement's proof. When used, the PR should say why `decide` does not suffice.
- **Robustness.** Prefer automation (`simp`, `omega`, `decide`, `norm_num`, `grind`) over long
  chains of named rewrites. `change`, `show` and reliance on accidental definitional unfolding need
  a comment saying why.

## Verdict

- `request_changes` for a proof of a `research open` statement, a proof over 10 lines, a solved
  proof that should be a `formal_proof` link, `native_decide` outside tests, or a brittle or opaque
  proof.
- `approve` when proofs are short, robust and placed where they belong, or when the PR adds no
  proofs.
