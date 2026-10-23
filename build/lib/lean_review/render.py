"""Markdown for everything lean-review posts: the core-mode PR review and its inline comments, and
the scoreboard-mode board, per-rubric threads and contest replies."""

import datetime, json, re

from . import __version__
from .verdict import newest_reply_id, state_of

REVIEW_MARKER = "<!--lean-review:review-->"
BOARD_MARKER = "<!--lean-review:scoreboard-->"
REPLY_MARKER = "<!--lean-review:reply-->"
RUBRIC_MARKER_RE = re.compile(r"<!--lean-review:rubric:([a-z][a-z0-9-]*)-->")
META_RE = re.compile(r"<!--lean-review:meta (.*?)-->", re.S)

ICON = {"green": "✅", "stale": "♻️", "blocking_request": "🟡", "blocking_block": "⛔",
        "error": "⚠️", "absent": "▫️"}
WORD = {"green": "approved", "stale": "approved on an earlier commit",
        "blocking_request": "changes requested", "blocking_block": "blocked",
        "error": "error (no verdict)", "absent": "not run"}


def sanitize(text, limit=2000):
    """Model-derived text is untrusted: strip HTML comments so a prompt-injected reviewer cannot
    forge a lean-review marker, drop control characters, and cap the length."""
    if not text:
        return ""
    t = re.sub(r"<!--.*?(-->|$)", "", str(text), flags=re.S)
    t = "".join(ch for ch in t if ch == "\n" or ord(ch) >= 32)
    return t[:limit]


def meta_block(**payload):
    """Hidden machine-readable state, the last line of a body. `<` and `>` are escaped inside the
    JSON so model text it carries can never close the HTML comment early."""
    s = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return "<!--lean-review:meta " + s.replace("<", "\\u003c").replace(">", "\\u003e") + "-->"


def _cell(text):
    return sanitize(text or "", 400).replace("\n", " ").replace("|", "\\|")


def _judge(cf):
    return f"`{cf.get('provider')}/{cf.get('model') or 'default'}`" if cf.get("provider") else "—"


def _loc(f):
    return sanitize((f.get("file") or "") + (f":{f['line']}" if f.get("line") else ""), 300)


def _finding_line(f):
    loc = _loc(f)
    return (f"- {('`' + loc + '` — ') if loc else ''}{sanitize(f.get('issue', ''))}"
            + (f" _Fix:_ {sanitize(f['fix'])}" if f.get("fix") else ""))


def _footer(ws):
    sub = [f"Reviewed head `{ws.head[:7]}`"]
    if ws.merge_base:
        sub.append(f"[diff](https://github.com/{ws.repo}/compare/{ws.merge_base}...{ws.head})")
    sub.append(f"lean-review {__version__}")
    return f"<sub>{' · '.join(sub)}</sub>"


def diff_right_lines(diff_text):
    """{path: lines on the new side that a review comment can anchor to}: added and context lines
    of each hunk, which is what GitHub accepts for `side: RIGHT`."""
    out, path, line = {}, None, None
    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            path, line = None, None
        elif raw.startswith("+++ "):
            target = raw[4:].strip()
            path = target[2:] if target.startswith("b/") else None
        elif raw.startswith("@@ ") and path:
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            line = int(m.group(1)) if m else None
        elif path and line is not None:
            if raw.startswith("+") or raw.startswith(" "):
                out.setdefault(path, set()).add(line)
                line += 1
            elif raw.startswith("\\"):
                continue
            elif not raw.startswith("-"):
                line = None
    return out


def _as_line(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def render_core_review(rubrics, state_map, ws, overall):
    """The core-mode PR review: `(body, inline_comments)`. Findings whose line lies in the diff
    become inline comments; the rest are listed in the body."""
    anchorable = diff_right_lines(ws.diff_text)
    lines = [REVIEW_MARKER, f"## lean-review — {overall}", "",
             "| | rubric | verdict | reviewer | summary |", "|---|---|---|---|---|"]
    comments, unanchored = [], []
    for r in rubrics:
        cf = state_map.get(r) or {}
        s = state_of(cf, ws.head)
        lines.append(f"| {ICON[s]} | {r} | {WORD[s]} | {_judge(cf)} | {_cell(cf.get('summary'))} |")
        for f in cf.get("findings") or []:
            path, n = f.get("file") or "", _as_line(f.get("line"))
            if n and n in anchorable.get(path, ()):
                body = [f"**{r}** — {sanitize(f.get('issue', ''))}"]
                if f.get("fix"):
                    body.append(f"**Fix:** {sanitize(f['fix'])}")
                if f.get("evidence"):
                    body.append(f"<sub>Evidence: {sanitize(f['evidence'], 600)}</sub>")
                comments.append({"path": path, "line": n, "side": "RIGHT",
                                 "body": "\n\n".join(body)})
            else:
                unanchored.append((r, f))
    if unanchored:
        lines += ["", "### Findings outside the diff"]
        for r, f in unanchored:
            lines.append(_finding_line(f).replace("- ", f"- **{r}**: ", 1))
    if comments:
        lines += ["", f"{len(comments)} finding(s) are attached inline."]
    lines += ["", _footer(ws), "",
              meta_block(kind="review", head_sha=ws.head,
                         states={r: state_of(state_map.get(r), ws.head) for r in rubrics})]
    return "\n".join(lines), comments


def render_thread(cf, ws):
    """A blocking rubric's review-thread root. The marker maps a reply back to the rubric."""
    emoji = {"block": "⛔", "request_changes": "🟡"}
    v = cf.get("verdict", "error")
    lines = [f"<!--lean-review:rubric:{cf['rubric']}-->",
             f"### {emoji.get(v, '•')} {cf['rubric']} — {v}  {_judge(cf)}", "",
             sanitize(cf.get("summary", "")), ""]
    lines += [_finding_line(f) for f in cf.get("findings") or []]
    lines += ["", "Reply in this thread to contest a finding; the next `lean-review --mode "
              "scoreboard` run re-reviews **only** this rubric and answers here. To fix it, push a "
              "commit.", "", _footer(ws)]
    return "\n".join(lines)


def render_contest_reply(cf, head_sha):
    rubric = cf.get("rubric", "")
    if state_of(cf, head_sha) == "green":
        verdict = f"this clears the finding ✅ (approved on `{head_sha[:7]}`)."
    else:
        why = _cell(cf.get("summary")) or "the prior finding still holds"
        verdict = f"the finding stands — {why}"
    return (f"{REPLY_MARKER}\n**Re: your reply on `{rubric}`:** re-reviewed on `{head_sha[:7]}`; "
            f"{verdict}\n\n<sub>{_judge(cf)} · answers replies through comment "
            f"{newest_reply_id(cf)}.</sub>")


def render_scoreboard(rubrics, state_map, ws, overall, persisted):
    """The scoreboard comment; `persisted` is the compact state carried to the next run."""
    lines = [BOARD_MARKER, f"## lean-review — {overall}", "",
             "Each rubric is judged by an independent review agent.", "",
             "| | rubric | state | reviewer | summary |", "|---|---|---|---|---|"]
    for r in rubrics:
        cf = state_map.get(r) or {}
        s = state_of(cf, ws.head)
        state = WORD[s]
        if s == "green" and cf.get("carried_from_sha"):
            state += f" (carried from `{cf['carried_from_sha'][:7]}`, patch unchanged)"
        thread = (cf.get("thread") or {}).get("url")
        if thread and s in ("blocking_request", "blocking_block"):
            state = f"[{state}]({thread})"
        lines.append(f"| {ICON[s]} | {r} | {state} | {_judge(cf)} | {_cell(cf.get('summary'))} |")
    lines += ["", _footer(ws), "",
              meta_block(kind="scoreboard", head_sha=ws.head,
                         ts=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         state=persisted)]
    return "\n".join(lines)
