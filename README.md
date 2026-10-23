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
`CLAUDE.md`, settings, skills and MCP servers are not used. `gh`
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
`placement`, `naming`, `documentation`, `proof-quality`, plus any the project adds.

| flag | effect |
|---|---|
| `--post` | publish to the PR under your GitHub login |
| `--mode core\|scoreboard` | output style (see below); default from config, else `core` |
| `--rubrics a,b` | run only these rubrics, in this order |
| `--reviewer claude,codex,kiro` | restrict the reviewers. By default each rubric is given to one reviewer drawn at random from the installed `claude` and `codex`; the progress line shows which. Pass e.g. `--reviewer claude` for a single one |
| `--claude-model` | exact Claude model id; default `claude-opus-5-5` |
| `--codex-model` | exact Codex model id; default `gpt-6.1-sol` |
| `--kiro-model` | exact Kiro model id; default `gpt-5.6-sol`. `auto` is refused |
| `--repo owner/name` | the repository; defaults to the one the current directory is a clone of |
| `--no-mathlib` | skip fetching Mathlib source (faster; weaker `reuse`/`naming`) |
| `--no-halt` | keep reviewing after a rubric blocks. By default a `block` stops the round |
| `--rerun-all` | scoreboard mode: re-run rubrics that are already green at this head |
| `--config PATH` | use a local `.lean-review.toml` instead of the one on the PR's base branch |
| `--keep` | keep the temporary workspace |

### Modes

- **`core`** (default) posts one GitHub PR review (event `COMMENT`):
  - The body holds a verdict table with one row per rubric.
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

- **stdout** holds the review exactly as it would be posted (Markdown), followed by the inline
  comments in core mode. **stderr** holds progress, one `[rubric] reviewer → verdict` line per
  rubric, plus any errors.
- **Run time.** Each rubric takes about 10–60 seconds, so all nine take a few minutes. The first
  step also downloads the PR's code and, unless you pass `--no-mathlib`, the Mathlib source the
  project pins. That is usually under a minute, but slower on a slow connection. The tool is
  non-interactive and never prompts, so allow at least 30 minutes before treating a run as hung.
  When run through `uvx`, uv's own build messages appear on stderr first.
- **Disk.** Everything is downloaded into a fresh temporary directory, which is deleted when the
  run ends (`--keep` keeps it and prints its path). Each reviewer's throwaway HOME lives under
  `~/.lean-review-rev/` and is removed as soon as that reviewer finishes. Nothing else persists,
  apart from uv's or pipx's own package cache.
- **Exit status:**

  | status | meaning |
  |---|---|
  | 0 | The review completed and was printed (and posted with `--post`). A `blocked` or `changes requested` verdict still exits 0. Read the verdict from the output. |
  | 1 | A usage or setup error, or posting failed. The message on stderr says which. |
  | 3 | No rubric produced a verdict, typically because every reviewer CLI is logged out, outdated, or out of quota. Nothing was posted. |

- **Verdicts.** Each rubric returns `approve`, `request_changes` or `block`. The review's headline
  sums them up as `approved`, `changes requested` or `blocked`. A `block` halts the remaining
  rubrics unless `--no-halt` is given.

## Troubleshooting

stderr names the cause after `no verdict:`.

| message | fix |
|---|---|
| `cli_outdated` (e.g. "version 2.1.280 or newer is required", "requires a newer version of Codex") | Update that CLI: `claude update`, or reinstall `codex`. Check that `which claude` points at the updated copy. |
| `not_authenticated` | Log that CLI in again interactively (run `claude`, then `/login`; or `codex login`). |
| `model_unavailable` | Your plan cannot use the default model. Pass one it can use: `--claude-model …` or `--codex-model …`. |
| `quota_exhausted` / `rate_limited` | The subscription window is used up. Wait, or use `--reviewer` to switch to another CLI. |
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
ci_check    = "build"          # if this check passed on the head, reviewers are told the build is green
```

- **`.lean-review/common.md`** is appended to the shared protocol as *project notes*. Use it for
  house policy, such as a compatibility policy. Without one, reviewers follow Mathlib's deprecation
  practice.
- **`.lean-review/rubrics/<name>.md`** adds a new rubric, or replaces the built-in rubric of that
  name. List new rubrics in `rubrics`.

[`examples/tauceti/`](examples/tauceti/) is a complete example: a configuration for
[Tau Ceti](https://github.com/TauCetiProject/TauCeti), including its stricter compatibility policy.

## Rubrics

The built-in rubrics are in [`lean_review/rubrics/`](lean_review/rubrics/). An agent's prompt is
assembled in this order:

1. `_common.md`, the shared protocol.
2. The project notes.
3. The rubric file itself.
4. The PR context: diff, description and a trusted CI note.

Placeholders such as `{{project}}` and `{{source_root}}` are filled from the configuration.

## How it stays honest

- **Clean room.** Each reviewer runs in a throwaway HOME holding only its own subscription
  credential, so your personal `CLAUDE.md`, `AGENTS.md`, skills, plugins and other credentials
  never reach it.
- **Read-only tools.** claude and kiro get only read, grep and glob: no shell, no writes, no web.
  codex runs in its own `read-only` sandbox with an empty environment.
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

lean-review grew out of [TauCetiReview](https://github.com/TauCetiProject/TauCetiReview), the
review engine of the Tau Ceti project, and keeps its rubrics and its security design. It was
inspired by [botbaki](https://github.com/kim-em/botbaki). Apache-2.0.
