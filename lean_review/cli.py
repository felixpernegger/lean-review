"""`lean-review`: review a Lean 4 PR with the reviewer CLIs you are logged into.

    lean-review 42                      # review PR #42 of the current directory's repo; print only
    lean-review 42 --repo owner/name --post
"""

import argparse, pathlib, shutil, subprocess, sys, tempfile

from . import config, engine, post, render, reviewers, state, workspace
from .verdict import has_new_contest, newest_reply_id, overall_label, posts_review_thread, state_of

PROVIDERS_DOWN_EXIT = 3


def die(msg):
    print(f"lean-review: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="lean-review", description=__doc__.split("\n\n")[0])
    ap.add_argument("pr", type=int, help="pull request number")
    ap.add_argument("--repo", help="owner/name (default: the current directory's GitHub repo)")
    ap.add_argument("--config", help="local .lean-review.toml to use instead of the one on the "
                                     "PR's base branch")
    ap.add_argument("--mode", choices=config.MODES, help="core (one PR review; default) or "
                                                          "scoreboard (stateful board + threads)")
    ap.add_argument("--rubrics", help="comma-separated rubrics to run (default: the config's)")
    ap.add_argument("--reviewer", help="comma-separated subset of claude,codex,kiro "
                                       "(default: every installed one of claude,codex)")
    ap.add_argument("--claude-model", default=reviewers.DEFAULT_MODELS["claude"])
    ap.add_argument("--codex-model", default=reviewers.DEFAULT_MODELS["codex"])
    ap.add_argument("--kiro-model", default=reviewers.DEFAULT_MODELS["kiro"])
    ap.add_argument("--no-mathlib", action="store_true", help="skip the Mathlib source checkout")
    halting = ap.add_mutually_exclusive_group()
    halting.add_argument("--halt", action="store_true",
                         help="stop at the first rubric that blocks (default in scoreboard mode)")
    halting.add_argument("--no-halt", action="store_true",
                         help="run every rubric even after one blocks (default in core mode)")
    ap.add_argument("--rerun-all", action="store_true",
                    help="scoreboard mode: re-run every rubric, including ones green at this head")
    ap.add_argument("--post", action="store_true", help="publish to the PR as your gh login")
    ap.add_argument("--keep", action="store_true", help="keep the temporary workspace")
    return ap.parse_args(argv)


def pick_providers(arg):
    have = reviewers.available()
    wanted = [p.strip() for p in arg.split(",") if p.strip()] if arg else list(reviewers.AUTO_PROVIDERS)
    unknown = set(wanted) - set(reviewers.PROVIDERS)
    if unknown:
        die(f"unknown reviewer(s): {', '.join(sorted(unknown))}")
    chosen = [p for p in wanted if p in have]
    if not chosen:
        die("no reviewer CLI found on PATH: install and log into `claude` (Claude Code) or `codex`"
            " (or pass --reviewer kiro with `kiro-cli`)")
    missing = [p for p in wanted if p not in have]
    if arg and missing:
        die(f"requested reviewer(s) not on PATH: {', '.join(missing)}")
    return chosen


def load_config(a, repo, base):
    try:
        cfg = config.load_local(a.config) if a.config else config.load_remote(repo, base)
        if a.mode:
            cfg.mode = a.mode
        if a.rubrics:
            cfg.rubrics = [r.strip() for r in a.rubrics.split(",") if r.strip()]
        if a.no_mathlib:
            cfg.mathlib = False
        cfg.project = cfg.project or repo.split("/")[1]
        config.validate(cfg)
        for r in cfg.rubrics:
            cfg.rubric_text(r)
    except config.ConfigError as e:
        die(str(e))
    return cfg


def should_halt(a, cfg):
    """Core mode is a one-off review, so it runs every rubric unless told otherwise. Scoreboard
    mode stops at a block by default: a later run picks up the rest once the block is fixed."""
    if a.halt or a.no_halt:
        return a.halt
    return cfg.mode == "scoreboard"


def select_scoreboard_queue(cfg, state_map, head, rerun_all):
    """Rubrics to run this invocation: everything not green at `head`, except an adverse verdict
    already judged at this exact head with no new author reply (re-running it would only
    reproduce it), plus every rubric with a new contest."""
    queue = []
    for r in cfg.rubrics:
        cf = state_map.get(r)
        s = state_of(cf, head)
        if rerun_all or has_new_contest(cf):
            queue.append(r)
        elif s == "green":
            continue
        elif s in ("blocking_request", "blocking_block") and cf.get("reviewed_sha") == head:
            continue
        else:
            queue.append(r)
    return queue


def publish_scoreboard(cfg, ws, state_map, ran, contested, overall, board_id):
    me = post.current_login()
    if not me:
        die("could not determine your GitHub login (`gh auth status`)")
    failures = []
    roots = [c for c in (post.gh_paginate(f"/repos/{ws.repo}/pulls/{ws.pr}/comments?per_page=100")
                         or []) if c.get("in_reply_to_id") is None]
    fallback = ws.changed[0] if ws.changed else ""
    for r in cfg.rubrics:
        cf = state_map.get(r)
        if not cf:
            continue
        s = state_of(cf, ws.head)
        thread = cf.get("thread") or {}
        if posts_review_thread(s) and r in ran and fallback:
            path = state.pick_anchor(cf, fallback, set(ws.changed))
            post.upsert_thread(ws.repo, ws.pr, ws.head, cf, render.render_thread(cf, ws), path, me,
                               roots, failures)
        elif s == "green" and thread.get("comment_id") and not thread.get("resolved"):
            post.resolve_thread(ws.repo, ws.pr, thread["comment_id"])
            thread["resolved"] = True
        if r in contested and cf.get("author_replies"):
            root = max(cf["author_replies"], key=lambda x: x["id"])["root_id"]
            post.reply_in_thread(ws.repo, ws.pr, root, render.render_contest_reply(cf, ws.head),
                                 failures)
    body = render.render_scoreboard(cfg.rubrics, state_map, ws, overall, state.compact(state_map))
    if not post.upsert_scoreboard(ws.repo, ws.pr, body, board_id, me, failures):
        failures.append("scoreboard")
    return failures


def main(argv=None):
    a = parse_args(argv)
    for tool in ("git", "gh"):
        if not shutil.which(tool):
            die(f"`{tool}` not found on PATH")
    providers = pick_providers(a.reviewer)
    models = {"claude": a.claude_model, "codex": a.codex_model, "kiro": a.kiro_model}
    if "kiro" in providers:
        try:
            reviewers.exact_kiro_model(a.kiro_model)
        except ValueError as e:
            die(str(e))
    repo = a.repo
    if not repo:
        r = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                           text=True, capture_output=True)
        repo = r.stdout.strip() if r.returncode == 0 else ""
        if not repo:
            die("not inside a GitHub repository; pass --repo owner/name")
    reviewers.sweep_rev_homes()

    work = pathlib.Path(tempfile.mkdtemp(prefix="lean-review-"))
    try:
        try:
            head, base = workspace.pr_refs(repo, a.pr)
        except (RuntimeError, ValueError, KeyError) as e:
            die(f"could not read PR #{a.pr} of {repo}: {e}")
        cfg = load_config(a, repo, base)
        print(f"reviewing {repo}#{a.pr} @ {head[:12]} — mode {cfg.mode}, reviewers "
              f"{', '.join(providers)}", file=sys.stderr)
        try:
            ws = workspace.build(repo, a.pr, work, mathlib=cfg.mathlib, ci_check=cfg.ci_check)
        except RuntimeError as e:
            die(str(e))
        if not cfg.source_root:
            name = repo.split("/")[1]
            cfg.source_root = name if (ws.root / name).is_dir() else "."
        context = workspace.base_context(ws, cfg.source_root)
        version = state.rubrics_version(cfg)
        digest = state.patch_digest(ws.diff_text)

        board_id, state_map, replies, contested = None, {}, {}, set()
        queue = list(cfg.rubrics)
        if cfg.mode == "scoreboard":
            me = post.current_login()
            comments = post.gh_paginate(f"/repos/{repo}/issues/{a.pr}/comments?per_page=100") or []
            board_id, state_map = state.load_board(comments, me)
            thread_replies = state.thread_replies(
                post.gh_paginate(f"/repos/{repo}/pulls/{a.pr}/comments?per_page=100") or [])
            for r, reps in thread_replies.items():
                if r in state_map:
                    state_map[r]["author_replies"] = reps
            contested = {r for r in cfg.rubrics if has_new_contest(state_map.get(r))}
            replies = {r: max(state_map[r]["author_replies"], key=lambda x: x["id"])["body"]
                       for r in contested}
            carried = state.carry_forward(state_map, ws.head, digest, version)
            if carried:
                print(f"carried approvals (patch unchanged): {', '.join(carried)}", file=sys.stderr)
            queue = select_scoreboard_queue(cfg, state_map, ws.head, a.rerun_all)

        try:
            ran, halted = engine.run_queue(cfg, ws, queue, providers, models, state_map, context,
                                           digest=digest, version=version, replies=replies,
                                           halt=should_halt(a, cfg))
        except engine.ProvidersDown as e:
            print(f"lean-review: {e}; nothing posted", file=sys.stderr)
            return PROVIDERS_DOWN_EXIT
        if ran and all(state_map[r]["verdict"] == "error" for r in ran):
            print("lean-review: no rubric produced a verdict; nothing posted", file=sys.stderr)
            return PROVIDERS_DOWN_EXIT
        for r in contested & set(ran):
            state_map[r]["last_reply_seen"] = newest_reply_id(state_map[r])

        overall = overall_label([state_of(state_map.get(r), ws.head) for r in cfg.rubrics], halted)
        if cfg.mode == "core":
            body, comments = render.render_core_review(cfg.rubrics, state_map, ws, overall)
            print(body)
            for c in comments:
                print(f"\n--- inline {c['path']}:{c['line']}\n{c['body']}")
            if a.post:
                failures = []
                if post.post_review(repo, a.pr, ws.head, body, comments, failures) is None:
                    die("posting the review failed")
                print(f"\nposted the review to {repo}#{a.pr}", file=sys.stderr)
        else:
            print(render.render_scoreboard(cfg.rubrics, state_map, ws, overall, {}))
            for r in cfg.rubrics:
                cf = state_map.get(r)
                if cf and posts_review_thread(state_of(cf, ws.head)):
                    print("\n---\n" + render.render_thread(cf, ws))
            if a.post:
                failures = publish_scoreboard(cfg, ws, state_map, ran, contested, overall, board_id)
                if failures:
                    die("publication incomplete: " + ", ".join(failures))
                print(f"\nposted the scoreboard to {repo}#{a.pr}", file=sys.stderr)
            elif not ran:
                print("\nnothing to re-run at this head", file=sys.stderr)
        if not a.post:
            print("\n(dry run: nothing posted; pass --post to publish)", file=sys.stderr)
        return 0
    finally:
        if a.keep:
            print(f"workspace kept at {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
