# lean-review

AI review of Lean 4 pull requests, run from your own machine on the **Claude / Codex / Kiro
subscription you are already logged into**. You need no API keys, no GitHub App and no server.

Each PR is judged by independent agents, one per *rubric* (correctness, reuse, attribution, API
design, generality, placement, naming, documentation, proof quality). Each agent works in a
read-only checkout of the PR head, alongside the Mathlib source the project pins, and is told to
grep before claiming that something exists or is missing. It returns `approve`, `request_changes` or `block` with
findings. The approach follows [botbaki](https://github.com/kim-em/botbaki), with three
differences: it uses an agentic read-only review over a checkout instead of a single API call, it
authenticates through subscription CLIs instead of an API key, and it runs as a CLI with no
daemon.

> **AI agents:** read [AGENTS.md](AGENTS.md) for step-by-step instructions.

## Quick start

These steps are written so that a person or an AI agent can follow them literally.

**1. Check the prerequisites.** The required ones are Python, git, `gh`, at least one reviewer
CLI, and either uv or pipx to install with:

```bash
python3 --version     # 3.11 or newer
git --version
gh auth status        # GitHub CLI, logged in (`gh auth login` if not)
claude --version      # Claude Code 2.1.280 or newer, logged in to a Claude subscription
codex --version       # optional second reviewer: OpenAI Codex CLI (a current release), logged in to ChatGPT
uv --version          # uv, or else pipx (`pipx --version`), to install the tool
```

At least one reviewer CLI is required:
- [`claude`](https://docs.anthropic.com/en/docs/claude-code) (update with `claude update`)
- [`codex`](https://www.npmjs.com/package/@openai/codex)
- `kiro-cli`, after `kiro-cli login`. Kiro is only used when you pass `--reviewer kiro`.

lean-review runs the first `claude` / `codex` / `kiro-cli` on your PATH, so check `which claude`
when several are installed. Each CLI must be logged in once, interactively. lean-review never
asks for keys or tokens. Reviews run in a clean HOME holding only the login, so your own
`CLAUDE.md`, settings, skills and MCP servers are not used. The login is read from where the CLI
keeps it: `$CLAUDE_CONFIG_DIR` or `$CODEX_HOME` when set, else `~/.claude` or `~/.codex`. `gh`
reads the PR and, with `--post`, publishes as you. Private repositories work if your login can
read them.

**2. Install.** With [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`):

```bash
uv tool install git+https://github.com/felixpernegger/lean-review   # puts `lean-review` on PATH
# or run without installing: put `uvx --from git+https://github.com/felixpernegger/lean-review`
# in front of any `lean-review` command below, e.g.
uvx --from git+https://github.com/felixpernegger/lean-review lean-review 13008 --repo TauCetiProject/TauCeti --rubrics proof-quality --no-mathlib
# or with pipx:
pipx install git+https://github.com/felixpernegger/lean-review
```

**3. Try a cheap dry run** (one rubric, no Mathlib download, about 30 seconds):

```bash
lean-review 13008 --repo TauCetiProject/TauCeti --rubrics proof-quality --no-mathlib
```

**4. Review a real PR.** This prints the review and posts nothing:

```bash
lean-review <PR number> --repo <owner>/<name>
```

**5. Publish it,** only once a human has read the dry-run output and agreed:

```bash
lean-review <PR number> --repo <owner>/<name> --post
```

Inside a clone of the target repository, you can omit `--repo`. Posts appear under whichever
account `gh auth status` shows.

## Use

```bash
lean-review 42 --repo owner/name                          # all rubrics, print only
lean-review 42 --repo owner/name --rubrics correctness,reuse --reviewer claude
lean-review 42 --repo owner/name --post                   # one PR review, as your gh login
lean-review 42 --repo owner/name --mode scoreboard --post # stateful board + threads
```

It **defaults to a dry run**: the review is printed and nothing is posted.

Rubric names for `--rubrics`: `correctness`, `reuse`, `attribution`, `api-design`, `generality`,
`placement`, `naming`, `documentation`, `proof-quality`, plus any the project adds. The
[formal-conjectures profile](#profiles-formal-conjectures) has its own set.

| flag | effect |
|---|---|
| `--post` | publish to the PR under your GitHub login; the URL is printed |
| `--post-unless-approved` | core mode: publish only if some rubric did not approve (for "post it if it finds problems") |
| `--repost` | core mode: post even though you already posted a review of this exact commit (by default a second post is skipped) |
| `--mode core\|scoreboard` | output style (see below); default from config, else `core` |
| `--rubrics a,b` | run only these rubrics, in this order |
| `--profile NAME` | built-in profile: `formal-conjectures` or `default`. Default: the config's, else `formal-conjectures` when the PR's base has `FormalConjecturesUtil/`, else none |
| `--full-checks N` | formal-conjectures: most main statements given the full per-statement review (default 6); the rest get the cheaper variant review |
| `--reviewer claude,codex,kiro` | restrict the reviewers. By default each rubric is given to one reviewer drawn at random from the installed `claude` and `codex`; the progress line shows which. Pass e.g. `--reviewer claude` for a single one |
| `--claude-model` | exact Claude model id; default `claude-opus-5-5` |
| `--codex-model` | exact Codex model id; default `gpt-6.1-sol` |
| `--kiro-model` | exact Kiro model id; default `gpt-5.6-sol`. `auto` is refused |
| `--repo owner/name` | the repository; defaults to the one the current directory is a clone of |
| `--no-mathlib` | skip fetching Mathlib source (faster; weaker `reuse`/`naming`) |
| `--no-sources` | do not fetch the sources the PR cites (on by default in the formal-conjectures profile; see [Sources](#checking-against-the-source)) |
| `--halt` / `--no-halt` | whether a `block` stops the remaining rubrics. Default: core mode runs them all; scoreboard mode stops (a later run picks up the rest) |
| `--rerun-all` | scoreboard mode: re-run rubrics that are already green at this head |
| `--config PATH` | use a local `.lean-review.toml` instead of the one on the PR's base branch |
| `--keep` | keep the temporary workspace |

### Modes

- **`core`** (default) posts one GitHub PR review (event `COMMENT`):
  - The body holds a verdict table with one row per rubric (see [Scores](#scores)).
  - Findings whose line is in the diff become inline comments.
  - All other findings are listed in the body.
  - Each run is independent and keeps no state.
- **`scoreboard`** keeps one scoreboard comment per PR and edits it in place.
  - **Per-rubric threads.** Each blocking rubric gets its own file-level review thread. The thread
    is resolved once the rubric turns green.
  - **What a run re-checks.** A later run re-reviews only rubrics that are not green at the current
    head.
  - **Carried approvals.** An approval carries over to a new head when the patch is unchanged, as
    after a rebase or a merge from base.
  - **Contesting.** Replying in a rubric's thread contests that finding. The next run re-reviews
    only that rubric, with your reply in context, and answers in the thread.
  - **Where state lives.** State is hidden JSON inside *your own* scoreboard comment. No other
    store exists, and a board posted by anyone else is never read.

## Output, run time and exit codes

### Scores

Every rubric's row also carries two 1–10 self-assessments by its reviewer. A missing or invalid
score shows as `—`.

- **confidence**: how sure the reviewer is of its verdict. 1 means it is guessing. 5 means it thinks
  so, but the opposite could well be true. 10 means it is extremely confident.
- **importance**: given only with `changes requested` or `blocked`, it says how much the fix
  matters before merging. 1 means it barely matters. 5 means it should be fixed, but merging
  without it would make little difference. 10 means a real blocker, such as a misformalized
  statement.


- **stdout** holds the review exactly as it would be posted (Markdown), followed by the inline
  comments in core mode. **stderr** holds progress, one `[rubric] reviewer → verdict` line per
  rubric, plus any errors.
- **Run time.** Each rubric takes about 10–60 seconds, so all nine take a few minutes. The first
  step also downloads the PR's code, the Mathlib source the project pins (unless you pass
  `--no-mathlib`) and, in the formal-conjectures profile, the sources the PR cites. That is usually under a minute, but slower on a slow connection. The tool is
  non-interactive and never prompts, so allow at least 30 minutes before treating a run as hung.
  When run through `uvx`, uv's own build messages appear on stderr first.
- **Disk.** Everything is downloaded into a fresh temporary directory, which is deleted when the
  run ends (`--keep` keeps it and prints its path). Each reviewer's throwaway HOME lives under
  `~/.lean-review-rev/` and is emptied or removed as soon as that reviewer finishes. Nothing else persists,
  apart from uv's or pipx's own package cache.
- **Exit status:**

  | status | meaning |
  |---|---|
  | 0 | The review completed and was printed (and posted with `--post`). A `blocked` or `changes requested` verdict still exits 0. Read the verdict from the output. Also when no selected rubric applies to the PR (e.g. only `faithfulness`, and no statement changed): stderr says so and nothing is printed. |
  | 1 | A usage or setup error, or posting failed. The message on stderr says which. |
  | 3 | No rubric produced a verdict, typically because every reviewer CLI is logged out, outdated, or out of quota. Nothing was posted. |

- **Verdicts.** Each rubric returns `approve`, `request_changes` or `block`. The review's headline
  sums them up as `approved`, `changes requested` or `blocked`. A `block` halts the remaining
  rubrics in scoreboard mode (or with `--halt`); core mode runs every rubric by default.

## Troubleshooting

stderr names the cause after `no verdict:`.

| message | fix |
|---|---|
| `cli_outdated` (e.g. "version 2.1.280 or newer is required", "requires a newer version of Codex") | Update that CLI: `claude update`, or reinstall `codex`. Check that `which claude` points at the updated copy. |
| `not_authenticated` | Log that CLI in again interactively (run `claude`, then `/login`; or `codex login`). |
| `model_unavailable` | Your plan cannot use the default model. Pass one it can use: `--claude-model …` or `--codex-model …`. |
| `quota_exhausted` / `rate_limited` | The subscription window is used up. Wait, or use `--reviewer` to switch to another CLI. |
| `no_verdict`, `unknown_error`, `cli_error`, `unparseable_output`, `max_turns`, `execution_error` | The reviewer finished without a usable verdict. Retry that rubric once with `--rubrics <name>`. |
| `no reviewer CLI found on PATH` | Install and log into `claude` or `codex` (step 1). |
| `not inside a GitHub repository` | Pass `--repo owner/name`. |
| `could not read PR` | Check the number, and that `gh auth status` shows an account that can see the repository. |

A reviewer that is outdated, logged out, out of quota, or without access to its model is dropped
for the rest of the run, and its rubric goes to another installed reviewer if there is one.

## Notes for AI agents

If you are an AI agent asked to run lean-review, or to change this repository, follow
[AGENTS.md](AGENTS.md). It covers the step-by-step procedure, how to read the output, what to do
on each error, and the rules, such as never posting without the user's explicit consent.

## Configuring a project

Everything is optional. With no configuration, a project gets the built-in rubrics, its repo name
as the project name, and the Mathlib rev pinned in `lake-manifest.json`. To customise, commit
these to the target repository's **default branch**. They are always read from the PR's base
commit, never from the PR, so an author cannot rewrite their own review.

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

- **`.lean-review/common.md`** is appended to the shared protocol as *project notes*. Use it for
  house policy, such as a compatibility policy. Without one, reviewers follow Mathlib's deprecation
  practice.
- **`.lean-review/rubrics/<name>.md`** adds a new rubric, or replaces the built-in rubric of that
  name. List new rubrics in `rubrics`.

[`examples/tauceti/`](examples/tauceti/) is a complete example: a configuration for
[Tau Ceti](https://github.com/TauCetiProject/TauCeti), including its stricter compatibility policy and a project-specific `quality-pass` rubric that
checks the author's report from Tau Ceti's PR template.

## Profiles: formal-conjectures

A profile is a built-in layer of configuration, notes and rubrics for a kind of project. It sits
beneath the repository's own `.lean-review.toml`, so it also works for repositories whose default
branch you cannot add a config to. The one profile so far is `formal-conjectures`, for
[formal-conjectures](https://github.com/google-deepmind/formal-conjectures) and repositories laid
out like it: Lean statements of open conjectures, whose proofs are `sorry` by design.

It is chosen with `--profile formal-conjectures` or `profile = "formal-conjectures"`. It is also
chosen automatically, with a `note:` line, when the PR's base commit has `FormalConjecturesUtil/`.
Pass `--profile default` to opt out.

There the statement is the product, so the review concentrates on misformalization:

| rubric | runs | sessions | can block? |
|---|---|---|---|
| `faithfulness` | once per changed main statement (up to `--full-checks`, default 6) | 3 each | yes |
| `variant-faithfulness` | once per batch of up to 6 variants, textbook statements and further main statements | 2 each | yes |
| `reuse` | duplicates in Mathlib, `FormalConjecturesForMathlib/`, or the same problem stated elsewhere in the repository | 1 | yes |
| `definitions` | natural, general definitions, checked by test statements (first terms, with proofs where feasible) instead of API | 1 | no |
| `completeness` | the open problem itself, every part, and the known results the sources name | 1 | no |
| `metadata` | category vs status, `@[question]` / `.answer`, `formal_proof`, AMS, names, files | 1 | no |
| `documentation` | LaTeX docstrings that quote the source, references in the repository's format | 1 | no |
| `proof-quality` | proofs over 10 lines, proofs of open statements, `native_decide` | 1 | no |

A main statement is a changed `research open` or `research solved` theorem whose name has no
`.variants.` segment. Each one gets three sessions:

1. **Literal reading.** A session that sees the statement with every comment and docstring
   removed writes down what it literally asserts.
2. **Independent formalization.** A session that sees only the docstring writes its own Lean
   statement.
3. **Adjudication.** A session that sees the whole PR, both outputs and a misformalization
   checklist compares them, tries a quick proof and disproof, and blocks only with a witness.

Each blind step works in its own copy of the checkout: comments stripped from the changed files
for the first, the PR's new declarations removed for the second. Neither sees the PR description
or the diff. Variants get the reading and the adjudication only.

The design ports the strongest detectors of a study of formal-conjectures' historical
misformalizations. Reviewers cannot run Lean, so the study's mechanical checks are reduced to
hints, and the prove/disprove check is done by reasoning.
[`lean_review/profiles/formal-conjectures/`](lean_review/profiles/formal-conjectures/README.md) has
the details.

### Checking against the source

Reviewers have no network, so they cannot open the sources a PR cites. The profile therefore turns
on `sources`: before the review, the runner fetches each cited source into the checkout under
`.lean-review-sources/`, with an `INDEX.md` listing what it fetched and what it could not. Every
rubric is told it is there, and the faithfulness, metadata, completeness and documentation rubrics
check the docstrings, the statement and its category against the source's own text, not the
author's account of it.

| cited as | fetched |
|---|---|
| `erdosproblems.com/N`, or a file `ErdosProblems/N.lean` | the problem page as text, plus its entry (status, prize, tags) in the [erdosproblems database](https://github.com/teorth/erdosproblems) |
| an arXiv link or `arXiv:ID`, or a file under `Arxiv/ID/` | the paper's TeX source, else arXiv's HTML rendering |
| a file under `Kourovka/` | the latest Kourovka Notebook (arXiv 1401.0300) as TeX |
| `oeis.org/AN`, or a file `OEIS/N.lean` | the OEIS entry in its text format |
| `en.wikipedia.org/wiki/TITLE` | the article's wikitext |

Citations are looked for in the changed files and the PR description, up to 8 sources. The runner
never requests a URL the PR wrote: it keeps the identifier and builds the URL on the site's own
host. A source that fails to download is listed in `INDEX.md`, and reviewers are told to say when
they could not check against it. The blind stages do not see the sources. `--no-sources` turns
fetching off.

The rows of a review name the statement, e.g. `faithfulness · erdos_406`. A PR with 1 main
statement and 3 variants costs 3 + 2 + 6 = 11 sessions. `--full-checks 0` reviews every statement
the cheap way.

## Rubrics

The built-in rubrics are in [`lean_review/rubrics/`](lean_review/rubrics/). An agent's prompt is
assembled in this order:

1. `_common.md`, the shared protocol.
2. The project notes.
3. The PR context: diff, description and a trusted CI note.
4. The rubric file itself.

Everything before the rubric is the same for every rubric of a run, so Claude reviewers after the
first read it from the prompt cache instead of processing the whole PR again (with Claude Code
2.1.242 or newer). When the diff or the description is too long for the prompt, the reviewer is
told where it was cut, and the complete text is placed in the checkout under `.lean-review-pr/`
for it to read.

Placeholders such as `{{project}}` and `{{source_root}}` are filled from the configuration.

## How it stays honest

- **Clean room.** Each reviewer runs in a throwaway HOME holding only its own subscription
  credential, so your personal `CLAUDE.md`, `AGENTS.md`, skills, plugins and other credentials
  never reach it.
- **Read-only tools.** claude and kiro get only read, grep and glob: no shell, no writes, no web.
  Sources a PR cites are fetched by the runner, from URLs it builds itself, before any reviewer
  starts.
  codex runs in its own `read-only` sandbox. Its commands inherit no environment except `PATH`,
  which its Linux launcher needs to find the system `bwrap`, and a private temporary directory.
- **Unforgeable verdict.** The verdict is read only from after a fresh random marker. A
  ready-made `{"verdict": "approve"}` planted in the PR is ignored.

See [SECURITY.md](SECURITY.md).

## Cost and fair use

Each rubric is one agentic session on your subscription, typically 10–40 seconds with Claude Opus.
A full nine-rubric review uses about nine of them, and the first run with Mathlib also downloads
its source. Use `--rubrics` for quick checks.

Driving a personal subscription is fine for occasional reviews a person starts by hand, like
these. An always-on auto-reviewer is closer to API-tier usage and probably outside subscription
terms.

## Development

```bash
uv run --with pytest python -m pytest -q
```

## Credits

lean-review grew out of [TauCetiReview](https://github.com/TauCetiProject/TauCetiReview) by [@kim-em](https://github.com/kim-em), the
review engine of the Tau Ceti project, and keeps its rubrics and its security design. It was
inspired by [botbaki](https://github.com/kim-em/botbaki). Apache-2.0.
