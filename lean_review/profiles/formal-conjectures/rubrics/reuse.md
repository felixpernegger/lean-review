# Reuse and duplication

Does the PR reuse Mathlib and {{project}} instead of reinventing them? A new declaration that a
located existing one directly replaces is a `block`. Every other duplication is `request_changes`.

## Detecting it

Run each of these searches. Choose search terms and grep `.lake/packages/mathlib/`,
`FormalConjecturesForMathlib/` and `FormalConjectures/` to verify.

- For each new definition, search for an existing one with the same content: in Mathlib (for
  example `Nat.centralBinom`, `Nat.partitionNumber`, `IsPGroup`, `Nat.nth`, `Set.ncard`,
  `Filter.Tendsto`), in `FormalConjecturesForMathlib/`, or in another problem file. Look under other
  names, and for variants equal up to unfolding or symmetry.
- For each new problem, search `FormalConjectures/` for the same problem under another source: an
  Erdős problem that is also stated under `Wikipedia/`, `OEIS/`, `Paper/` or `GreensOpenProblems/`,
  or an OEIS conjecture that is also an Erdős problem. Grep for the distinctive objects, and for the
  source numbers and names.
- A definition the PR copies into a second problem file, when another file already defines it,
  belongs in `FormalConjecturesForMathlib/`, shared by both.
- Within the diff, look for one-use definitions that only rename a Mathlib expression, which are
  better inlined, and for definitions that restate one another.

## Rejecting it

Every finding names the located replacement, with the `grep` hit, and says how to use it. Do not
ask the author to search. Not every hit is a defect: a bespoke definition that makes one problem's
statement clearer can stay in its problem file.

## Verdict

- `block` on a new declaration that an existing one directly replaces, and on a problem already
  stated in the repository, unless the PR links the two statements (for example with a statement
  that they are equivalent) or says why both are needed.
- `request_changes` for a definition Mathlib or the repository already provides under another name,
  a definition that should be shared through `FormalConjecturesForMathlib/`, or a one-use wrapper
  that should be inlined.
- `approve` when the PR adds genuinely new material and reuses existing definitions where it can.
