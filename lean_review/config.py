"""Per-project configuration: `.lean-review.toml` plus optional prompt overlays.

Everything here is read from the target repository's BASE commit (or a local path the operator
names), never from the PR head: the head is written by the PR author, and a config or rubric
overlay taken from it would let the author rewrite their own review.
"""

import base64, dataclasses, json, pathlib, re, subprocess, tomllib

CONFIG_FILE = ".lean-review.toml"
OVERLAY_DIR = ".lean-review"
RUBRICS_DIR = pathlib.Path(__file__).resolve().parent / "rubrics"
PROFILES_DIR = pathlib.Path(__file__).resolve().parent / "profiles"
# Built-in profiles: a bundled layer of configuration, notes and rubrics for a kind of project,
# for repositories whose default branch the operator cannot add a `.lean-review.toml` to.
# "default" is the plain built-in set.
PROFILES = ("default", "formal-conjectures")
# A repository whose base commit has this directory gets the formal-conjectures profile unless a
# profile is chosen explicitly.
PROFILE_MARKERS = {"formal-conjectures": "FormalConjecturesUtil"}

# Review order: the block-capable integrity angles first, so a block halts the round early.
DEFAULT_RUBRICS = ["correctness", "reuse", "attribution", "api-design", "generality",
                   "placement", "naming", "documentation", "proof-quality"]
MODES = ("core", "scoreboard")
RUBRIC_NAME = re.compile(r"[a-z][a-z0-9-]*")


class ConfigError(Exception):
    pass


@dataclasses.dataclass
class Config:
    project: str = ""
    description: str = "a Lean 4 project"
    source_root: str = ""
    namespace: str = ""
    mode: str = "core"
    rubrics: list = dataclasses.field(default_factory=lambda: list(DEFAULT_RUBRICS))
    mathlib: bool = True
    # Fetch the sources the PR cites (erdosproblems.com, arXiv, OEIS, Wikipedia) into the checkout.
    sources: bool = False
    ci_check: str = "build"
    profile: str = ""
    # Most statements a rubric that reviews one statement at a time takes on in full; the rest go
    # to the profile's cheaper per-variant rubric.
    full_checks: int = 6
    # Overlays: project notes appended to the shared protocol, and rubric texts that add to or
    # replace the built-in ones (name -> markdown).
    notes: str = ""
    rubric_overrides: dict = dataclasses.field(default_factory=dict)
    # The profile layer, below the repository's own overlays. `expand` maps a rubric to the
    # statements it reviews one unit at a time ("main" or "variants"); `stages` lists the blind
    # steps run before such a rubric; `references` the documents appended to a rubric's prompt.
    profile_source: str = ""
    profile_notes: str = ""
    profile_rubrics: dict = dataclasses.field(default_factory=dict)
    stage_texts: dict = dataclasses.field(default_factory=dict)
    stages: dict = dataclasses.field(default_factory=dict)
    expand: dict = dataclasses.field(default_factory=dict)
    references: dict = dataclasses.field(default_factory=dict)
    reference_texts: dict = dataclasses.field(default_factory=dict)

    def rubric_text(self, name):
        if name in self.rubric_overrides:
            return self.rubric_overrides[name]
        if name in self.profile_rubrics:
            return self.profile_rubrics[name]
        path = RUBRICS_DIR / f"{name}.md"
        if not path.is_file():
            raise ConfigError(f"unknown rubric {name!r}: no built-in rubric and no "
                              f"{OVERLAY_DIR}/rubrics/{name}.md overlay")
        return path.read_text()

    def placeholders(self):
        return {"project": self.project, "description": self.description,
                "source_root": self.source_root or ".", "namespace": self.namespace}


# The keys a `.lean-review.toml` may set; the rest of Config is filled from overlays and profiles.
TOML_KEYS = ("project", "description", "source_root", "namespace", "mode", "rubrics", "mathlib",
             "sources", "ci_check", "profile", "full_checks")


def _loads(text, where=CONFIG_FILE):
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{where}: {e}")


def _apply(cfg, data, where):
    for key, value in data.items():
        if key not in TOML_KEYS:
            raise ConfigError(f"{where}: unknown key {key!r}")
        expected = type(getattr(Config(), key))
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise ConfigError(f"{where}: {key} must be a {expected.__name__}")
        setattr(cfg, key, value)


def parse(text, cfg=None, profile=None):
    """Apply a `.lean-review.toml` document to `cfg` (a default Config if None). Its `profile`
    is applied first, beneath its other keys, unless `profile` (from the command line, say) is
    given, which wins."""
    cfg = cfg or Config()
    data = _loads(text)
    name = data.pop("profile", None)
    if name is not None and not isinstance(name, str):
        raise ConfigError(f"{CONFIG_FILE}: profile must be a str")
    if profile is None and name:
        apply_profile(cfg, name, "config")
    _apply(cfg, data, CONFIG_FILE)
    validate(cfg)
    return cfg


def toml_profile(text):
    name = _loads(text).get("profile") if text else None
    return name if isinstance(name, str) else ""


def apply_profile(cfg, name, source):
    """Lay the bundled profile `name` onto `cfg`, beneath anything applied after it."""
    if name not in PROFILES:
        raise ConfigError(f"unknown profile {name!r}; known: {', '.join(PROFILES)}")
    cfg.profile, cfg.profile_source = name, source
    if name == "default":
        return cfg
    d = PROFILES_DIR / name
    data = _loads((d / "profile.toml").read_text(), f"profile {name}")
    tables = {k: data.pop(k, {}) for k in ("stages", "expand", "references")}
    _apply(cfg, data, f"profile {name}")
    cfg.profile = name
    cfg.stages, cfg.expand, cfg.references = (tables["stages"], tables["expand"],
                                              tables["references"])
    cfg.profile_notes = (d / "common.md").read_text() if (d / "common.md").is_file() else ""
    cfg.profile_rubrics = {p.stem: p.read_text() for p in sorted((d / "rubrics").glob("*.md"))}
    cfg.stage_texts = {p.stem: p.read_text() for p in sorted((d / "stages").glob("*.md"))}
    cfg.reference_texts = {f"{name}/{rel}": (d / rel).read_text()
                           for rels in cfg.references.values() for rel in rels}
    cfg.references = {r: [f"{name}/{rel}" for rel in rels] for r, rels in cfg.references.items()}
    for rubric, stages in cfg.stages.items():
        for st in stages:
            if st not in cfg.stage_texts:
                raise ConfigError(f"profile {name}: rubric {rubric} names unknown stage {st!r}")
    validate(cfg)
    return cfg


def detect_profile(repo, ref):
    """The profile a repository's layout at `ref` calls for, or ""."""
    for name, marker in PROFILE_MARKERS.items():
        if isinstance(_gh_contents(repo, marker, ref), list):
            return name
    return ""


def validate(cfg):
    if cfg.mode not in MODES:
        raise ConfigError(f"mode must be one of {', '.join(MODES)}, not {cfg.mode!r}")
    if cfg.profile and cfg.profile not in PROFILES:
        raise ConfigError(f"unknown profile {cfg.profile!r}; known: {', '.join(PROFILES)}")
    if cfg.full_checks < 0:
        raise ConfigError("full_checks must not be negative")
    if not cfg.rubrics:
        raise ConfigError("no rubrics selected")
    for name in cfg.rubrics:
        if not isinstance(name, str) or not RUBRIC_NAME.fullmatch(name):
            raise ConfigError(f"invalid rubric name {name!r}")
    if cfg.source_root and (cfg.source_root.startswith("/") or ".." in cfg.source_root.split("/")):
        raise ConfigError("source_root must be a relative path inside the repository")


def _gh_contents(repo, path, ref):
    """The decoded text of `path` at `ref`, None when absent; a directory listing as a list."""
    r = subprocess.run(["gh", "api", f"/repos/{repo}/contents/{path}?ref={ref}"],
                       text=True, capture_output=True)
    if r.returncode != 0:
        if "404" in r.stderr or "Not Found" in r.stderr or "Not Found" in r.stdout:
            return None
        raise ConfigError(f"could not read {path} at {ref[:12]}: {r.stderr.strip()[-300:]}")
    data = json.loads(r.stdout)
    if isinstance(data, list):
        return data
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8")
    raise ConfigError(f"{path} at {ref[:12]} is not a regular file")


def _base_layer(text, profile, detect):
    """A Config holding the profile layer: `profile` if given, else the TOML's, else the one
    `detect()` finds (when given)."""
    cfg = Config()
    if profile:
        apply_profile(cfg, profile, "flag")
    elif not toml_profile(text) and detect:
        found = detect()
        if found:
            apply_profile(cfg, found, "detected")
    return cfg


def load_remote(repo, ref, profile=None, detect=False):
    """Config and overlays from `repo` at commit `ref` (the PR's base). Missing files are fine."""
    text = _gh_contents(repo, CONFIG_FILE, ref)
    text = text if isinstance(text, str) else ""
    cfg = _base_layer(text, profile, (lambda: detect_profile(repo, ref)) if detect else None)
    parse(text, cfg, profile)
    notes = _gh_contents(repo, f"{OVERLAY_DIR}/common.md", ref)
    if isinstance(notes, str):
        cfg.notes = notes
    listing = _gh_contents(repo, f"{OVERLAY_DIR}/rubrics", ref)
    for entry in listing if isinstance(listing, list) else []:
        name = entry.get("name", "")
        if entry.get("type") == "file" and name.endswith(".md") and RUBRIC_NAME.fullmatch(name[:-3]):
            text = _gh_contents(repo, f"{OVERLAY_DIR}/rubrics/{name}", ref)
            if isinstance(text, str):
                cfg.rubric_overrides[name[:-3]] = text
    return cfg


def load_local(path, profile=None, detect=None):
    """Config from a local `.lean-review.toml`; overlays from a `.lean-review/` beside it.
    `detect`, when given, is called to find a profile if neither `profile` nor the file names one."""
    path = pathlib.Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    text = path.read_text()
    cfg = parse(text, _base_layer(text, profile, detect), profile)
    overlay = path.parent / OVERLAY_DIR
    if (overlay / "common.md").is_file():
        cfg.notes = (overlay / "common.md").read_text()
    for p in sorted((overlay / "rubrics").glob("*.md")) if (overlay / "rubrics").is_dir() else []:
        if RUBRIC_NAME.fullmatch(p.stem):
            cfg.rubric_overrides[p.stem] = p.read_text()
    return cfg


_IF_BLOCK = re.compile(r"<!-- if (\w+) -->\n?(.*?)<!-- end -->\n?", re.S)


def render_template(text, values):
    """Fill `{{key}}` placeholders, keeping a `<!-- if key -->…<!-- end -->` block only when that
    value is non-empty."""
    text = _IF_BLOCK.sub(lambda m: m.group(2) if values.get(m.group(1)) else "", text)
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text
