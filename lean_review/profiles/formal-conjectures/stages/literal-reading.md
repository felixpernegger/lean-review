# Literal reading

Below are Lean 4 statements from a pull request, with every comment and docstring removed. Write,
in precise mathematical English, exactly what each one asserts: a literal reading, not the intended
meaning. Do not guess what the author meant. If a condition looks odd or unintended, still state it
as written. Another reviewer will compare your reading with the intended statement, which you are
deliberately not shown, so a reading that repairs the code is worse than useless.

Your working directory is the repository at the pull request's head. In the files the pull request
changes, comments and docstrings are removed too. The pinned Mathlib source is under
`.lake/packages/mathlib/`, and the project's own definitions are under
`FormalConjecturesForMathlib/` and in the problem files. Before you describe a name you did not see
defined, find its definition (Grep for it, then Read it) and describe what it actually says. Never
write that a definition "would need to be looked up".

For each statement give:

- every variable with its type: natural numbers include 0, and say whether a variable is real,
  integer, a set, a finset, a function and so on;
- every hypothesis and the conclusion, with the quantifiers in order and what each witness may
  depend on;
- every definition it uses, read literally, including what it does on edge cases: 0, 1, the empty
  set, a degenerate object, inputs outside its intended domain;
- for every partial operation (subtraction or division on ℕ or ℤ, `/` by zero, `⁻¹`, `Real.sqrt`,
  `Real.log`, `Int.toNat`, `sInf`/`sSup`, `Set.ncard`/`Nat.card`, `limsup`/`liminf`, a limit), the
  value Lean gives it and whether that can matter here;
- for a statement that mentions some `….answer`: that this value is an unknown placeholder.

Do not judge whether a statement is correct, interesting or well chosen. Only describe it.

{{statements}}

## Output

```json
{"readings": [{"name": "<declaration name as given above>", "reading": "<the literal reading>"}]}
```
