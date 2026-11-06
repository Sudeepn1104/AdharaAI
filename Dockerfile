# AdharaAI production image - Zoho Catalyst AppSail (custom runtime).
# Also works on Render (it reads $PORT).
#
# Build (from the repo root, on any machine - Catalyst needs linux/amd64):
#   docker build --platform linux/amd64 \
#     --build-arg HF_MODEL_REPO=Sudeepn1104/adharaai-inlegalbert-onnx \
#     --build-arg HF_MODEL_REVISION=v1 \
#     -t adharaai:v1 .
#
# Leave HF_MODEL_REPO empty to build a rules-only image (no InLegalBERT).
#
# AppSail limits this image is designed around:
#   * must listen within 10 s  -> models load in the background after start
#   * 2 GB RAM max             -> ONNX int8, no PyTorch in this image
#   * 30 s request timeout

# ── Stage 1: fetch model + build the retrieval index ─────────────────────────
FROM --platform=linux/amd64 python:3.12-slim AS models

ARG HF_MODEL_REPO=""
ARG HF_MODEL_REVISION="main"
ENV PIP_NO_CACHE_DIR=1

RUN pip install fastembed==0.9.1 onnxruntime==1.29.0 tokenizers==0.23.3 pandas huggingface_hub

WORKDIR /build
COPY ml/build_retriever_index.py ml/
COPY adharaai/Data/adharaai_deployment_ready_v3.csv data/

# Retrieval index + MiniLM embedding model (cached inside the image, so no
# download at startup)
RUN python ml/build_retriever_index.py \
      --csv data/adharaai_deployment_ready_v3.csv \
      --out artifacts/retriever \
      --cache-dir artifacts/fastembed_cache

# InLegalBERT ONNX export (made by ml/export_onnx.py, uploaded to HF Hub).
# The revision should be a tag like v1, so every image maps to one model version.
RUN mkdir -p artifacts/inlegalbert_onnx && if [ -n "$HF_MODEL_REPO" ]; then \
      python -c "from huggingface_hub import snapshot_download; \
snapshot_download('$HF_MODEL_REPO', revision='$HF_MODEL_REVISION', \
local_dir='artifacts/inlegalbert_onnx', \
allow_patterns=['model.onnx','tokenizer.json','labels.json','export_report.json'])" ; \
    else echo 'HF_MODEL_REPO not set - building rules-only image'; fi

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM --platform=linux/amd64 python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ADHARA_EMBED_CACHE=/app/adharaai/artifacts/fastembed_cache \
    HF_HUB_OFFLINE=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/adharaai
COPY adharaai/requirements-prod.txt ./requirements-prod.txt
RUN pip install -r requirements-prod.txt

COPY adharaai/ ./
COPY --from=models /build/artifacts ./artifacts

# Run as a non-root user
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 9000

# One worker keeps a single copy of the models in RAM.
# Catalyst sets X_ZOHO_CATALYST_LISTEN_PORT; Render sets PORT; default 9000.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT:-${PORT:-9000}} --workers 1"]
