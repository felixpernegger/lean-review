# Security model

lean-review runs on a trusted person's machine, on their own logged-in reviewer subscriptions and
their own `gh` login. The PR it reviews (diff, description, comments, file contents) is
**attacker-controlled**, and every reviewer is assumed to be prompt-injected. The design does not
try to prevent injection, which no wording can. Instead, an injected reviewer has nothing worth
stealing and no way to publish or approve on its own authority.

## Mitigations

- **Configuration comes from the base commit.** `.lean-review.toml`, the project notes and rubric
  overlays are read at the PR's base commit, as is the Mathlib pin in `lake-manifest.json`. The PR
  head never supplies them.
- **Nothing from the PR is executed.**
  - The diff is built in a bare repository with an allowlisted environment and no user or system
    git config, so the PR's `.gitattributes` cannot hide a change.
  - The PR head is checked out without `.git`.
  - Symlinks that resolve outside the checkout are deleted before any reviewer starts.
- **Clean-room reviewers.**
  - Each reviewer process gets a throwaway HOME seeded with only its own subscription credential.
    It never receives the other providers' credentials, a GitHub token, or an API key from the
    operator's environment.
  - If a credential cannot be found (for example a macOS keychain login), the run falls back to
    the real HOME and says so.
- **Read-only tools.**
  - claude: `--tools Read Grep Glob`. Without `--tools` the shell would stay available.
  - codex: a `read-only` sandbox with `shell_environment_policy.inherit=none`.
  - kiro: trusted tools `read,grep,glob`.
- **Unforgeable verdict.**
  - A verdict is parsed only from after a fresh random marker. Parsing fails closed on a missing
    marker, malformed JSON or an out-of-set verdict.
  - A run the CLI itself reports as failed is never treated as a review.
- **Publication runs after the reviewers.** Posting happens through `gh` only after every reviewer
  has exited. Model text is sanitised before it is rendered, so HTML comments are stripped and a
  reviewer cannot forge a lean-review marker. The hidden state JSON escapes `<` and `>`.
- **State is read only from our own comment.** In scoreboard mode, state is read only from a
  scoreboard authored by the operator's own login. Only comments by that login are ever edited or
  deleted.

## Residual risks

- **R1: prompt injection is not eliminable.** An injected reviewer can still produce a wrong
  verdict. The operator reads the output before passing `--post`. A posted review is advisory and
  carries the operator's name.
- **R2: a reviewer can read its own subscription credential**, which its CLI needs in order to
  work, from the clean-room HOME. Its tools give it no shell and no network to send the credential
  out, but the model's own answer is published. Treat any credential echoed in a review as leaked
  and revoke it.
- **R3: the Mathlib checkout is large and fetched by SHA from GitHub.** A tampered pin on the base
  branch is a maintainer problem, not a PR-author problem.
