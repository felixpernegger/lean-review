# Misformalization checklist

Each item names a way a Lean statement can differ from the mathematics it records. Read every
definition literally, including on edge cases, and check the statement against each item.

1. **Junk values.** Division by zero (`x / 0 = 0`), `0⁻¹ = 0`, truncated subtraction and rounded
   division on ℕ, `Real.sqrt` of a negative number, `Real.log` of a non-positive number,
   `Int.toNat` of a negative number, `sInf`/`sSup` of an empty or unbounded set, `Set.ncard` or
   `Nat.card` of an infinite set (both 0), `limsup`/`liminf` without boundedness, `ENNReal`
   arithmetic (∞, 0 · ∞), and where coercions sit.
2. **Number systems and types.** ℕ vs ℤ vs ℚ vs ℝ for every variable and every constant: a constant
   "c > 0" ranging over ℕ, or an exponent computed in ℕ, changes the claim. Universe levels, and
   whether quantifying over `Type` instead of `Type*` or `Type u` matters.
3. **Indexing and sizes.** 0- vs 1-indexing, `Fin n` vs `Fin (n + 1)`, `Finset.range n` vs
   `Finset.Icc 1 n`, `Nat.nth` (0-indexed), vertex vs edge counts, off-by-one in lengths.
4. **Quantifiers.** Order and scope, what each witness may depend on (∀ε ∃δ vs ∃δ ∀ε), ∀ vs ∃ vs
   ∃!, "for all large n" (`∀ᶠ … atTop`) vs "for infinitely many n" (`∃ᶠ`) vs "for all n", "almost
   all" vs "all". An object fixed where the source says "there exists one", or the reverse.
5. **Logical form.** The direction of each implication, iff vs if, inclusive vs exclusive or, `∧`
   where `→` was meant, and the scope of a negation. `∃ x, P x → Q` is almost always wrong.
6. **Extrema and attainment.** Largest or smallest value vs a bound, `sSup` vs a maximum, a limit
   that must exist vs a bound on `liminf`/`limsup`, density that must exist vs lower density.
7. **Completeness and extra hypotheses.** Every part of the source is formalized; no hypothesis is
   added that the source does not state or imply; the statement is not only one direction or one
   case of the source.
8. **Implicit conditions.** Non-degeneracy (n ≥ 2, k ≥ 1, a non-constant polynomial, a nontrivial
   group), non-emptiness, finiteness, distinctness, simplicity of graphs, non-zero denominators.
   For each hypothesis, ask whether any object satisfies it; for each parameter, try 0 and 1.
9. **Definitions of notions.** Each new or reused definition matches the standard notion as the
   source uses it, on degenerate inputs too: a "nontrivial" solution, a partition vs a cover, all
   coefficients vs those up to the degree, `ZMod 0` (which is ℤ), empty sums and products.
10. **Asymptotics.** `o(1)` and `O(·)` terms quantified correctly (an `o(1)` is a function tending
    to 0, chosen before n, not a constant per n); `≍`/`Θ` vs `~`; `≪` vs `(1 + o(1))`; which side
    of `=O[atTop]` is which; a limit to ∞ vs to 0.
11. **Questions and answers.** A yes/no question states the proposition asked about, negated only
    when the answer is known to be no. For a `….answer` value, check that no trivial or tautological
    choice of answer makes the statement provable or meaningless.
12. **Parameter exploits.** Is there a value of a parameter, or a degenerate object, for which the
    Lean statement is provable by a trick (vacuous, trivial, a junk value) although the mathematical
    statement is open, or false although the mathematical statement is true?

A difference is **material** when it changes which statements are claimed for some input that the
source does not clearly exclude. Differences on edge cases are material. Give evidence for each
finding: the Lean fragment, and an input on which the two readings differ.
