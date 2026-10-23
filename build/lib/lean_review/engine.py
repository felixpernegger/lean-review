"""Run the selected rubrics against a workspace, one at a time."""

import random, secrets, sys, time

from . import reviewers
from .reviewers import PROVIDER_DOWN_KINDS, build_prompt, cleanup_rev_home, error_kind, reviewer_env
from .state import build_reactivation_block, normalize_finding_path, update_case_file
from .verdict import extract_verdict


class ProvidersDown(Exception):
    """Every configured reviewer failed for a reason the next rubric would hit too."""


def run_rubric(cfg, rubric, provider, model, cwd, context, prior=None, reply_text=None):
    """One rubric on one reviewer, with one retry. Returns the run result; `verdict_obj` is None
    when no attempt produced a verdict behind the one-time marker."""
    marker = "LEAN-REVIEW-VERDICT-" + secrets.token_hex(12)
    prompt = build_prompt(cfg, rubric, context + build_reactivation_block(prior, reply_text), marker)
    fn = reviewers.RUNNERS[provider]
    t0 = time.monotonic()
    for attempt in (1, 2):
        env, home = reviewer_env(provider)
        try:
            res = fn(prompt, str(cwd), model, env)
        finally:
            cleanup_rev_home(home)
        # A run the CLI reports as failed is not a review, however well-formed its text looks.
        vo = None if reviewers.cli_reports_failure(res) else extract_verdict(res.get("text", ""), marker)
        if vo is not None:
            break
        res["error_kind"] = error_kind(res)
        if res["error_kind"] in PROVIDER_DOWN_KINDS:
            break  # retrying cannot help; the caller drops this provider
    for f in (vo or {}).get("findings") or []:
        if isinstance(f.get("file"), str):
            f["file"] = normalize_finding_path(f["file"])
    res.update(rubric=rubric, provider=provider, model=model, verdict_obj=vo,
               duration_s=round(time.monotonic() - t0, 1), attempts=attempt)
    return res


def run_queue(cfg, ws, queue, providers, models, state_map, context, *, digest=None,
              version=None, replies=None, halt=True):
    """Run `queue` in order, folding each result into `state_map`. A rubric keeps the provider
    that last judged it when that one is available (so a re-run audits its own finding and an
    author cannot shop for a softer model); otherwise one is drawn at random. Returns
    `(ran, halted_at)`: `halted_at` names the first rubric skipped after a `block`."""
    live = list(providers)
    ran = []
    replies = replies or {}
    for i, rubric in enumerate(queue):
        if not live:
            raise ProvidersDown("no reviewer is able to serve: " + ", ".join(providers))
        prior = state_map.get(rubric)
        pinned = (prior or {}).get("provider")
        while True:
            provider = pinned if pinned in live else random.choice(live)
            print(f"[{rubric}] reviewing with {provider}…", file=sys.stderr)
            res = run_rubric(cfg, rubric, provider, models.get(provider, ""), ws.root, context,
                             prior=prior, reply_text=replies.get(rubric))
            ok = res["verdict_obj"] is not None
            print(f"[{rubric}] {provider}/{res['model'] or 'default'} → "
                  f"{res['verdict_obj']['verdict'] if ok else 'error'} ({res['duration_s']:.0f}s)",
                  file=sys.stderr)
            if ok:
                break
            why = reviewers.failure_summary(res)
            print(f"[{rubric}]   no verdict: {res.get('error_kind')}" + (f" — {why}" if why else ""),
                  file=sys.stderr)
            if res.get("error_kind") not in PROVIDER_DOWN_KINDS:
                break
            # This reviewer cannot serve any rubric: drop it, and give this rubric to another.
            live.remove(provider)
            print(f"[{rubric}]   dropping {provider} for the rest of this run", file=sys.stderr)
            if not live:
                break
        cf = update_case_file(state_map, rubric, res, ws.head, digest, version)
        ran.append(rubric)
        verdict = cf["verdict"]
        if verdict == "block" and halt and i + 1 < len(queue):
            return ran, queue[i + 1]
    return ran, None
