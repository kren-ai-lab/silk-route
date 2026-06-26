"""Offline tests for the BLAST utilities.

Only the pure, network-free parts: tabular result parsing + identity filtering,
the latest-version regex (with a mocked HTTP fetch), and the guard clauses that
raise before any subprocess or download runs. The subprocess/FTP orchestration
(``run_blast``, ``make_blast_database`` execution, ``download_*``) is left
untested — it needs heavy mocking for little behavioral payoff.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

from bioseq_dl.core.utils import blast_search

# A BLAST outfmt-6 row: qseqid sseqid pident length evalue bitscore qcovs
ROW_95 = "q1\ts1\t95.0\t100\t1e-50\t200\t98"
ROW_80 = "q2\ts2\t80.0\t90\t1e-20\t150\t90"


# --- parse_blast_results ----------------------------------------------------


def _write(tmp_path, *rows):
    path = tmp_path / "blast_results.txt"
    path.write_text("\n".join(rows) + "\n")
    return str(path)


def test_parse_keeps_hits_at_or_above_threshold(tmp_path):
    results = blast_search.parse_blast_results(_write(tmp_path, ROW_95, ROW_80), identity_threshold=90.0)
    assert [r["subject"] for r in results] == ["s1"]  # 80% dropped


def test_parse_maps_all_columns(tmp_path):
    [hit] = blast_search.parse_blast_results(_write(tmp_path, ROW_95))
    assert hit == {
        "query": "q1",
        "subject": "s1",
        "identity": "95.0",
        "alignment_length": "100",
        "evalue": "1e-50",
        "bit_score": "200",
        "coverage": "98",
    }


def test_parse_threshold_is_inclusive(tmp_path):
    results = blast_search.parse_blast_results(_write(tmp_path, ROW_95), identity_threshold=95.0)
    assert len(results) == 1


def test_parse_default_threshold_is_90(tmp_path):
    # ROW_80 is below the 90.0 default and must be dropped.
    assert blast_search.parse_blast_results(_write(tmp_path, ROW_80)) == []


def test_parse_skips_blank_and_malformed_lines(tmp_path):
    # Blank lines and short rows must be skipped, not crash (was an IndexError).
    path = tmp_path / "blast_results.txt"
    path.write_text(f"{ROW_95}\n\n  \nq3\ts3\n")  # blank, whitespace, and a 2-field row
    results = blast_search.parse_blast_results(path.as_posix())
    assert [r["subject"] for r in results] == ["s1"]


# --- get_latest_version_url -------------------------------------------------


@contextmanager
def _fake_urlopen(html: str):
    class _Resp:
        def read(self):
            return html.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    yield _Resp()


def test_get_latest_version_url_parses_tarball(monkeypatch):
    html = 'href="ncbi-blast-2.16.0+-x64-linux.tar.gz"'
    monkeypatch.setattr(blast_search, "urlopen", lambda _url: _fake_urlopen(html))
    version, url = blast_search.get_latest_version_url()
    assert version == "2.16.0+"
    assert url.endswith("ncbi-blast-2.16.0+-x64-linux.tar.gz")


def test_get_latest_version_url_raises_when_absent(monkeypatch):
    monkeypatch.setattr(blast_search, "urlopen", lambda _url: _fake_urlopen("<html>nothing</html>"))
    with pytest.raises(RuntimeError, match="Could not find the latest BLAST version"):
        blast_search.get_latest_version_url()


# --- guard clauses (raise before any network/subprocess) --------------------


def test_download_unsupported_database_raises():
    with pytest.raises(ValueError, match="is not supported"):
        blast_search.download_uniprot_database("not_a_real_db")


def test_make_database_missing_source_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(blast_search, "DB_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="Please download it first"):
        blast_search.make_blast_database("absent")


def test_run_blast_missing_database_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(blast_search, "DB_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match="Please download it first"):
        blast_search.run_blast(["MSEQ"], "absent")
