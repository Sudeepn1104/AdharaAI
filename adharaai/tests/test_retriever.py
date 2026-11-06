"""
test_retriever.py - retrieval simplifier: threshold, number filter, fallback.
Uses a fake embedder, so no model download is needed.
"""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

import backend.services.retriever as retriever
from backend.services.simplifier import simplify_all_clauses

ROWS = [
    {"clause_type": "deposit", "risk_level": "high",
     "simplified_text": "The owner keeps your deposit if you leave early.",
     "tip": "Ask for a written refund timeline."},
    {"clause_type": "payment", "risk_level": "low",
     "simplified_text": "You must pay Rs.25,000 rent by the 7th.",
     "tip": "Set a reminder before the 7th."},
]
VECS = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)


def fake_embedder(texts):
    out = []
    for t in texts:
        t = t.lower()
        if "deposit" in t:
            out.append([1.0, 0.1, 0.0])
        elif "rent" in t:
            out.append([0.1, 1.0, 0.0])
        else:
            out.append([0.0, 0.0, 1.0])
    return np.array(out, dtype=np.float32)


@pytest.fixture
def index(tmp_path):
    np.save(tmp_path / "embeddings.npy", VECS)
    (tmp_path / "meta.json").write_text(json.dumps({"model": "fake", "rows": ROWS}))
    real = retriever.INDEX_PATH
    retriever.INDEX_PATH = str(tmp_path)
    retriever._loaded = False
    assert retriever.load(embedder=fake_embedder)
    yield
    retriever.INDEX_PATH = real
    retriever._loaded = False


def test_close_match_reuses_vetted_text(index):
    m = retriever.match_many(["Tenant forfeits deposit on early exit"])[0]
    assert m["clause_type"] == "deposit"
    assert m["simplified_text"].startswith("The owner keeps your deposit")
    assert m["tip"] == "Ask for a written refund timeline."


def test_vetted_text_with_numbers_is_never_shown(index):
    m = retriever.match_many(["Monthly rent payable"])[0]
    assert m is not None
    assert m["simplified_text"] is None  # has Rs.25,000 / 7th from another agreement
    assert m["tip"] is None


def test_unrelated_clause_gets_no_match(index):
    assert retriever.match_many(["Pets are not allowed"]) == [None]


def test_simplifier_uses_retrieval_then_regex(index):
    clauses = [{"text": "Tenant forfeits deposit on early exit"},
               {"text": "Pets are not allowed hereinafter"}]
    out = simplify_all_clauses(clauses)
    assert out[0]["simplifier_source"] == "retrieval"
    assert out[0]["retrieved_tip"] == "Ask for a written refund timeline."
    assert out[1]["simplifier_source"] == "regex"


def test_missing_index_falls_back_to_regex(tmp_path):
    real = retriever.INDEX_PATH
    retriever.INDEX_PATH = str(tmp_path / "nothing_here")
    retriever._loaded = False
    try:
        out = simplify_all_clauses([{"text": "The tenant shall pay rent."}])
        assert out[0]["simplifier_source"] == "regex"
    finally:
        retriever.INDEX_PATH = real
        retriever._loaded = False
