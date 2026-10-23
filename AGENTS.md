# AGENTS.md

Instructions for AI agents. Part A is for running lean-review on a user's behalf. Part B is for
changing this repository. [README.md](https://github.com/felixpernegger/lean-review/blob/main/README.md) has the full flag table and configuration
reference.

---

# Part A: running lean-review for a user

lean-review reviews one GitHub pull request of a Lean 4 project. It runs several rubrics, each
judged by a reviewer CLI (`claude`, `codex` or `kiro-cli`) on the user's own logged-in
subscription. It prints the review, and only with `--post` publishes it to the PR under the
user's GitHub account.

## Ground rules

1. **Never pass `--post` unless the user explicitly asked to publish.** Posting is visible to
   other people and appears under the user's name. When unsure, run without it and ask.
2. **Never supply or ask for API keys or tokens.** lean-review uses only the CLIs' own
   interactive logins. Keys are ignored.
3. **Ask before changing the user's system.** That includes installing tools, running
   `claude update`, upgrading codex and logging in. Logins need the human anyway, since they open
   a browser.
4. **Spend quota deliberately.** Each rubric uses one session of the user's subscription. Don't
   re-run full reviews in a loop. Use `--rubrics` for quick checks.
5. **Don't modify the target repository.** No commits, no `.lean-review.toml`, no comments, unless
   the user asks.
6. **When this file says "ask" but no human can answer,** take the cautious option: don't post,
   don't install, don't update. Follow an explicit instruction in the request, and report what you
   would have asked.

## Step 1: translate the request into arguments

| The user says… | Argument |
|---|---|
| a PR URL `https://github.com/OWNER/NAME/pull/N` | `N --repo OWNER/NAME` |
| "PR 42" while you are inside a clone of the target repo | `42` (`--repo` is inferred) |
| a subset of angles ("just check naming and docs") | `--rubrics naming,documentation` |
| "quick" or "cheap" | add `--no-mathlib`, and possibly a single rubric. That is fine for `naming`, `documentation`, `proof-quality`, `attribution` and `correctness`. Keep Mathlib (omit `--no-mathlib`) when `reuse` runs, because finding duplicates relies on grepping it. |
| "what's wrong with it", "is it ready to merge", "full review", "list all problems" | nothing extra in core mode, which runs every rubric. In scoreboard mode add `--no-halt`, since it otherwise stops at the first rubric that blocks |
| "stop at the first blocker", "save quota" | `--halt` |
| "post it", "publish", "leave a review on the PR" | `--post`, see step 5 |
| "post it **if** it finds problems", "only post if it isn't clean" | `--post-unless-approved` (core mode): one run that posts only when some rubric did not approve |
| "keep a running scoreboard", "update the review after my fixes" | `--mode scoreboard` |
| "use Claude only" / "use Codex" | `--reviewer claude` / `--reviewer codex` |

Rubric names: `correctness`, `reuse`, `attribution`, `api-design`, `generality`, `placement`,
`naming`, `documentation`, `proof-quality`. A project may add its own. With no `--rubrics`, all
the project's rubrics run in that order.

## Step 2: preflight

Run each check as its own command, not chained with `&&` (an absent optional tool would make the
whole line fail), and act on the result:

| Check | Expected | If not |
|---|---|---|
| `python3 --version` | ≥ 3.11 | Ask the user to install a newer Python. |
| `gh auth status` | logged in | Ask the user to run `gh auth login`. Note the account name: posts appear under it. |
| `gh repo view OWNER/NAME --json name` | succeeds | The account cannot see the repository. Check the name, or ask the user. |
| `command -v claude`, then `claude --version` | ≥ 2.1.280 | Ask the user to run `claude update`, or to install Claude Code. Only the first path that `command -v claude` prints is used; others listed by `which -a claude` don't matter. |
| `command -v codex` | optional | Missing is fine if `claude` works. Its version can't be checked reliably (`codex --version` may print nothing), so don't gate on it. An outdated codex, or one whose plan lacks the model, is detected and dropped during the run, and the rubric goes to claude. Mention it to the user. |
| `command -v lean-review` | found | Use the `uvx` form below, or ask before `uv tool install …`. |
| `command -v uv` (then `command -v pipx` only if uv is missing) | one of them | Needed only if `lean-review` is not installed. |

You need at least one working reviewer CLI. Version checks don't prove the CLI is logged in. The
first real run does.

## Step 3: run it

Run without a posting flag (a dry run) unless the user's request already asked to publish; see
step 5.

If `lean-review` is installed:

```bash
lean-review N --repo OWNER/NAME [--rubrics …] [--no-mathlib] > review.md 2> progress.log
```

Without installing, put the `uvx` prefix in front. This does **not** count as installing: it adds
nothing to PATH and changes no configuration. uv only keeps a cached copy of the package in its
own cache directory (`uv cache dir`), so it is the right choice when the user doesn't want
software installed:

```bash
uvx --from git+https://github.com/felixpernegger/lean-review lean-review N --repo OWNER/NAME … > review.md 2> progress.log
```

- **Where to write.** Put `review.md` and `progress.log` in a scratch or temporary directory of
  your choice, not inside the user's repositories.
- **Time limits.** A single rubric takes 10–60 s, and all nine take a few minutes, plus the
  Mathlib download. If your shell tool allows a timeout of at least 30 minutes, run in the
  foreground with that timeout. If its maximum is shorter, run it in the background, so that
  the exit status is written to a file even when the run fails:

  ```bash
  ( lean-review N --repo OWNER/NAME … > review.md 2> progress.log; echo $? > exit.txt )
  ```

  Prefer your shell tool's own background option for this command. If you append `&` instead,
  the tool reports the command finished immediately, with exit 0, while lean-review is still
  running. Either way, **only `exit.txt` tells you the run is over and how it ended.** Wait until
  it exists, with your tool's wait or monitor feature, or a polling loop such as
  `until [ -f exit.txt ]; do sleep 15; done` (repeat it if your tool's timeout cuts it short). A full nine-rubric run can take 5–15 minutes. The tool never prompts for input.
- **Run from anywhere.** You don't need a clone unless you rely on `--repo` being inferred.
- **No leftovers.** Everything goes into a temporary directory that is deleted afterwards
  (`--keep` keeps it). Nothing needs cleaning up.

## Step 4: read the result

**Exit status:**

| status | meaning | what to do |
|---|---|---|
| 0 | The review completed. | Read `review.md`. A `blocked` or `changes requested` headline is a *successful* run that found problems. |
| 1 | A setup error or posting failure. | Read the `lean-review: …` line in `progress.log` and fix it (see the table below). |
| 3 | No rubric produced a verdict. Nothing was posted. | Read the `no verdict:` lines in `progress.log`. |

**progress.log (stderr)**:
- one `reviewing OWNER/NAME#N @ <sha> — mode …, reviewers …` header line. It lists the
  reviewers *available* to this run; each rubric uses one of them, so a listed reviewer may never
  be tried. Every run starts fresh, so a reviewer dropped in an earlier run is listed again.
- `fetching OWNER/NAME @ <sha>…`, then `fetching Mathlib source @ <rev>…` when Mathlib is used.
  It is not used with `--no-mathlib`, when the project's config sets `mathlib = false`, or when
  the base `lake-manifest.json` pins no Mathlib (which prints a `note:` line instead). **No
  `fetching Mathlib` line means Mathlib was not used**, so `reuse` and `naming` could not grep it.
  Mention this when those rubrics ran.
- per rubric, `[rubric] reviewing with <cli>…`, then `[rubric] <cli>/<model> → <verdict> (<s>)`.
  `<verdict>` is `approve`, `request_changes`, `block`, or `error`, where `error` means that
  attempt produced no verdict.
- after an `error`, `[rubric]   no verdict: <kind> — <the CLI's own message>`. If the reviewer was
  unusable, a `dropping <cli> for the rest of this run` line follows, and the rubric is retried
  with another reviewer, which prints its own `reviewing with` line. Only the last line for a
  rubric is its result.
- when run through `uvx`, uv's build lines come first
- at the end, exactly one of:
  - `(dry run: nothing posted; pass --post to publish)`: no posting flag was given
  - `posted the review to OWNER/NAME#N as <login>: <url>`: posted (scoreboard mode: `posted the
    scoreboard to …: <url>`)
  - `every rubric approved; nothing posted (--post-unless-approved)`
  - `not posted: <login> already posted a lean-review review of this head: <url> …`: a review of
    this exact commit by the same account already exists, for example from an earlier or
    concurrent run. That is a success, and it fulfils a request to post: the review the user asked
    for is on the PR. Report the existing URL. Pass `--repost` only if the user explicitly wants a
    second copy.

**review.md (stdout), core mode:**
- A first line `<!--lean-review:review-->`: a hidden marker, ignore it.
- A headline `## lean-review — <overall>`, where `<overall>` is one of `approved`, `changes
  requested`, `blocked`, `pending` (some rubric has not run yet), `re-review pending`
  (scoreboard mode: approvals from an earlier commit still need re-checking) or `partial`. If a block stopped the run early, it says so: `(halted
  at a block; X and later not run)`.
- A table with one row per rubric: icon, rubric, verdict, reviewer, one-paragraph summary.
- Optionally `### Findings outside the diff`, one bullet per finding.
- One `--- inline path:line` block per finding that will be attached to a changed line.
- A `<sub>Reviewed head … · diff · lean-review <version></sub>` footer, followed by a hidden
  `<!--lean-review:meta …-->` line. The footer is for readers; ignore the meta line.

**review.md, scoreboard mode:** the scoreboard, then `---` and one thread body per blocking
rubric.

**No-verdict kinds:**

| kind | cause | fix |
|---|---|---|
| `cli_outdated` | the CLI is too old for the model | Ask the user to update it (`claude update`, or reinstall codex). |
| `not_authenticated` | the CLI is logged out | Ask the user to log in (`claude`, then `/login`; or `codex login`). |
| `model_unavailable` | the plan cannot use the default model (claude: `claude-opus-5-5`; codex: `gpt-6.1-sol`; kiro: `gpt-5.6-sol`) | lean-review can't list a plan's models. If another reviewer covered the rubric, nothing is needed. Otherwise use `--reviewer` to pick one that works, or ask the user which model their plan offers and pass `--claude-model …` / `--codex-model …`. |
| `quota_exhausted`, `rate_limited` | the subscription limit was hit | Wait, or use `--reviewer` to switch to another installed CLI. |
| `no_verdict`, `unknown_error` | the reviewer answered without the required verdict | Retry that rubric once with `--rubrics <name>`. |

Outdated, logged-out, quota-exhausted and model-unavailable reviewers are dropped for the rest of
the run automatically. Their rubric goes to another installed reviewer.

## Step 5: report, then post only on request

1. Give the user the headline, each rubric's verdict, and the findings, including file and line.
   If a rubric approved with no findings, say so. If progress.log shows a reviewer was dropped,
   say which one and why, because the verdicts then come from the remaining reviewer only. Don't
   paste the hidden meta line.
2. **If the headline says `halted at a block`**, the rubrics after the blocking one never ran.
   Say so plainly: the PR is not ready to merge, and the list of problems is incomplete. If the
   user wants everything that is wrong, run again with `--no-halt`. A halt happens by default
   only in scoreboard mode, or when `--halt` was passed. Any headline without `(halted …)`,
   including `blocked`, means every requested rubric ran.
3. **Posting.**
   - **When the user asked to post in the original request,** one run is enough: `--post`, or
     `--post-unless-approved` when posting depends on the result ("post it if it finds
     problems"). The run prints the same review it posts, so a separate dry run would only spend
     quota and produce a slightly different text.
   - **When the user asks to post after seeing a dry run,** run the same command again with
     `--post`. The review is regenerated, and wording or borderline verdicts can differ from the
     dry run. Report what was actually posted, from the new output.
   - **The account.** Posts appear under the account `gh auth status` showed. A git user name that
     differs from the GitHub login is normal and is no reason to stop. Name the account in your
     report. Ask before posting only if you have a concrete reason to think the account belongs
     to someone other than the user.
4. **Report the URL** from the `posted …` (or `not posted: … already posted …`) line in
   progress.log. That line is the confirmation; no separate check is needed. Other people's
   reviews on the PR do not affect it.

## Scoreboard mode

- **Where state lives.** The board stores its state in hidden JSON in the user's own board
  comment.
- **Running it again.**
  - It re-reviews only rubrics that are not yet approved at the current head.
  - A rubric already judged adverse at this head is not re-run. Use `--rerun-all` to force it.
  - An approval carries over when a new commit leaves the patch unchanged, as after a rebase.
- **Contesting.** A human contests a finding by replying in that rubric's review thread. The next
  run re-reviews only that rubric and answers in the thread.

## Configuring a project, if the user asks

Configuration is read from the PR's **base** commit, so it must be committed to the target
repo's default branch to take effect. For one run you can test it locally with
`--config path/to/.lean-review.toml`. The format is in [README.md](https://github.com/felixpernegger/lean-review/blob/main/README.md#configuring-a-project).
[`examples/tauceti/`](https://github.com/felixpernegger/lean-review/blob/main/examples/tauceti/) is a complete example.

---

# Part B: working on this repository

## Layout

| Path | Role |
|---|---|
| `lean_review/cli.py` | argument parsing, orchestration, choosing the scoreboard queue |
| `lean_review/config.py` | `.lean-review.toml` and overlays, read from the base commit; `{{placeholder}}` and `<!-- if key -->` templating |
| `lean_review/workspace.py` | PR metadata, the checkout at head (no `.git`, escaping symlinks removed), Mathlib at the base-pinned rev, the shared prompt context |
| `lean_review/pr_diff.py` | three-dot diff via a bounded, credential-free bare git fetch |
| `lean_review/reviewers.py` | claude/codex/kiro runners, clean-room HOME, prompt assembly, error classification |
| `lean_review/engine.py` | the rubric loop: retry, reviewer fallback, halt on block |
| `lean_review/verdict.py` | marker-gated verdict parsing, state rules |
| `lean_review/state.py` | scoreboard case files, patch digest, carry-forward, thread replies |
| `lean_review/render.py` | all posted Markdown, sanitising, hidden meta |
| `lean_review/post.py` | `gh api` publishing |
| `lean_review/rubrics/` | the shipped prompts: `_common.md` plus one file per rubric |
| `tests/` | pytest, with no network and no reviewer CLIs needed |

## Commands

```bash
uv run --with pytest python -m pytest -q      # must pass before any commit
uv run lean-review N --repo OWNER/NAME --rubrics proof-quality --no-mathlib   # live smoke test
```

The live smoke test uses the user's subscription, so ask before running it.

## Invariants that must not regress

Tests cover most of these. Keep them that way.

- **Reviewer isolation.**
  - Read-only tools only: claude `--tools Read Grep Glob`, codex `-s read-only`, kiro
    `--trust-tools=read,grep,glob`.
  - A throwaway HOME holding only that provider's login.
  - No API keys, and no `GH_TOKEN` or `gh` credential, in a reviewer's environment.
- **Verdict channel.** Parse verdicts only from after the one-time marker, and fail closed. A run
  the CLI reports as failed is never a verdict.
- **Trusted inputs.**
  - Config, overlays and the Mathlib pin come from the PR's base commit, never the head.
  - Scoreboard state is read only from a comment by the operator's own login.
  - Only the operator's own comments are edited or deleted.
- **Rendering safety.** Model text passes through `render.sanitize`. Hidden meta escapes `<` and
  `>`.
- **Packaging.** No Python dependencies. Python 3.11+. Rubrics ship as package data. A new
  rubric file lands in the wheel automatically through the glob in `pyproject.toml`.
- **Rubric prompts stay project-agnostic.** No project names or roadmap references; use
  placeholders. `tests/test_prompt.py` checks this.

## Style

Match the surrounding code: compact modules, docstrings that explain *why*, few comments.
Keep the README, this file and `--help` in sync whenever flags, defaults, exit codes or output
formats change.
