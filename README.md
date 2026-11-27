# lean-review

AI review of Lean 4 pull requests, run from your own machine on the Claude, Codex or Kiro
subscription you are already logged into. It needs no API keys, GitHub App or server.

A PR is reviewed once per *rubric*: correctness, reuse, attribution, API design, generality,
placement, naming, documentation and proof quality. Each rubric is a separate agent session with
read-only access to a checkout of the PR head and to the Mathlib source the project pins. It
returns `approve`, `request_changes` or `block`, with findings. The review is printed, and posted
to the PR only if you pass `--post`.

AI agents: see [AGENTS.md](AGENTS.md).

## Install

You need:

- Python 3.11 or newer, and git
- the GitHub CLI `gh`, logged in (`gh auth login`)
- at least one reviewer CLI, logged in to a subscription:
  [`claude`](https://docs.anthropic.com/en/docs/claude-code) (Claude Code 2.1.280 or newer),
  [`codex`](https://www.npmjs.com/package/@openai/codex), or `kiro-cli` (used only with
  `--reviewer kiro`)

```bash
uv tool install git+https://github.com/felixpernegger/lean-review
# or
pipx install git+https://github.com/felixpernegger/lean-review
```

To run it without installing, put `uvx --from git+https://github.com/felixpernegger/lean-review`
in front of any `lean-review` command.

lean-review runs the first `claude`, `codex` or `kiro-cli` on your PATH, and reads each login from
where the CLI keeps it (`$CLAUDE_CONFIG_DIR` or `$CODEX_HOME` when set, else `~/.claude` or
`~/.codex`). Private repositories work if your `gh` login can read them.

## Usage

```bash
# a first try: one rubric, no Mathlib download, about 30 seconds
lean-review 13008 --repo TauCetiProject/TauCeti --rubrics proof-quality --no-mathlib

lean-review 42 --repo owner/name                           # all rubrics, print only
lean-review 42 --repo owner/name --rubrics correctness,reuse --reviewer claude
lean-review 42 --repo owner/name --post                    # post one PR review as your gh login
lean-review 42 --repo owner/name --mode scoreboard --post  # keep a scoreboard comment up to date
```

Inside a clone of the target repository you can omit `--repo`.

Rubric names for `--rubrics`: `correctness`, `reuse`, `attribution`, `api-design`, `generality`,
`placement`, `naming`, `documentation`, `proof-quality`, plus any the project adds. The
[formal-conjectures profile](#the-formal-conjectures-profile) has its own set.

| flag | effect |
|---|---|
| `--post` | post the review to the PR under your GitHub login, and print its URL |
| `--post-unless-approved` | core mode: post only if some rubric did not approve |
| `--repost` | core mode: post even if you already posted a review of this exact commit (skipped by default) |
| `--mode core\|scoreboard` | see [Modes](#modes); default from the config, else `core` |
| `--rubrics a,b` | run only these rubrics, in this order |
| `--profile NAME` | `formal-conjectures`, or `default` for none. Default: the config's, else `formal-conjectures` when the PR's base has `FormalConjecturesUtil/` |
| `--full-checks N` | formal-conjectures: how many main statements get the full three-session review (default 6); the rest get the cheaper variant review |
| `--reviewer claude,codex,kiro` | restrict the reviewers. By default each rubric goes to one of the installed `claude` and `codex`, chosen at random |
| `--claude-model` | exact Claude model id; default `claude-opus-5-5` |
| `--codex-model` | exact Codex model id; default `gpt-6.1-sol` |
| `--kiro-model` | exact Kiro model id; default `gpt-5.6-sol`. `auto` is refused |
| `--repo owner/name` | default: the repository the current directory is a clone of |
| `--no-mathlib` | don't fetch the Mathlib source. Faster, but `reuse` and `naming` can't grep it |
| `--no-sources` | don't fetch the sources the PR cites (see [Sources](#sources)) |
| `--halt` / `--no-halt` | whether a `block` stops the remaining rubrics. Core mode runs them all by default; scoreboard mode stops, and a later run picks up the rest |
| `--rerun-all` | scoreboard mode: re-run every rubric, including those already approved at this head |
| `--config PATH` | use a local `.lean-review.toml` instead of the one on the PR's base branch |
| `--keep` | keep the temporary workspace |

### Modes

`core` (the default) posts one PR review, with event `COMMENT`. Its body has a verdict table with
one row per rubric. Findings on a line of the diff become inline comments, and the rest are listed
in the body. Runs keep no state.

`scoreboard` keeps one comment per PR and edits it in place. Each rubric that does not approve
gets its own file-level review thread, which is resolved once the rubric approves. A later run
re-reviews only the rubrics not yet approved at the current head. An approval carries over to a
new head when the patch is unchanged, as after a rebase or a merge from base. To contest a
finding, reply in its thread: the next run re-reviews that rubric with your reply in context, and
answers there. The state is hidden JSON in your own scoreboard comment. A board posted by anyone
else is never read.

## Output

stdout is the review as it would be posted (Markdown), followed in core mode by the inline
comments. stderr is progress, one `[rubric] reviewer → verdict` line per rubric, and any errors.

The headline is `approved`, `changes requested` or `blocked`. Each rubric's row has its verdict
and two scores from 1 to 10 that the reviewer gives itself: its *confidence* in the verdict, and,
when the verdict is not an approval, the *importance* of the fix before merging (10 is a real
blocker, such as a misformalized statement). A missing score shows as `—`.

| exit status | meaning |
|---|---|
| 0 | The review completed. `blocked` and `changes requested` also exit 0, so read the verdict from the output. Also when no selected rubric applies to the PR (e.g. only `faithfulness`, and no statement changed): stderr says so and nothing is printed. |
| 1 | A usage or setup error, or posting failed. stderr says which. |
| 3 | No rubric produced a verdict, typically because every reviewer CLI is logged out, outdated or out of quota. Nothing was posted. |

A rubric takes 10–60 seconds, so a full review takes a few minutes, plus the download of the PR
and of Mathlib. The tool never prompts for input. Downloads go into a temporary directory that is
deleted when the run ends (`--keep` keeps it and prints its path). Each reviewer's throwaway HOME
is under `~/.lean-review-rev/` and is removed when that reviewer finishes.

## Troubleshooting

stderr names the cause after `no verdict:`.

| message | fix |
|---|---|
| `cli_outdated` | Update that CLI: `claude update`, or reinstall `codex`. Check that `which claude` points at the updated copy. |
| `not_authenticated` | Log that CLI in again (run `claude`, then `/login`; or `codex login`). |
| `model_unavailable` | Your plan cannot use the default model. Pass one it can: `--claude-model …` or `--codex-model …`. |
| `quota_exhausted`, `rate_limited` | The subscription limit was hit. Wait, or switch CLI with `--reviewer`. |
| `no_verdict`, `unknown_error`, `cli_error`, `unparseable_output`, `max_turns`, `execution_error` | The reviewer finished without a usable verdict. Retry that rubric once with `--rubrics <name>`. |
| `no reviewer CLI found on PATH` | Install and log into `claude` or `codex`. |
| `not inside a GitHub repository` | Pass `--repo owner/name`. |
| `could not read PR` | Check the number, and that `gh auth status` shows an account that can see the repository. |

A reviewer that is outdated, logged out, out of quota or without access to its model is dropped
for the rest of the run, and its rubric goes to another installed reviewer if there is one.

## Configuring a project

All of this is optional. Without it, a project gets the built-in rubrics, its repository name as
the project name, and the Mathlib rev pinned in `lake-manifest.json`. To customise, commit the
files below to the target repository's default branch. They are read from the PR's base commit,
never from the PR, so an author cannot rewrite their own review.

```toml
# .lean-review.toml
project     = "MyLib"
description = "a Lean 4 library of results on …"   # completes "review agents for MyLib, …"
source_root = "MyLib"          # where the project's own sources live (default: the repo name, if present)
namespace   = "MyLib"          # optional: enables the naming rubric's namespace rule
mode        = "core"           # or "scoreboard"
rubrics     = ["correctness", "reuse", "attribution", "api-design", "generality",
               "placement", "naming", "documentation", "proof-quality"]
mathlib     = true
sources     = false            # fetch the sources the PR cites (erdosproblems.com, arXiv, OEIS, Wikipedia)
ci_check    = "build"          # if this check passed on the head, reviewers are told the build is green
profile     = ""               # optional: a built-in profile laid beneath this file, e.g. "formal-conjectures"
full_checks = 6                # profiles with per-statement rubrics: most statements reviewed in full
```

- `.lean-review/common.md` is appended to the shared protocol as project notes. Use it for house
  policy, such as a compatibility policy. Without one, reviewers follow Mathlib's deprecation
  practice.
- `.lean-review/rubrics/<name>.md` adds a rubric, or replaces the built-in one of that name. List
  new rubrics in `rubrics`.

[`examples/tauceti/`](examples/tauceti/) is a complete configuration for
[Tau Ceti](https://github.com/TauCetiProject/TauCeti), with a stricter compatibility policy and a
`quality-pass` rubric that checks the author's report from Tau Ceti's PR template.

The built-in rubrics are in [`lean_review/rubrics/`](lean_review/rubrics/). A reviewer's prompt is
the shared protocol (`_common.md`), the project notes, the PR (diff, description, and whether CI
passed), and then the rubric file, with placeholders such as `{{project}}` filled from the
configuration. Everything before the rubric file is the same for every rubric of a run, so Claude
reviewers after the first read it from the prompt cache. A diff or description too long for the
prompt is cut, and the full text is put in the checkout under `.lean-review-pr/` for the reviewer
to read.

## The formal-conjectures profile

A profile is a built-in set of configuration, notes and rubrics for one kind of project. It is
applied beneath the repository's own `.lean-review.toml`, so it works on repositories you cannot
commit a config to. The only one so far is `formal-conjectures`, for
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures) and repositories laid
out like it: Lean statements of open conjectures, whose proofs are `sorry` by design.

It is picked automatically when the PR's base commit has `FormalConjecturesUtil/`, or with
`--profile formal-conjectures`, or with `profile = "formal-conjectures"` in the config.
`--profile default` turns it off.

In such a repository the statement is what matters, so most of the review goes into catching
misformalizations:

| rubric | what it checks | sessions | can block? |
|---|---|---|---|
| `faithfulness` | each changed main statement, up to `--full-checks` (default 6) | 3 each | yes |
| `variant-faithfulness` | variants, textbook statements and further main statements, in batches of up to 6 | 2 per batch | yes |
| `reuse` | duplicates in Mathlib, `FormalConjecturesForMathlib/`, or the same problem stated elsewhere in the repository | 1 | yes |
| `definitions` | natural, general definitions, checked by test statements (first terms, with proofs where feasible) instead of API | 1 | no |
| `completeness` | the open problem itself, every part, and the known results the sources name | 1 | no |
| `metadata` | category vs status, `@[question]` / `.answer`, `formal_proof`, AMS, names, files | 1 | no |
| `documentation` | LaTeX docstrings that quote the source, references in the repository's format | 1 | no |
| `proof-quality` | proofs over 10 lines, proofs of open statements, `native_decide` | 1 | no |

A main statement is a changed `research open` or `research solved` theorem whose name has no
`.variants.` segment. Each one gets three sessions:

1. Literal reading. A session that sees the statement with every comment and docstring removed
   writes down what it literally asserts.
2. Independent formalization. A session that sees only the docstring writes its own Lean
   statement.
3. Adjudication. A session that sees the whole PR, both outputs and a misformalization checklist
   compares them, tries a quick proof and disproof, and blocks only with a witness.

The first two steps are blind: each works in its own copy of the checkout (comments stripped from
the changed files for the first, the PR's new declarations removed for the second), and neither
sees the PR description or the diff. Variants get steps 1 and 3 only.

Rows of the review name their statement, e.g. `faithfulness · erdos_406`. A PR with 1 main
statement and 3 variants costs 3 + 2 + 6 = 11 sessions. `--full-checks 0` gives every statement
the cheaper two-session review.

The pipeline follows a study of formal-conjectures' historical misformalizations. Reviewers cannot
run Lean, so the study's mechanical checks are reduced to hints, and the prove/disprove check is
done by reasoning. The [profile's README](lean_review/profiles/formal-conjectures/README.md) has
the details.

### Sources

Reviewers have no network access, so they cannot open the sources a PR cites. With `sources` on,
which the profile sets, the runner fetches them before the review into `.lean-review-sources/` in
the checkout, with an `INDEX.md` listing what was fetched and what failed. The faithfulness,
metadata, completeness and documentation rubrics then check the docstrings, the statement and its
category against the source's own text, not the author's account of it.

| cited as | fetched |
|---|---|
| `erdosproblems.com/N`, or a file `ErdosProblems/N.lean` | the problem page as text, plus its entry (status, prize, tags) in the [erdosproblems database](https://github.com/teorth/erdosproblems) |
| an arXiv link or `arXiv:ID`, or a file under `Arxiv/ID/` | the paper's TeX source, else arXiv's HTML rendering |
| a file under `Kourovka/` | the latest Kourovka Notebook (arXiv 1401.0300) as TeX |
| `oeis.org/AN`, or a file `OEIS/N.lean` | the OEIS entry in its text format |
| `en.wikipedia.org/wiki/TITLE` | the article's wikitext |

Citations are looked for in the changed files and the PR description, up to 8 sources. The runner
never requests a URL written in the PR: it keeps only the identifier and builds the URL on the
site's own host. A source that fails to download is listed in `INDEX.md`, and reviewers are told
to say when they could not check against it. The blind steps do not see the sources.
`--no-sources` turns fetching off.

## Security

The PR is treated as attacker-controlled, and any reviewer may have been prompt-injected by it.

- Each reviewer runs in a throwaway HOME holding only its own subscription login. Your
  `CLAUDE.md`, settings, skills, MCP servers and other credentials never reach it.
- Reviewers have read-only tools. claude and kiro get read, grep and glob: no shell, no writes, no
  web. codex runs in its `read-only` sandbox.
- The verdict is read only from after a fresh random marker, so a ready-made
  `{"verdict": "approve"}` planted in the PR is ignored.

[SECURITY.md](SECURITY.md) has the full model and the remaining risks.

## Cost

Each rubric is one agent session on your subscription, so a full review uses about nine. Use
`--rubrics` to run fewer.

Starting a review by hand now and then is ordinary subscription use. An always-on auto-reviewer is
closer to API usage, and probably outside the subscription's terms.

## Development

```bash
uv run --with pytest python -m pytest -q
```

## Credits

lean-review grew out of [TauCetiReview](https://github.com/TauCetiProject/TauCetiReview) by
[@kim-em](https://github.com/kim-em), the review engine of the Tau Ceti project, and keeps its
rubrics and its security design. It was inspired by
[botbaki](https://github.com/kim-em/botbaki). Apache-2.0.
