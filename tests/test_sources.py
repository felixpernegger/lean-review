import gzip, io, tarfile, urllib.parse

from lean_review import sources
from lean_review.sources import SOURCES_DIR, cited_sources


def kinds(found):
    return [(s.kind, s.ident) for s in found]


def test_citations_from_paths_text_and_description():
    files = {
        "FormalConjectures/ErdosProblems/790.lean": "[erdosproblems.com/790](https://www.erdosproblems.com/790).",
        "FormalConjectures/Kourovka/5_59.lean": "*Reference:* [Notebook](https://arxiv.org/abs/1401.0300v50)",
        "FormalConjectures/Arxiv/0812.1418/Oda.lean": "Tu, https://arxiv.org/abs/2511.04322v1 and arXiv:2511.04322",
        "FormalConjectures/OEIS/45.lean": "See https://oeis.org/A000045 .",
    }
    desc = "Background: [Borel](https://en.wikipedia.org/wiki/Borel_conjecture), " \
           "https://en.wikipedia.org/wiki/Hilbert%27s_seventh_problem and erdosproblems.com/790."
    assert kinds(cited_sources(files, desc)) == [
        ("erdos", "790"),
        # The notebook is always its latest version, whatever version the file cites.
        ("arxiv", "1401.0300"),
        ("arxiv", "0812.1418"),
        ("arxiv", "2511.04322v1"),      # the first version cited is kept
        ("oeis", "A000045"),
        ("wikipedia", "Borel_conjecture"),
        ("wikipedia", "Hilbert's_seventh_problem"),
    ]
    found = cited_sources(files, desc)
    assert found[0].cited == "FormalConjectures/ErdosProblems/790.lean"
    assert found[-1].cited == "the PR description"
    assert "Kourovka Notebook" in found[1].label


def test_wikipedia_titles_with_parentheses_and_the_cap():
    text = "[x](https://en.wikipedia.org/wiki/Collatz_(conjecture)) and " \
           + " ".join(f"erdosproblems.com/{n}" for n in range(1, 20))
    found = cited_sources({"F.lean": text})
    assert found[0].ident == "Collatz_(conjecture)" and len(found) == sources.MAX_SOURCES


def test_urls_are_built_on_fixed_hosts():
    """Whatever the PR writes, only an identifier is kept and the host is the runner's choice."""
    text = ("https://evil.example/erdosproblems.com/7 http://127.0.0.1/arxiv.org/abs/2101.00001 "
            "https://en.wikipedia.org/wiki/x%2F..%2F..%2Fadmin oeis.org/A000001")
    hosts = {"www.erdosproblems.com", "arxiv.org", "oeis.org", "en.wikipedia.org",
             "raw.githubusercontent.com"}
    seen = []
    orig = sources._get
    try:
        sources._get = lambda url: seen.append(url) or b"<p>x</p>"
        for s in cited_sources({"F.lean": text}):
            assert urllib.parse.urlparse(s.url).hostname in hosts
            try:
                sources.fetch(s)
            except Exception:
                pass
    finally:
        sources._get = orig
    assert seen and all(urllib.parse.urlparse(u).hostname in hosts for u in seen)
    assert all(u.startswith("https://") for u in seen)


def test_html_to_text():
    page = ("<html><script>var a = '<p>no</p>';</script><style>p{}</style><h1>#790</h1>"
            "<p>Let $l(n)$ be &lt; $n$&amp;</p><div>Is it   true?</div></html>")
    assert sources.html_to_text(page) == "#790\nLet $l(n)$ be < $n$&\nIs it true?\n"


def tar_gz(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_stage_writes_index_and_flattens_archives(tmp_path, monkeypatch):
    root = tmp_path / "code"
    (root / "FC" / "Kourovka").mkdir(parents=True)
    (root / "FC" / "Kourovka" / "5_59.lean").write_text("-- Kourovka 5.59")
    (root / "FC" / "Paper.lean").write_text("arXiv:2101.00001 and https://www.erdosproblems.com/12")
    pages = {
        "https://arxiv.org/e-print/1401.0300": tar_gz({
            "21tkt.tex": b"\\textbf{5.59.}\r\nLet $G$ be locally finite.\r\n",
            "../../escape.tex": b"outside?", "kt.cls": b"class", "fig.png": b"\x89PNG"}),
        "https://arxiv.org/e-print/2101.00001": b"%PDF-1.5 ...",
        "https://arxiv.org/html/2101.00001": b"<p>Conjecture 1.1</p>",
    }

    def get(url):
        if url not in pages:
            raise sources.FetchError("HTTP Error 404: Not Found")
        return pages[url]
    monkeypatch.setattr(sources, "_get", get)
    log = []
    found = sources.stage(root, ["FC/Kourovka/5_59.lean", "FC/Paper.lean", "FC/Gone.lean"],
                          "# t", log.append)
    d = root / SOURCES_DIR
    assert kinds(found) == [("arxiv", "1401.0300"), ("arxiv", "2101.00001"), ("erdos", "12")]
    tex = d / "arxiv-1401.0300" / "21tkt.tex"
    assert tex.read_text() == "\\textbf{5.59.}\nLet $G$ be locally finite.\n"
    # Archive members are flattened into the source's folder: nothing escapes it.
    assert (d / "arxiv-1401.0300" / "escape.tex").read_text() == "outside?"
    assert sorted(p.name for p in (d / "arxiv-1401.0300").iterdir()) == ["21tkt.tex", "escape.tex"]
    assert not (tmp_path / "escape.tex").exists()
    # A PDF-only submission falls back to arXiv's HTML rendering.
    assert (d / "arxiv-2101.00001" / "paper.txt").read_text() == "Conjecture 1.1\n"
    index = (d / "INDEX.md").read_text()
    assert "untrusted text" in index
    assert f"`{SOURCES_DIR}/arxiv-1401.0300/21tkt.tex`" in index
    assert "Erdős Problem 12 <https://www.erdosproblems.com/12>, cited in FC/Paper.lean: " \
           "not fetched (HTTP Error 404: Not Found)" in index
    assert any(m.startswith("fetching sources: arXiv 1401.0300") for m in log)
    assert "note: could not fetch Erdős Problem 12: HTTP Error 404: Not Found" in log


def test_single_tex_eprint_and_oeis(tmp_path, monkeypatch):
    root = tmp_path
    (root / "OEIS").mkdir()
    (root / "OEIS" / "45.lean").write_text("arXiv:2101.00002")
    pages = {"https://arxiv.org/e-print/2101.00002": gzip.compress(b"\\begin{document}x"),
             "https://oeis.org/search?q=id:A000045&fmt=text": b"%N A000045 Fibonacci numbers."}
    monkeypatch.setattr(sources, "_get", pages.__getitem__)
    found = sources.stage(root, ["OEIS/45.lean"], "")
    assert [s.error for s in found] == ["", ""]
    assert (root / SOURCES_DIR / "arxiv-2101.00002" / "main.tex").read_text() == "\\begin{document}x"
    assert "Fibonacci" in (root / SOURCES_DIR / "oeis-A000045.txt").read_text()


def test_nothing_cited_and_a_pr_path_of_the_same_name(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "_get", lambda url: (_ for _ in ()).throw(AssertionError(url)))
    (tmp_path / "A.lean").write_text("theorem a : True := trivial")
    log = []
    assert sources.stage(tmp_path, ["A.lean"], "no links", log.append) == []
    assert not (tmp_path / SOURCES_DIR).exists() and "cites no source" in log[0]
    (tmp_path / "B.lean").write_text("erdosproblems.com/1")
    (tmp_path / SOURCES_DIR).write_text("the PR's own file")
    assert sources.stage(tmp_path, ["B.lean"], "", log.append) is None
    assert (tmp_path / SOURCES_DIR).read_text() == "the PR's own file"


def test_erdos_pages_carry_their_database_entry(tmp_path, monkeypatch):
    db = ('- number: "79"\n  status:\n    state: "proved"\n\n'
          '- number: "790"\n  status:\n    state: "open"\n  tags: ["additive combinatorics"]\n\n'
          '- number: "7900"\n  status:\n    state: "solved"\n')
    calls = []

    def get(url):
        calls.append(url)
        return db.encode() if url == sources.ERDOS_DB else b"<p>Let $l(n)$ be maximal</p>"
    monkeypatch.setattr(sources, "_get", get)
    (tmp_path / "E.lean").write_text("erdosproblems.com/790 erdosproblems.com/79 erdosproblems.com/5")
    sources.stage(tmp_path, ["E.lean"], "")
    page = (tmp_path / SOURCES_DIR / "erdos-790.txt").read_text()
    assert page.startswith("Let $l(n)$ be maximal\n")
    assert '- number: "790"\n  status:\n    state: "open"\n  tags:' in page
    assert '"79"' not in page and '"7900"' not in page
    assert 'state: "proved"' in (tmp_path / SOURCES_DIR / "erdos-79.txt").read_text()
    assert "database" not in (tmp_path / SOURCES_DIR / "erdos-5.txt").read_text()
    assert calls.count(sources.ERDOS_DB) == 1        # one download per run


def test_every_changed_text_file_is_scanned(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "_get", lambda url: b"text")
    (tmp_path / "BorelConjecture").write_text("[W](https://en.wikipedia.org/wiki/Borel_conjecture)")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\0 erdosproblems.com/1")
    found = sources.stage(tmp_path, ["BorelConjecture", "logo.png"], "")
    assert kinds(found) == [("wikipedia", "Borel_conjecture")]
