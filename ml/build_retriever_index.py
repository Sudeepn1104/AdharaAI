"""
build_retriever_index.py - build the vector index for the retrieval simplifier.

Embeds every clause in the vetted dataset with MiniLM (via fastembed, ONNX,
no PyTorch) and saves:

    <out>/embeddings.npy   float32 [rows, 384], L2-normalised
    <out>/meta.json        per row: clause_type, risk_level, simplified_text, tip
    <out>/calibration.json leave-one-out check to pick the similarity threshold

Usage (runs inside the Docker build, or locally):

    python ml/build_retriever_index.py \
        --csv adharaai/Data/adharaai_deployment_ready_v3.csv \
        --out adharaai/artifacts/retriever

Only the vetted columns are stored. clause_text and source_file are NOT
saved in meta.json, so no source-document text ships with the app.
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REQUIRED = ["clause_text", "risk_level", "clause_type", "simplified_text", "tip"]


def embed(texts, cache_dir=None):
    from fastembed import TextEmbedding
    model = TextEmbedding(EMBED_MODEL, cache_dir=cache_dir)
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def calibrate(vecs, types):
    """Leave-one-out: for each row, find its nearest *other* row. Report how
    often the neighbour has the same clause_type at different thresholds."""
    sims = vecs @ vecs.T
    np.fill_diagonal(sims, -1.0)
    best = sims.argmax(1)
    best_score = sims.max(1)
    same = np.array([types[i] == types[j] for i, j in enumerate(best)])
    out = []
    for t in [0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85]:
        hit = best_score >= t
        out.append({
            "threshold": t,
            "coverage": round(float(hit.mean()), 3),
            "same_type_rate": round(float(same[hit].mean()), 3) if hit.any() else None,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache-dir", default=None, help="where fastembed stores the model")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"CSV is missing columns: {missing}")
    df = df.dropna(subset=["clause_text", "simplified_text"]).reset_index(drop=True)

    vecs = embed(df["clause_text"].astype(str).tolist(), args.cache_dir)
    os.makedirs(args.out, exist_ok=True)
    np.save(os.path.join(args.out, "embeddings.npy"), vecs)

    meta = [
        {
            "clause_type": str(r.clause_type),
            "risk_level": str(r.risk_level),
            "simplified_text": str(r.simplified_text),
            "tip": "" if pd.isna(r.tip) else str(r.tip),
        }
        for r in df.itertuples()
    ]
    with open(os.path.join(args.out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"model": EMBED_MODEL, "rows": meta}, f, ensure_ascii=False)

    cal = calibrate(vecs, df["clause_type"].astype(str).tolist())
    with open(os.path.join(args.out, "calibration.json"), "w") as f:
        json.dump(cal, f, indent=2)

    print(f"Indexed {len(meta)} clauses -> {args.out}")
    for row in cal:
        print(row)


if __name__ == "__main__":
    main()
