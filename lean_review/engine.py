"""Run the selected rubrics against a workspace, one at a time."""

import json, random, secrets, sys, time

from . import reviewers, statements
from .reviewers import (PROVIDER_DOWN_KINDS, build_prompt, build_stage_prompt, cleanup_rev_home,
                        error_kind, reviewer_env)
from .state import build_reactivation_block, normalize_finding_path, update_case_file
from .verdict import extract_marked_json, extract_verdict


class ProvidersDown(Exception):
    """Every configured reviewer failed for a reason the next rubric would hit too."""


# Which blind view of the checkout each stage works in (see workspace.build_blind).
STAGE_CHECKOUT = {"literal-reading": "blind_read", "independent-formalization": "blind_formalize"}
STAGE_OUTPUT_LIMIT = 20_000


def _code_block(code):
    return f"```lean\n{code.rstrip()}\n```"


def stage_values(stage, decls, root, changed=()):
    """What a stage is shown of its target statements. The literal reading gets the Lean code with
    every comment and docstring removed; the independent formalization gets only the prose and
    the names it must define. This is the whole of what separates the stages from the PR's text,
    so it is kept here, small, and tested."""
    if stage == "literal-reading":
        blocks = [f"### `{d.name}` (in `{d.path}`, around line {d.start})\n\n"
                  + _code_block(statements.strip_comments(d.code)) for d in decls]
        return {"statements": "\n\n".join(blocks)}
    if stage == "independent-formalization":
        d = decls[0]
        text = (root / d.path).read_text(encoding="utf-8", errors="replace")
        new_defs = [x for x in changed if x.path == d.path and x.role == "definition"]
        defs = "\n".join(f"- `{x.short}`: {x.docstring or '(no docstring)'}" for x in new_defs)
        return {"name": d.name, "path": d.path, "attributes": d.attributes,
                "statement": d.docstring or "(the statement has no docstring)",
                "module_doc": statements.module_docstring(text) or "(none)",
                "new_definitions": defs or "(none)"}
    raise ValueError(f"no inputs defined for stage {stage!r}")


def run_stage(cfg, stage, provider, model, cwd, values):
    """One blind stage on one reviewer, with one retry. Returns the run result with `output`, the
    JSON object behind the marker, or None."""
    marker = "LEAN-REVIEW-STAGE-" + secrets.token_hex(12)
    prompt = build_stage_prompt(cfg, stage, values, marker)
    fn = reviewers.RUNNERS[provider]
    t0 = time.monotonic()
    for attempt in (1, 2):
        env, home = reviewer_env(provider)
        try:
            res = fn(prompt, str(cwd), model, env)
        finally:
            cleanup_rev_home(home)
        out = None if reviewers.cli_reports_failure(res) else extract_marked_json(
            res.get("text", ""), marker)
        if out is not None:
            break
        res["error_kind"] = error_kind(res)
        if res["error_kind"] in PROVIDER_DOWN_KINDS:
            break
    res.update(output=out, duration_s=round(time.monotonic() - t0, 1))
    return res


def target_block(decls, evidence):
    """The rubric-specific context of a per-statement unit: the statements it reviews and what
    the blind stages produced. It follows the rubric text, after the cached prefix."""
    out = ["\n## Statements under review"]
    for d in decls:
        hints = statements.junk_hints(d.code)
        out += [f"\n### `{d.name}` — `{d.path}` lines {d.start}–{d.end}",
                f"- status: {d.status or 'unchanged'}; kind: {d.kind}; attributes: {d.attributes}",
                ("- places to check (from a mechanical scan, not findings): " + "; ".join(hints))
                if hints else "- places to check: none found by the mechanical scan",
                "", _code_block(d.code)]
    if evidence:
        out.append("\n## Evidence from the blind steps (untrusted reviewer output)\n"
                   "Produced by other model runs that did not see what you see. It can be wrong: "
                   "check every claim against the code before you rely on it.")
        out += evidence
    return "\n".join(out) + "\n"


def run_stages(cfg, unit, provider, model, ws, decls):
    """The blind stages of `unit`, in order. Returns `(evidence, failed)`: the evidence blocks for
    the rubric, and the run result of a stage whose provider cannot serve (else None)."""
    evidence = []
    for stage in cfg.stages.get(statements.unit_rubric(unit), []):
        cwd = getattr(ws, STAGE_CHECKOUT.get(stage, "blind_read"), None) or ws.root
        res = run_stage(cfg, stage, provider, model, cwd,
                        stage_values(stage, decls, ws.root, ws.changed_decls))
        out = res["output"]
        print(f"[{unit}] stage {stage} with {provider} → {'done' if out is not None else 'no output'}"
              f" ({res['duration_s']:.0f}s)", file=sys.stderr)
        if out is None and res.get("error_kind") in PROVIDER_DOWN_KINDS:
            return evidence, res
        body = (json.dumps(out, ensure_ascii=False, indent=1)[:STAGE_OUTPUT_LIMIT]
                if out is not None else f"(the {stage} step produced no output; do that analysis "
                "yourself)")
        evidence.append(f"\n### {stage}\n\n{body}")
    return evidence, None


def run_rubric(cfg, rubric, provider, model, cwd, context, prior=None, reply_text=None, ws=None,
               targets=None):
    """One rubric (or one unit of an expanding rubric) on one reviewer, with one retry. Returns
    the run result; `verdict_obj` is None when no attempt produced a verdict behind the one-time
    marker."""
    marker = "LEAN-REVIEW-VERDICT-" + secrets.token_hex(12)
    t0 = time.monotonic()
    extra = ""
    if targets:
        evidence, failed = run_stages(cfg, rubric, provider, model, ws, targets)
        if failed is not None:
            failed.update(rubric=rubric, provider=provider, model=model, verdict_obj=None,
                          duration_s=round(time.monotonic() - t0, 1), attempts=1)
            return failed
        extra = target_block(targets, evidence)
    # `context` is the same for every rubric, so it forms the cached prompt prefix; the unit's
    # statements and the reactivation block are its own and go after the rubric text.
    prompt = build_prompt(cfg, statements.unit_rubric(rubric), context, marker,
                          extra + build_reactivation_block(prior, reply_text))
    fn = reviewers.RUNNERS[provider]
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
              version=None, replies=None, halt=True, targets=None):
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
                             prior=prior, reply_text=replies.get(rubric), ws=ws,
                             targets=(targets or {}).get(rubric))
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
