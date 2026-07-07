"""Offline tests for the BLAST utilities.

Only the pure, network-free parts: CSV result parsing + identity filtering,
``check_blast`` executable resolution, and the guard clauses that raise before
any subprocess or download runs. The subprocess execution (``run_blast``,
``make_blast_database``) and the UniProt DB download are left untested — they
need heavy mocking for little behavioral payoff.
"""

from __future__ import annotations

import pytest

from bioseq_dl.core.utils import blast_search

# A BLAST outfmt-10 (CSV) row: qseqid,sseqid,pident,length,evalue,bitscore,qcovs
ROW_95 = "q1,s1,95.0,100,1e-50,200,98"
ROW_80 = "q2,s2,80.0,90,1e-20,150,90"


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
    path.write_text(f"{ROW_95}\n\nq3,s3\n")  # blank line and a 2-field row
    results = blast_search.parse_blast_results(path.as_posix())
    assert [r["subject"] for r in results] == ["s1"]


# --- check_blast ------------------------------------------------------------


def test_check_blast_returns_resolved_path(monkeypatch):
    monkeypatch.setattr(blast_search.shutil, "which", lambda prog: f"/usr/bin/{prog}")
    assert blast_search.check_blast() == "/usr/bin/blastp"
    assert blast_search.check_blast("blastn") == "/usr/bin/blastn"


def test_check_blast_raises_with_install_hint_when_missing(monkeypatch):
    monkeypatch.setattr(blast_search.shutil, "which", lambda _prog: None)
    with pytest.raises(RuntimeError, match="pixi global add blast"):
        blast_search.check_blast()


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
