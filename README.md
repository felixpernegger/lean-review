# lean-review

AI review of Lean 4 pull requests, run from your own machine on the Claude or Codex
subscription you are already logged into. It needs no API keys, GitHub App or server.

A PR is reviewed once per *rubric*. Each rubric is a separate agent that judges the PR from one
angle and returns `approve`, `request_changes` or `block`, with findings. The review is printed,
and posted to the PR only if you pass `--post`.

This page is an overview. [AGENTS.md](AGENTS.md) is the full reference: every flag, the output
format, the error messages and the configuration keys. It is written so that an AI agent can run
lean-review for you.

## What it checks

Lean checks the proofs, and CI checks the build and the linters. The rubrics judge what those
cannot:

| rubric | question | can block? |
|---|---|---|
| `correctness` | Do the definitions and statements say what they are meant to? Looks for misformalizations, vacuous statements and content moved into the hypotheses. | yes |
| `reuse` | Does anything duplicate Mathlib or the project itself instead of using what is there? | yes, on a direct duplicate |
| `attribution` | Are the papers and notes the work follows credited? | yes, when credit is clearly missing |
| `api-design` | Is the public interface minimal, and does each new definition come with the lemmas needed to use it? | no |
| `generality` | Are statements at their natural level: no unused or over-strong assumptions, no abstraction without a use? | no |
| `placement` | Is each declaration in the right file, with sensible imports? | no |
| `naming` | Do names and notation follow Mathlib's conventions, and promise no more than the statement proves? | no |
| `documentation` | Are files and public declarations documented, accurately and without overclaiming? | no |
| `proof-quality` | Are proofs robust and readable: automation over brittle rewrite chains, long arguments split into lemmas? | no |

The prompts are in [`lean_review/rubrics/`](lean_review/rubrics/). A project can replace them or
add its own (see [Configuring a project](#configuring-a-project)), and repositories of open
conjectures get [a different set](#formal-conjectures).

## Install

You need:

- Python 3.11 or newer, and git
- the GitHub CLI `gh`, logged in (`gh auth login`)
- at least one reviewer CLI, logged in to a subscription:
  [`claude`](https://docs.anthropic.com/en/docs/claude-code) (Claude Code 2.1.280 or newer) or
  [`codex`](https://www.npmjs.com/package/@openai/codex)

```bash
uv tool install git+https://github.com/felixpernegger/lean-review
# or
pipx install git+https://github.com/felixpernegger/lean-review
```

To run it without installing, put `uvx --from git+https://github.com/felixpernegger/lean-review`
in front of any `lean-review` command.

## Usage

```bash
# a first try: one rubric, no Mathlib download, about 30 seconds
lean-review 13008 --repo TauCetiProject/TauCeti --rubrics proof-quality --no-mathlib

lean-review 42 --repo owner/name                           # all rubrics, print only
lean-review 42 --repo owner/name --rubrics correctness,reuse
lean-review 42 --repo owner/name --post                    # post the review as your gh login
lean-review 42 --repo owner/name --mode scoreboard --post  # keep a scoreboard comment up to date
```

Inside a clone of the target repository you can omit `--repo`. A full review takes a few minutes.

The flags you are most likely to want:

| flag | effect |
|---|---|
| `--post` | post the review to the PR under your GitHub login |
| `--rubrics a,b` | run only these rubrics |
| `--reviewer claude` | use only this reviewer. By default each rubric goes to `claude` or `codex` at random, whichever are installed |
| `--no-mathlib` | skip the Mathlib download. Faster, but `reuse` and `naming` cannot search Mathlib |
| `--mode scoreboard` | see below |

`lean-review --help` lists the rest, and [AGENTS.md](AGENTS.md#all-flags) explains them.

There are two modes. `core`, the default, posts one PR review with a verdict per rubric and
inline comments on the diff. `scoreboard` keeps a single comment per PR up to date across runs: it
re-reviews only the rubrics that have not approved yet, and you can contest a finding by replying
in its thread.

If a run produces no verdict, the error output names the cause, usually a reviewer CLI that is
logged out, outdated or out of quota. [AGENTS.md](AGENTS.md#step-4-read-the-result) lists each
message with its fix.

## Configuring a project

This is optional. To customise the review, commit a `.lean-review.toml` to the target
repository's default branch:

```toml
project     = "MyLib"
description = "a Lean 4 library of results on …"
rubrics     = ["correctness", "reuse", "naming", "my-rubric"]
mode        = "scoreboard"
```

Next to it, `.lean-review/common.md` holds house policy that every reviewer is told, and
`.lean-review/rubrics/<name>.md` adds a rubric or replaces a built-in one. These files are read
from the PR's base branch, never from the PR, so an author cannot rewrite their own review.

[AGENTS.md](AGENTS.md#configuring-a-project) has every key, and
[`examples/tauceti/`](examples/tauceti/) is a complete configuration for
[Tau Ceti](https://github.com/TauCetiProject/TauCeti).

## formal-conjectures

[formal-conjectures](https://github.com/google-deepmind/formal-conjectures) and repositories laid
out like it hold Lean statements of open conjectures, whose proofs are `sorry` by design. There
the statement is what matters, so lean-review detects the layout and switches to rubrics aimed at
catching misformalizations:

| rubric | question | can block? |
|---|---|---|
| `faithfulness` | Does each main statement say what its docstring and its source say? | yes |
| `variant-faithfulness` | The same for variants and textbook statements, with a cheaper check | yes |
| `reuse` | Is the problem already stated in Mathlib or elsewhere in the repository? | yes |
| `definitions` | Are new definitions natural and general, and tested on examples? | no |
| `completeness` | Is the whole problem there: every part, and the known results the sources name? | no |
| `metadata` | Do the category, status, answer and subject tags, names and file layout fit? | no |
| `documentation` | Do the docstrings quote the source, with references in the repository's format? | no |
| `proof-quality` | Are the few proofs short and legitimate, with no proof of an open statement? | no |

`faithfulness` reads each statement three times. One agent sees only the Lean and writes down
what it literally asserts, a second sees only the docstring and formalizes it independently, and
a third compares the two with the PR. The sources a PR cites (erdosproblems.com, arXiv, OEIS,
Wikipedia) are downloaded first, so statements are checked against the source's own text.

The [profile's README](lean_review/profiles/formal-conjectures/README.md) has the details.

## Security

The PR is treated as attacker-controlled, and any reviewer may have been prompt-injected by it.
So reviewers get read-only tools and a throwaway home directory holding nothing but their own
login, and a verdict planted in the PR is ignored. [SECURITY.md](SECURITY.md) has the full model
and the remaining risks.

## Cost

Each rubric is one agent session on your subscription, so a full review uses about nine. Use
`--rubrics` to run fewer.

Starting a review by hand now and then is ordinary subscription use. An always-on auto-reviewer is
closer to API usage, and probably outside the subscription's terms.

## Credits

lean-review grew out of [TauCetiReview](https://github.com/TauCetiProject/TauCetiReview) by
[@kim-em](https://github.com/kim-em), the review engine of the Tau Ceti project, and keeps its
rubrics and its security design. It was inspired by
[botbaki](https://github.com/kim-em/botbaki). Apache-2.0.

To work on lean-review itself, see [CLAUDE.md](CLAUDE.md).
