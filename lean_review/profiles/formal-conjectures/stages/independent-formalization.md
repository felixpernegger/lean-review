# Independent formalization

Formalize the mathematical statement below in Lean 4 with Mathlib, as a careful contributor to
{{project}} would. Another reviewer will compare your formalization with one written
independently, which you are deliberately not shown. Yours is a check on it, so read the statement
literally and carefully. Most formalization errors come from misreading the statement, not from
writing Lean.

## Environment

- Your working directory is the repository at the pull request's head, except that the
  declarations this pull request adds or changes have been removed. The pinned Mathlib source is
  under `.lake/packages/mathlib/`, and the project's generic definitions are under
  `FormalConjecturesForMathlib/`. Use an existing definition wherever one expresses a notion (Grep
  before you invent one), and check its edge cases by reading it.
- The definitions listed under "Definitions to write" were introduced by the pull request and are
  not available to you. Define each one yourself, with that name, above the theorem.
- Problem files import only `FormalConjecturesUtil` (all of Mathlib plus the project), and
  `autoImplicit` is off. The proof is `by sorry`.
- A yes/no question (`question` among the attributes) is formalized as the proposition it asks
  about: the statement that holds if the answer is yes. Do not decide the answer, and do not
  negate it unless the text says the answer is known to be no.
- A question asking for a value (`question value`) declares `def <name>.answer : T := sorry`
  first, and the theorem mentions that value.

## The statement

Declaration name: `{{name}}`, in `{{path}}`. Attributes: {{attributes}}.

Statement (from the declaration's docstring):

<statement>
{{statement}}
</statement>

Module docstring (title, context and references):

<module>
{{module_doc}}
</module>

Definitions to write:

{{new_definitions}}

## Step 1: specify

Before you write any Lean, fill in this specification:

- `objects`: every variable, function, set or structure, with its Lean type and why that type
  (number system; ℕ includes 0).
- `explicit_hypotheses`: each condition the statement makes, quoted, with its Lean form.
- `implicit_hypotheses`: each condition the statement takes for granted but does not state
  (positivity, non-degeneracy, non-zero denominators, non-emptiness, the domain of `sqrt` or `log`,
  distinctness), with its Lean form and why it is implied. An empty list if none.
- `quantifier_tree`: the quantifiers from outermost to innermost, each with its variables, domain,
  restriction, and the earlier variables it may depend on.
- `goal`: the form of the conclusion (equality, inequality, attained extremum, iff, implication,
  cardinality, asymptotic statement, …) and exactly what it says.
- `conventions`: the indexing (0- or 1-based, which interval) and every operation that can produce
  a junk value, with how it is guarded.
- `definitions`: for each definition you must write, its signature, meaning, and how it handles 0,
  1, the empty set and degenerate inputs.
- `ambiguities`: anything that admits more than one reading, the reading you chose, and why.

## Step 2: translate

Translate the specification into Lean, field by field: the same types, hypotheses, quantifier
order and goal. Before you finish, check your formalization against each point below and fix
anything that fails:

1. Junk values. Lean totalises partial operations: `x / 0 = 0`, `0⁻¹ = 0`, subtraction on ℕ
   truncates, `Real.sqrt` of a negative number is 0, `Real.log 0 = 0` and `Real.log (-x) =
   Real.log x`, `Int.toNat` of a negative number is 0, division on ℕ rounds down, `sInf ∅ = 0` on ℕ.
   Wherever the statement could hit such a case, add the guard the mathematics assumes or choose a
   type where the operation is honest.
2. Number systems. Choose ℕ, ℤ, ℚ, ℝ or ℂ deliberately for every variable and every intermediate
   quantity (ratios, logarithms, limits, constants). "Positive integer" means `0 < n`.
3. Indexing. `Finset.range n` is {0, …, n - 1}, `Finset.Icc 1 n` is {1, …, n}, `Fin n` has values
   0 to n - 1, and `Nat.nth Nat.Prime 0 = 2`.
4. Quantifiers. Check the order and scope of every quantifier and what each witness may depend on.
   "For sufficiently large n" is `∀ᶠ n in atTop`; "infinitely many" is `Set.Infinite` or `∃ᶠ`.
5. Logical form. If and only if, or only if; the direction of every implication; inclusive or.
6. Extrema. "The largest value is c" needs attainment (`IsGreatest`, `IsLeast`), not only a bound.
7. Completeness. Formalize every part of a multi-part claim, and add no hypothesis the statement
   neither states nor implies.
8. Implicit conditions. Non-degenerate objects, non-zero denominators, non-empty sets, distinct
   elements, finiteness.
9. Mathlib pitfalls. `Set` vs `Finset`; `Set.ncard` and `Nat.card` are 0 on infinite sets;
   coefficients of a polynomial beyond its degree are 0; `Nat.Prime` vs `Prime`; asymptotic
   notation (`=O[atTop]`, `~[atTop]`, `=Θ[atTop]`) and which side is which; where coercions sit
   around a division.
10. Questions. State the proposition being asked about.

If the text admits several readings, choose the one a specialist would intend and record the
others under `ambiguities`.

## Output

```json
{"spec": {"objects": [], "explicit_hypotheses": [], "implicit_hypotheses": [],
          "quantifier_tree": [], "goal": "", "conventions": "", "definitions": [],
          "ambiguities": []},
 "lean": "<your definitions, if any, followed by the theorem, as Lean source>"}
```
