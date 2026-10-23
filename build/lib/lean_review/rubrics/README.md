# Review rubrics

Each file here is the prompt for one review agent. A PR is reviewed by several independent
agents, each judging a single angle. An agent's full prompt is `_common.md` (the shared
protocol) followed by its angle file.

Agents leave the mechanical layer (the build and whatever linters CI runs) to CI. When the
project's configured CI check passed on the PR head, the runner tells them so as trusted ground
truth.

A project can add rubrics or replace these with `.lean-review/rubrics/<name>.md` on its default
branch, and append house policy with `.lean-review/common.md` (see the top-level README).

## The angles

The table is in review order: rubrics run one at a time and a `block` halts the round, so the
block-capable integrity angles run first (cheapest, most-likely-to-block earliest).

| Rubric | Question | Can block? |
| --- | --- | --- |
| [`correctness`](correctness.md) | Do the statements and definitions say what they should? | yes |
| [`reuse`](reuse.md) | Does it reuse Mathlib and the project instead of reinventing? | yes (outright duplication) |
| [`attribution`](attribution.md) | Does it credit its formal and informal sources? | yes (clear missing credit) |
| [`api-design`](api-design.md) | Minimal public surface, complete characteristic API? | no |
| [`generality`](generality.md) | Weakest assumptions; natural level? | no |
| [`placement`](placement.md) | Canonical home; direct, minimal imports? | no |
| [`naming`](naming.md) | Conclusion-describing names; conventional notation? | no |
| [`documentation`](documentation.md) | Accurate module and declaration docstrings? | no |
| [`proof-quality`](proof-quality.md) | Automation-first, robust proofs? | no |

Blocking angles are integrity checks. The rest use `request_changes` for fixable issues.
