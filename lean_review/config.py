"""Per-project configuration: `.lean-review.toml` plus optional prompt overlays.

Everything here is read from the target repository's BASE commit (or a local path the operator
names), never from the PR head: the head is written by the PR author, and a config or rubric
overlay taken from it would let the author rewrite their own review.
"""

import base64, dataclasses, json, pathlib, re, subprocess, tomllib

CONFIG_FILE = ".lean-review.toml"
OVERLAY_DIR = ".lean-review"
RUBRICS_DIR = pathlib.Path(__file__).resolve().parent / "rubrics"

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
    ci_check: str = "build"
    # Overlays: project notes appended to the shared protocol, and rubric texts that add to or
    # replace the built-in ones (name -> markdown).
    notes: str = ""
    rubric_overrides: dict = dataclasses.field(default_factory=dict)

    def rubric_text(self, name):
        if name in self.rubric_overrides:
            return self.rubric_overrides[name]
        path = RUBRICS_DIR / f"{name}.md"
        if not path.is_file():
            raise ConfigError(f"unknown rubric {name!r}: no built-in rubric and no "
                              f"{OVERLAY_DIR}/rubrics/{name}.md overlay")
        return path.read_text()

    def placeholders(self):
        return {"project": self.project, "description": self.description,
                "source_root": self.source_root or ".", "namespace": self.namespace}


def parse(text, cfg=None):
    """Apply a `.lean-review.toml` document to `cfg` (a default Config if None)."""
    cfg = cfg or Config()
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{CONFIG_FILE}: {e}")
    fields = {f.name for f in dataclasses.fields(Config)} - {"notes", "rubric_overrides"}
    for key, value in data.items():
        if key not in fields:
            raise ConfigError(f"{CONFIG_FILE}: unknown key {key!r}")
        expected = type(getattr(Config(), key))
        if not isinstance(value, expected):
            raise ConfigError(f"{CONFIG_FILE}: {key} must be a {expected.__name__}")
        setattr(cfg, key, value)
    validate(cfg)
    return cfg


def validate(cfg):
    if cfg.mode not in MODES:
        raise ConfigError(f"mode must be one of {', '.join(MODES)}, not {cfg.mode!r}")
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


def load_remote(repo, ref):
    """Config and overlays from `repo` at commit `ref` (the PR's base). Missing files are fine."""
    cfg = Config()
    text = _gh_contents(repo, CONFIG_FILE, ref)
    if isinstance(text, str):
        parse(text, cfg)
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


def load_local(path):
    """Config from a local `.lean-review.toml`; overlays from a `.lean-review/` beside it."""
    path = pathlib.Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    cfg = parse(path.read_text())
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
