"""Publishing through the operator's `gh` login. Runs only after every reviewer has exited, and
the reviewers never see this credential."""

import json, os, random, subprocess, sys, tempfile, time

from .render import BOARD_MARKER, META_RE, REVIEW_MARKER


def gh_api(method, endpoint, payload=None, failures=None, action=""):
    """`gh api` with a JSON request body. Comment sends are spaced, and GitHub's 422 "submitted too
    quickly" anti-abuse rejection is retried with backoff; other errors are recorded in `failures`
    and return None."""
    cmd = ["gh", "api", "-X", method, endpoint]
    body_path = None
    if payload is not None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(payload, f)
            body_path = f.name
        cmd += ["--input", body_path]
    sending = method in ("POST", "PATCH") and payload is not None
    try:
        for attempt in range(4):
            if sending:
                time.sleep(2)
            r = subprocess.run(cmd, text=True, capture_output=True)
            if r.returncode == 0:
                try:
                    return json.loads(r.stdout) if r.stdout.strip() else {}
                except ValueError:
                    return {}
            throttled = sending and ("submitted too quickly" in r.stdout + r.stderr
                                     or '"code":"abuse"' in r.stdout)
            if throttled and attempt < 3:
                delay = 60 * 2 ** attempt + random.uniform(0, 5)
                print(f"GitHub throttled the comment; retry {attempt + 1}/3 in {delay:.0f}s",
                      file=sys.stderr)
                time.sleep(delay)
                continue
            print(f"gh api {method} {endpoint} failed: {(r.stderr or r.stdout)[-600:]}",
                  file=sys.stderr)
            if failures is not None:
                failures.append(action or f"{method} {endpoint}")
            return None
    finally:
        if body_path:
            os.unlink(body_path)


def gh_paginate(endpoint):
    """Every item of a paginated list endpoint, or None on failure."""
    r = subprocess.run(["gh", "api", "--paginate", "--jq", ".[] | @json", endpoint],
                       text=True, capture_output=True)
    if r.returncode != 0:
        print(f"gh api {endpoint} failed: {r.stderr[-300:]}", file=sys.stderr)
        return None
    out = []
    for line in r.stdout.splitlines():
        try:
            item = json.loads(line)
            out.append(json.loads(item) if isinstance(item, str) else item)
        except ValueError:
            continue
    return out


def current_login():
    r = subprocess.run(["gh", "api", "user", "--jq", ".login"], text=True, capture_output=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def post_review(repo, pr, head, body, comments, failures):
    """Core mode: one PR review (event COMMENT) with its inline comments. If GitHub rejects an
    inline anchor, fall back to the same review with every finding in the body."""
    payload = {"commit_id": head, "event": "COMMENT", "body": body, "comments": comments}
    resp = gh_api("POST", f"/repos/{repo}/pulls/{pr}/reviews", payload, failures, "review POST")
    if resp is None and comments:
        failures.clear()
        extra = "\n\n### Inline findings\n" + "\n".join(
            f"- `{c['path']}:{c['line']}` — {c['body']}" for c in comments)
        resp = gh_api("POST", f"/repos/{repo}/pulls/{pr}/reviews",
                      {**payload, "body": body + extra, "comments": []}, failures,
                      "review POST (no inline)")
    return resp


def find_own_review(repo, pr, head, me):
    """The URL of the newest lean-review review `me` already posted for exactly `head`, or None."""
    for r in reversed(gh_paginate(f"/repos/{repo}/pulls/{pr}/reviews?per_page=100") or []):
        body = r.get("body") or ""
        if (r.get("user") or {}).get("login") != me or REVIEW_MARKER not in body:
            continue
        metas = META_RE.findall(body)
        try:
            meta = json.loads(metas[-1]) if metas else {}
        except ValueError:
            continue
        if meta.get("head_sha") == head:
            return r.get("html_url") or ""
    return None


def upsert_scoreboard(repo, pr, body, board_id, me, failures):
    """Edit our scoreboard in place, or create it. Only a comment authored by `me` is edited, and
    our own older duplicates are removed. Returns the comment id or None."""
    comments = gh_paginate(f"/repos/{repo}/issues/{pr}/comments?per_page=100")
    if comments is None:
        failures.append("scoreboard discovery")
        return None
    ours = sorted((c for c in comments if (c.get("user") or {}).get("login") == me
                   and BOARD_MARKER in (c.get("body") or "")),
                  key=lambda c: (c.get("updated_at") or "", c.get("id") or 0), reverse=True)
    target = next((c["id"] for c in ours if c["id"] == board_id), ours[0]["id"] if ours else None)
    if target:
        ok = gh_api("PATCH", f"/repos/{repo}/issues/comments/{target}", {"body": body},
                    failures, "scoreboard PATCH") is not None
    else:
        resp = gh_api("POST", f"/repos/{repo}/issues/{pr}/comments", {"body": body},
                      failures, "scoreboard POST")
        target = (resp or {}).get("id")
        ok = bool(target)
    if ok:
        for c in ours:
            if c["id"] != target:
                gh_api("DELETE", f"/repos/{repo}/issues/comments/{c['id']}")
    return target if ok else None


def upsert_thread(repo, pr, head, cf, body, path, me, roots, failures):
    """Create or edit a blocking rubric's file-level review thread root; updates `cf["thread"]`."""
    known = (cf.get("thread") or {}).get("comment_id")
    mine = next((c for c in roots if c["id"] == known and (c.get("user") or {}).get("login") == me),
                None)
    if mine:
        resp = gh_api("PATCH", f"/repos/{repo}/pulls/comments/{known}", {"body": body},
                      failures, f"thread PATCH {cf['rubric']}")
    else:
        resp = gh_api("POST", f"/repos/{repo}/pulls/{pr}/comments",
                      {"commit_id": head, "path": path, "subject_type": "file", "body": body},
                      failures, f"thread POST {cf['rubric']}")
    if resp and resp.get("id"):
        cf["thread"] = {"comment_id": resp["id"], "url": resp.get("html_url")}
    return resp


def reply_in_thread(repo, pr, root_id, body, failures):
    return gh_api("POST", f"/repos/{repo}/pulls/{pr}/comments/{root_id}/replies",
                  {"body": body}, failures, "contest reply")


def resolve_thread(repo, pr, comment_id):
    """Resolve the review thread whose root is `comment_id`. Best-effort."""
    owner, name = repo.split("/")
    q = ("query($owner:String!,$name:String!,$pr:Int!){repository(owner:$owner,name:$name){"
         "pullRequest(number:$pr){reviewThreads(first:100){nodes{id isResolved "
         "comments(first:1){nodes{databaseId}}}}}}}")
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}", "-F", f"owner={owner}",
                        "-F", f"name={name}", "-F", f"pr={int(pr)}"], text=True, capture_output=True)
    try:
        nodes = json.loads(r.stdout)["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
    except (ValueError, KeyError, TypeError):
        return
    tid = next((t["id"] for t in nodes if not t["isResolved"] and t["comments"]["nodes"]
                and t["comments"]["nodes"][0]["databaseId"] == comment_id), None)
    if tid:
        mut = "mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}"
        subprocess.run(["gh", "api", "graphql", "-f", f"query={mut}", "-F", f"id={tid}"],
                       text=True, capture_output=True)
