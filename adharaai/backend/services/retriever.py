"""
retriever.py - retrieval simplifier (replaces the cut Ollama/Mistral RAG plan).

For each uploaded clause, find the most similar clause in AdharaAI's vetted
dataset (MiniLM embeddings + cosine similarity) and reuse that row's
hand-written plain-English explanation and tip.

Safety rules:
  * Below SIMILARITY_THRESHOLD -> no match; the regex simplifier is used.
  * A vetted explanation or tip that contains digits (amounts, dates, day
    numbers) belongs to another agreement, so it is never shown to a user.
  * Any error -> no match. The app never fails because of the retriever.

Index files are built by ml/build_retriever_index.py.
"""

import json
import logging
import os
import re
import threading

import numpy as np

logger = logging.getLogger("adharaai")

_HERE = os.path.dirname(__file__)
INDEX_PATH = os.environ.get(
    "ADHARA_RETRIEVER_PATH",
    os.path.normpath(os.path.join(_HERE, "..", "..", "artifacts", "retriever")),
)
EMBED_CACHE = os.environ.get("ADHARA_EMBED_CACHE") or None
SIMILARITY_THRESHOLD = float(os.environ.get("ADHARA_SIMILARITY_THRESHOLD", "0.75"))

_HAS_NUMBER = re.compile(r"\d")

_embeddings = None
_meta = None
_embedder = None  # callable: list[str] -> np.ndarray [n, d]
_loaded = False
_lock = threading.Lock()


def _default_embedder(model_name):
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name, cache_dir=EMBED_CACHE)

    def run(texts):
        return np.array(list(model.embed(texts)), dtype=np.float32)
    return run


def load(embedder=None) -> bool:
    """Load the index. `embedder` lets tests pass a fake one."""
    global _embeddings, _meta, _embedder, _loaded
    if _loaded:
        return True
    with _lock:
        if _loaded:
            return True
        try:
            emb_file = os.path.join(INDEX_PATH, "embeddings.npy")
            meta_file = os.path.join(INDEX_PATH, "meta.json")
            if not (os.path.exists(emb_file) and os.path.exists(meta_file)):
                logger.warning(f"Retriever index not found at {INDEX_PATH}. Regex simplifier only.")
                return False
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            embeddings = np.load(emb_file)
            if len(meta["rows"]) != len(embeddings):
                logger.error("Retriever index and meta.json row counts differ - not using it.")
                return False
            _embedder = embedder or _default_embedder(meta["model"])
            _embeddings, _meta, _loaded = embeddings, meta["rows"], True
            logger.info(f"Retriever loaded: {len(_meta)} vetted clauses")
            return True
        except Exception as e:
            logger.error(f"Failed to load retriever: {e}")
            return False


def is_available() -> bool:
    return load()


def match_many(texts: list) -> list:
    """Return one dict per text: {score, simplified_text, tip, clause_type}
    or None when there is no safe match."""
    if not texts or not load():
        return [None] * len(texts)
    try:
        q = _embedder(texts)
        q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-12)
        sims = q @ _embeddings.T
        out = []
        for row_sims in sims:
            i = int(row_sims.argmax())
            score = float(row_sims[i])
            if score < SIMILARITY_THRESHOLD:
                out.append(None)
                continue
            row = _meta[i]
            explanation = row["simplified_text"]
            tip = row.get("tip", "")
            out.append({
                "score": round(score, 3),
                "simplified_text": None if _HAS_NUMBER.search(explanation) else explanation,
                "tip": None if (not tip or _HAS_NUMBER.search(tip)) else tip,
                "clause_type": row["clause_type"],
            })
        return out
    except Exception as e:
        logger.error(f"Retriever error: {e}")
        return [None] * len(texts)
