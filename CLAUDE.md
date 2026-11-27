# CLAUDE.md

Instructions for changing this repository. They apply to every AI agent, not only Claude.

To run lean-review on a pull request for a user, first read Part A of [AGENTS.md](AGENTS.md).
Never pass `--post` unless the user explicitly asked to publish.

## Layout

| Path | Role |
|---|---|
| `lean_review/cli.py` | argument parsing, orchestration, choosing the scoreboard queue |
| `lean_review/config.py` | `.lean-review.toml` and overlays, read from the base commit; `{{placeholder}}` and `<!-- if key -->` templating |
| `lean_review/workspace.py` | PR metadata, the checkout at head (no `.git`, escaping symlinks removed), Mathlib at the base-pinned rev, the shared prompt context |
| `lean_review/pr_diff.py` | three-dot diff via a bounded, credential-free bare git fetch |
| `lean_review/reviewers.py` | claude/codex runners, clean-room HOME, prompt assembly (rubrics and blind stages), error classification |
| `lean_review/engine.py` | the rubric loop: retry, reviewer fallback, halt on block, blind stages before a per-statement unit |
| `lean_review/sources.py` | the sources a PR cites: recognised by pattern, fetched from URLs built on fixed hosts, staged with an `INDEX.md` |
| `lean_review/statements.py` | changed declarations from the diff, per-statement units (`rubric:target`), junk-value hints |
| `lean_review/verdict.py` | marker-gated verdict parsing, state rules |
| `lean_review/state.py` | scoreboard case files, patch digest, carry-forward, thread replies |
| `lean_review/render.py` | all posted Markdown, sanitising, hidden meta |
| `lean_review/post.py` | `gh api` publishing |
| `lean_review/rubrics/` | the shipped prompts: `_common.md` plus one file per rubric |
| `lean_review/profiles/<name>/` | built-in profiles: `profile.toml`, notes (`common.md`), rubrics, blind-stage prompts, references |
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
  - Read-only tools only: claude `--tools Read Grep Glob`, codex `-s read-only`.
  - A throwaway HOME holding only that provider's login. Claude's is one path per process,
    wiped before and after each attempt, so the prompt cache keeps working.
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
- **Cacheable prompt prefix.** The context passed to `build_prompt` is identical for every rubric
  of a run. Anything rubric-specific (the reactivation block) goes in `rubric_context`, after the
  rubric text. `tests/test_prompt.py` checks this.
- **Rubric prompts stay project-agnostic.** No project names or roadmap references; use
  placeholders. `tests/test_prompt.py` checks this. Prompts under `profiles/` are for one kind of
  project and may name its layout and conventions.
- **Fetched sources come from URLs the runner builds.** `sources.py` keeps only an identifier from
  a citation and builds the URL on a fixed host; it never requests a URL from the PR. Archives are
  read in memory and only their text members written, flattened. The sources directory is dropped
  from the blind copies. `tests/test_sources.py` and `tests/test_workspace.py` check this.
- **Blind stages stay blind.** A stage prompt carries neither the shared protocol nor the PR block.
  The literal reading sees the statement with comments stripped. The independent formalization
  sees only the docstring. Each runs in its own blind copy of the checkout
  (`workspace.build_blind`), which is hard-linked, and every file rewritten in it is unlinked
  first. `tests/test_prompt.py` and `tests/test_workspace.py` check this.

## Style

Match the surrounding code: compact modules, docstrings that explain *why*, few comments.
Keep the README, AGENTS.md and `--help` in sync whenever flags, defaults, exit codes or output
formats change.
