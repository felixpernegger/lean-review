"""The statements a pull request adds or changes, for rubrics that review one statement at a time.

A profile can mark a rubric as expanding (`[expand]` in its profile.toml): instead of one review of
the whole PR, it runs once per changed main statement ("main") or once per batch of variants
("variants"). This module finds those statements in the changed Lean files with a light scanner,
not a Lean parser: it needs declarations that start at column 0, which every file of the projects
it serves follows. A statement it misses is still in the diff that every rubric reads.
"""

import dataclasses, re

# Declarations that start a span. `@[`, `/--` and `set_option … in` lines begin the span of the
# declaration that follows them.
_MODIFIERS = r"(?:(?:private|protected|noncomputable|public|nonrec|partial|unsafe)\s+)*"
_KEYWORD = re.compile(_MODIFIERS + r"(theorem|lemma|def|abbrev|structure|inductive|class|"
                      r"instance|example|opaque|axiom)\b\s*([^\s:({\[]*)")
_INLINE_ATTRS = re.compile(r"(?:@\[[^\]]*\]\s*)+")
_PREFIX = re.compile(r"(@\[|set_option\s.*\sin\s*$)")
_CLOSER = re.compile(r"(end|namespace|section|open|variable|universe|noncomputable section|"
                     r"@\[expose\]|public section|module|import|public import)\b")
DEFINITION_KINDS = ("def", "abbrev", "structure", "inductive", "class", "opaque")
CATEGORY = re.compile(r"\bcategory\s+(research\s+open|research\s+solved|textbook|API|test|"
                      r"undergraduate|graduate|high_school)\b")
QUESTION = re.compile(r"\bquestion(\s+value)?\b")
CHUNK = 6
_SAFE = re.compile(r"[^\w.'«»!?]")


@dataclasses.dataclass
class Decl:
    kind: str
    short: str                  # the name as written
    name: str                   # qualified by the enclosing namespaces
    start: int                  # 1-based, inclusive, including docstring and attributes
    end: int
    code: str                   # the span's source text
    docstring: str = ""
    category: str = ""
    question: str = ""          # "", "yes/no" or "value"
    path: str = ""
    status: str = ""            # "new", "modified", or "uses changed <def>"
    role: str = ""              # main | variant | definition | answer | test | other

    @property
    def attributes(self):
        bits = [f"category {self.category}"] if self.category else []
        if self.question:
            bits.append("question value" if self.question == "value" else "question")
        return ", ".join(bits) or "(none)"


def _scan(text):
    """`(code, comments)`: `text` with every comment blanked to spaces (newlines kept, so offsets
    and line numbers survive), and the comments as `(start, end, kind)` with kind `doc` (`/--`),
    `module` (`/-!`), `block` or `line`. Strings and char literals are skipped over."""
    out, comments, i, n = list(text), [], 0, len(text)
    while i < n:
        if text.startswith("/-", i):
            kind = "doc" if text.startswith("/--", i) and not text.startswith("/--/", i) else (
                "module" if text.startswith("/-!", i) else "block")
            j, depth = i + 2, 1
            while j < n and depth:
                if text.startswith("/-", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("-/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            comments.append((i, j, kind))
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            comments.append((i, j, "line"))
            for k in range(i, j):
                out[k] = " "
            i = j
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            i = j + 1
        elif text[i] == "'" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_'.")):
            m = re.match(r"'(?:\\.[^']*|[^\\'\n])'", text[i:])
            i += len(m.group(0)) if m else 1
        else:
            i += 1
    return "".join(out), comments


def strip_comments(text):
    """`text` without comments or docstrings, blank runs collapsed; line structure is kept within
    each declaration."""
    code, _ = _scan(text)
    lines = [l.rstrip() for l in code.split("\n")]
    out = []
    for l in lines:
        if l or (out and out[-1]):
            out.append(l)
    return "\n".join(out).strip("\n") + "\n"


def _doc_text(raw):
    return raw[3:-2].strip() if raw.startswith("/-") and raw.endswith("-/") else raw.strip()


def module_docstring(text):
    _, comments = _scan(text)
    return "\n\n".join(_doc_text(text[a:b]) for a, b, k in comments if k == "module")


def declarations(text):
    """Every declaration starting at column 0, with its span, namespace and attributes."""
    code, comments = _scan(text)
    raw_lines, lines = text.split("\n"), code.split("\n")
    offsets, pos = [], 0
    for l in raw_lines:
        offsets.append(pos)
        pos += len(l) + 1
    doc_at = {}                                 # line index -> docstring comment
    for a, b, kind in comments:
        if kind == "doc":
            ln = text.count("\n", 0, a)
            if a == offsets[ln]:
                doc_at[ln] = (a, b)
    decls, scopes, pending, cur = [], [], None, None

    def close(upto):
        nonlocal cur
        if cur is not None:
            end = upto
            while end > cur.start and not raw_lines[end - 1].strip():
                end -= 1
            cur.end = end
            cur.code = "\n".join(raw_lines[cur.start - 1:end])
            decls.append(cur)
            cur = None

    for i, line in enumerate(lines):
        if i in doc_at:
            if pending is None:
                close(i)
                pending = i
            continue
        if not line or line[0].isspace():
            continue
        attrs = _INLINE_ATTRS.match(line)
        km = _KEYWORD.match(line, attrs.end() if attrs else 0)
        if km:
            close(i)
            start = pending if pending is not None else i
            pending = None
            short = km.group(2)
            prefix = ".".join(s for kind, s in scopes if kind == "ns")
            name = short[6:] if short.startswith("_root_.") else (
                f"{prefix}.{short}" if prefix and short else short)
            head = "\n".join(lines[start:i + 1])  # attributes live above or on the keyword line
            cat = CATEGORY.search(head)
            q = QUESTION.search(head)
            doc = next((text[a:b] for ln, (a, b) in doc_at.items() if start <= ln < i), "")
            cur = Decl(kind=km.group(1), short=short, name=name, start=start + 1, end=i + 1,
                       code="", docstring=_doc_text(doc) if doc else "",
                       category=" ".join(cat.group(1).split()) if cat else "",
                       question=("value" if q.group(1) else "yes/no") if q else "")
            continue
        if _PREFIX.match(line):
            if pending is None:
                close(i)
                pending = i
            continue
        if _CLOSER.match(line):
            close(i)
            pending = None
            words = line.split()
            if words[0] == "namespace" and len(words) > 1:
                scopes.append(("ns", words[1]))
            elif words[0] == "section":
                scopes.append(("sec", words[1] if len(words) > 1 else ""))
            elif words[0] == "end" and scopes:
                scopes.pop()
    close(len(lines))
    return decls


def role(d):
    if d.kind in DEFINITION_KINDS:
        return "answer" if d.short.endswith(".answer") or d.short == "answer" else "definition"
    if d.kind in ("theorem", "lemma"):
        if d.category in ("research open", "research solved"):
            return "variant" if "variants" in d.short.split(".") else "main"
        if d.category in ("textbook", "undergraduate", "graduate", "high_school"):
            return "variant"
        return "test"
    return "other"


def added_lines(diff_text):
    """`{path: line numbers added on the new side}`. Unlike the anchorable lines in render, context
    lines do not count: a declaration is changed only if the PR wrote one of its lines."""
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
            if raw.startswith("+"):
                out.setdefault(path, set()).add(line)
                line += 1
            elif raw.startswith(" "):
                line += 1
            elif not raw.startswith(("-", "\\")):
                line = None
    return out


def changed_declarations(root, diff_text, changed):
    """Declarations of the changed `.lean` files that the PR adds or edits, plus each research
    statement in the same file that uses a definition the PR edits: its meaning changed too."""
    added, out = added_lines(diff_text), []
    for path in changed:
        f = root / path
        if not path.endswith(".lean") or not f.is_file() or f.is_symlink():
            continue
        lines = added.get(path, set())
        decls = declarations(f.read_text(encoding="utf-8", errors="replace"))
        touched = []
        for d in decls:
            d.path, d.role = path, role(d)
            hit = [n for n in range(d.start, d.end + 1) if n in lines]
            if hit:
                nonblank = [n for n, l in enumerate(d.code.split("\n"), d.start) if l.strip()]
                d.status = "new" if all(n in lines for n in nonblank) else "modified"
                touched.append(d)
        defs = [d for d in touched if d.role == "definition" and d.short]
        for d in decls:
            if d in touched or d.role not in ("main", "variant") or not defs:
                continue
            body = strip_comments(d.code)
            used = [x.short for x in defs
                    if re.search(rf"(?<![\w.]){re.escape(x.short.split('.')[-1])}(?![\w'])", body)]
            if used:
                d.status = "uses changed " + ", ".join(f"`{u}`" for u in used)
                touched.append(d)
        out.extend(sorted(touched, key=lambda d: d.start))
    return out


def _target(d, taken):
    key = _SAFE.sub("_", d.short or d.name)[:80] or f"line{d.start}"
    if key in taken:
        key = _SAFE.sub("_", f"{d.path}.{d.short}")[-80:]
    taken.add(key)
    return key


def unit_rubric(unit):
    """The rubric a unit key (`rubric` or `rubric:target`) runs."""
    return unit.split(":", 1)[0]


def unit_label(unit):
    return unit.replace(":", " · ", 1)


def expand_units(cfg, decls, log=lambda msg: None):
    """`(units, targets)`: the rubric queue with each expanding rubric replaced by one unit per
    target, and `targets[unit]` the declarations that unit reviews. Main statements beyond
    `cfg.full_checks` go to the "variants" rubric. An expanding rubric with nothing to review is
    left out."""
    mains = [d for d in decls if d.role == "main"]
    full, overflow = mains[:cfg.full_checks], mains[cfg.full_checks:]
    variants = overflow + [d for d in decls if d.role == "variant"]
    has_variant_rubric = "variants" in [cfg.expand.get(r) for r in cfg.rubrics]
    if overflow and has_variant_rubric:
        log(f"note: {len(overflow)} main statement(s) beyond full_checks={cfg.full_checks} get "
            "the cheaper variant review")
    units, targets, taken = [], {}, set()
    for r in cfg.rubrics:
        kind = cfg.expand.get(r)
        if kind == "main":
            if not full:
                log(f"[{r}] no changed main statement; skipped")
            for d in full:
                u = f"{r}:{_target(d, taken)}"
                units.append(u)
                targets[u] = [d]
        elif kind == "variants":
            if not variants:
                log(f"[{r}] no changed variant statement; skipped")
            chunks = [variants[i:i + CHUNK] for i in range(0, len(variants), CHUNK)]
            for i, chunk in enumerate(chunks, 1):
                u = r if len(chunks) == 1 else f"{r}:{i}"
                units.append(u)
                targets[u] = chunk
        else:
            units.append(r)
    return units, targets


# Places where Lean's totalised operations or common encodings can change a statement's meaning:
# leads for the reviewer, never findings by themselves.
_HINTS = (
    (re.compile(r"(?<![-<])-(?![->])"), "subtraction: truncates at 0 on ℕ"),
    (re.compile(r"(?<!/)/(?![/\\])"), "division: rounds down on ℕ/ℤ, and x / 0 = 0"),
    (re.compile(r"⁻¹"), "inverse: 0⁻¹ = 0"),
    (re.compile(r"\bNat\.sqrt\b|\.sqrt\b"), "Nat.sqrt truncates"),
    (re.compile(r"\bReal\.sqrt\b|√"), "Real.sqrt of a negative number is 0"),
    (re.compile(r"\bReal\.log\b|\blog\b"), "Real.log 0 = 0 and log (-x) = log x"),
    (re.compile(r"\btoNat\b"), "Int.toNat of a negative number is 0"),
    (re.compile(r"\bsInf\b|⨅"), "sInf of the empty (or unbounded) set is a junk value"),
    (re.compile(r"\bsSup\b|⨆"), "sSup of the empty or unbounded set is a junk value"),
    (re.compile(r"\bncard\b|\bNat\.card\b|\bencard\b"), "ncard / Nat.card of an infinite set is 0"),
    (re.compile(r"\bFinset\.range\b|\brange\b"), "Finset.range n is {0, …, n - 1}"),
    (re.compile(r"\bFin\b"), "Fin n is {0, …, n - 1}"),
    (re.compile(r"\blimsup\b|\bliminf\b"), "limsup / liminf need boundedness to mean anything"),
    (re.compile(r"∀ᶠ|∃ᶠ|\bTendsto\b"), "filters: check the filter and which side is eventual"),
    (re.compile(r"\bZMod\b"), "ZMod 0 is ℤ"),
    (re.compile(r"\bnth\b"), "Nat.nth is 0-indexed (Nat.nth Nat.Prime 0 = 2)"),
)


def junk_hints(code):
    body = strip_comments(code)
    return [why for pat, why in _HINTS if pat.search(body)]
