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

## Prerequisites

- **Python** ≥ 3.11, `git`.
- **[`gh`](https://cli.github.com/)**, logged in with `gh auth login`. It reads the PR and, with
  `--post`, publishes as you. Private repositories work if your login can read them.
- **At least one reviewer CLI**, logged in:
  - [`claude`](https://www.npmjs.com/package/@anthropic-ai/claude-code) on a Claude subscription.
  - [`codex`](https://www.npmjs.com/package/@openai/codex) on a ChatGPT subscription.
  - `kiro-cli`, after `kiro-cli login`. Kiro is explicit-only: pass `--reviewer kiro`.

## Use

```bash
uvx --from git+https://github.com/felixpernegger/lean-review lean-review 42 --repo owner/name
# or: uv tool install git+https://github.com/felixpernegger/lean-review
lean-review 42                       # inside a clone: review PR #42 and print the result
lean-review 42 --post                # publish it to the PR as your gh login
lean-review 42 --rubrics correctness,reuse --reviewer claude
lean-review 42 --mode scoreboard --post
```

It **defaults to a dry run**: the review is printed and nothing is posted.

| flag | effect |
|---|---|
| `--post` | publish to the PR under your GitHub login |
| `--mode core\|scoreboard` | output style (see below); default from config, else `core` |
| `--rubrics a,b` | run only these rubrics, in this order |
| `--reviewer claude,codex,kiro` | restrict the reviewers. The default is every installed one of `claude` and `codex`, drawn at random per rubric |
| `--claude-model` / `--codex-model` / `--kiro-model` | exact model ids. Defaults: `claude-opus-5-5`, `gpt-6.1-sol`, `gpt-5.6-sol` |
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
  credential, so your `CLAUDE.md`, `AGENTS.md`, skills, plugins and other credentials never reach
  it.
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
