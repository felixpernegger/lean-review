"""Verdict parsing and per-rubric state rules."""

import json, re

VERDICTS = ("approve", "request_changes", "block")


def extract_verdict(text, marker):
    """Parse the verdict only from after the one-time secret marker.

    The marker is a fresh random token the attacker cannot predict, so it cannot be forged in
    PR content. We take the text after the last marker occurrence (tolerating a benign restate)
    and read the JSON object there. Everything before the marker — including any attacker JSON
    echoed by the model — is ignored. Fail closed (None) on a missing marker, unparseable JSON,
    or a verdict outside the allowed set; the caller renders that as an `error` verdict.
    """
    if not text or marker not in text:
        return None
    tail = text.rsplit(marker, 1)[1]
    m = re.search(r"\{.*\}", tail, flags=re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("verdict") not in VERDICTS:
        return None
    if not isinstance(d.get("findings"), list):
        d["findings"] = []
    d["findings"] = [f for f in d["findings"] if isinstance(f, dict)]
    return d


def state_of(cf, head_sha):
    """A rubric's live state from its case file and the current HEAD."""
    if not cf or not cf.get("verdict"):
        return "absent"
    v = cf["verdict"]
    if v == "approve":
        return "green" if cf.get("approved_sha") == head_sha else "stale"
    if v == "block":
        return "blocking_block"
    if v == "request_changes":
        return "blocking_request"
    return "error"


def posts_review_thread(state):
    """States that warrant a contestable review thread: a genuine adverse verdict. `error` is an
    infrastructure failure (no parseable verdict), not a finding to contest, so it gets none."""
    return state in ("blocking_request", "blocking_block")


def newest_reply_id(cf):
    """The highest author-reply comment id recorded for this rubric, or None. GitHub comment ids
    are monotonic, so this is the watermark a re-run compares against `last_reply_seen`."""
    ids = [r.get("id") for r in ((cf or {}).get("author_replies") or []) if r.get("id") is not None]
    return max(ids) if ids else None


def has_new_contest(cf):
    """True iff this rubric carries an author reply NEWER than the one last adjudicated. Strict `>`
    on the monotonic id, so a deleted newest reply can never re-fire the run."""
    nr = newest_reply_id(cf)
    return nr is not None and nr > ((cf or {}).get("last_reply_seen") or 0)


def overall_label(states, halted=None):
    if any(s == "blocking_block" for s in states):
        label = "blocked"
    elif any(s in ("blocking_request", "error") for s in states):
        label = "changes requested"
    elif any(s == "absent" for s in states):
        label = "pending"
    elif any(s == "stale" for s in states):
        label = "re-review pending"
    elif states and all(s == "green" for s in states):
        label = "approved"
    else:
        label = "partial"
    if halted:
        label += f" (halted at a block; {halted} and later not run)"
    return label
