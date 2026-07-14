"""End-to-end CLI tests driven by the bundled Alice in Wonderland PDF.

Covers:
  1. extract-sentences always writes into a ``chunks/`` folder (even when
     --max-chunk-minutes=0), so validate-corpus can point at that directory.
  2. validate-corpus / convert-to-altavo-csv glob all ``*.txt`` files in any
     directory and enumerate them by the ``<num>_<name>.<ext>`` prefix.
"""

import sys
from pathlib import Path

import pytest

from text_conversion import extract_sentences, validate_corpus

ALICE_PDF = Path(__file__).parent / "data" / "alice-in-wonderland.pdf"


def _run(main, argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", argv)
    return main()


@pytest.mark.skipif(not ALICE_PDF.exists(), reason="Alice PDF test fixture missing")
def test_single_output_goes_into_chunks_folder(tmp_path, monkeypatch):
    """--max-chunk-minutes=0 still lands in chunks/ as a single 0001_ file."""
    out = tmp_path / "alice.txt"
    rc = _run(
        extract_sentences.main,
        ["extract-sentences", str(ALICE_PDF), "--output", str(out), "--no-plot-charts"],
        monkeypatch,
    )
    assert rc == 0

    chunks_dir = tmp_path / "chunks"
    files = sorted(chunks_dir.glob("*.txt"))
    assert [f.name for f in files] == ["0001_alice.txt"]
    # Nothing is written directly at the output path anymore.
    assert not out.exists()
    assert files[0].read_text(encoding="utf-8").strip()


@pytest.mark.skipif(not ALICE_PDF.exists(), reason="Alice PDF test fixture missing")
def test_chunked_naming_and_charts(tmp_path, monkeypatch):
    """Chunked output is named <num>_<output_name>.<ext> with matching charts."""
    out = tmp_path / "alice.txt"
    rc = _run(
        extract_sentences.main,
        ["extract-sentences", str(ALICE_PDF), "--output", str(out), "--max-chunk-minutes", "2"],
        monkeypatch,
    )
    assert rc == 0

    chunks_dir = tmp_path / "chunks"
    files = sorted(chunks_dir.glob("*.txt"))
    assert len(files) > 1
    assert [f.name for f in files] == [f"{i:04d}_alice.txt" for i in range(1, len(files) + 1)]

    charts = sorted((chunks_dir / "charts").glob("*.png"))
    assert len(charts) == len(files)
    assert all("chunk" not in c.name for c in charts)


@pytest.mark.skipif(not ALICE_PDF.exists(), reason="Alice PDF test fixture missing")
def test_validate_corpus_globs_all_txt_in_any_folder(tmp_path, monkeypatch, capsys):
    """validate-corpus finds enumerated files in an arbitrarily-named folder."""
    out = tmp_path / "alice.txt"
    _run(
        extract_sentences.main,
        [
            "extract-sentences", str(ALICE_PDF), "--output", str(out),
            "--max-chunk-minutes", "2", "--no-plot-charts",
        ],
        monkeypatch,
    )

    # Rename the chunks folder to something that does NOT contain "chunk" —
    # this is the folder that previously broke validate-corpus.
    weird_dir = tmp_path / "xunks"
    (tmp_path / "chunks").rename(weird_dir)

    rc = _run(
        validate_corpus.main,
        ["validate-corpus", str(weird_dir), "--min-length", "5", "--max-length", "25"],
        monkeypatch,
    )
    assert rc == 0

    output = capsys.readouterr().out
    names = [f.name for f in sorted(weird_dir.glob("*.txt"))]
    # Files are the enumerated <num>_alice.txt names and each is reported.
    assert names == [f"{i:04d}_alice.txt" for i in range(1, len(names) + 1)]
    for name in names:
        assert name in output
