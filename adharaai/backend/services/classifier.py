"""
classifier.py - InLegalBERT dual-head clause classifier (risk_level + clause_type).

Load order (first one that works wins):
  1. ONNX int8 model at artifacts/inlegalbert_onnx/   (production: no PyTorch)
  2. PyTorch checkpoint at backend/models/inlegalbert/ (local dev)
  3. Neither -> fail closed: every call returns source="fallback" and the
     app runs on rules only.

torch/transformers are imported only inside the PyTorch path, so the
production image does not need them installed.
"""

import json
import logging
import os
import pickle
import threading

import numpy as np

logger = logging.getLogger("adharaai")

_HERE = os.path.dirname(__file__)
MODEL_PATH = os.path.normpath(os.path.join(_HERE, "..", "models", "inlegalbert"))
ONNX_PATH = os.environ.get(
    "ADHARA_ONNX_PATH",
    os.path.normpath(os.path.join(_HERE, "..", "..", "artifacts", "inlegalbert_onnx")),
)
MAX_LEN = 256

# Shared state (tests reset these)
_tokenizer = None
_model = None
_risk_encoder = None
_type_encoder = None
_model_loaded = False

_onnx_session = None
_onnx_tokenizer = None
_labels = None
_backend = None  # "onnx" | "torch" | None

_lock = threading.Lock()

FALLBACK = {
    "risk_level": "low",
    "clause_type": "standard",
    "risk_confidence": 0,
    "type_confidence": 0,
    "source": "fallback",
}


# ── ONNX path (production) ────────────────────────────────────────────────────

def _load_onnx() -> bool:
    global _onnx_session, _onnx_tokenizer, _labels, _backend, _model_loaded
    model_file = os.path.join(ONNX_PATH, "model.onnx")
    if not os.path.exists(model_file):
        return False
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        with open(os.path.join(ONNX_PATH, "labels.json")) as f:
            labels = json.load(f)
        if not labels.get("risk") or not labels.get("type"):
            logger.error("labels.json is missing risk/type labels - not using ONNX model")
            return False

        tok = Tokenizer.from_file(os.path.join(ONNX_PATH, "tokenizer.json"))
        tok.enable_truncation(max_length=MAX_LEN)
        tok.no_padding()

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # small, predictable CPU/RAM use on AppSail
        session = ort.InferenceSession(model_file, opts, providers=["CPUExecutionProvider"])

        _onnx_session, _onnx_tokenizer, _labels = session, tok, labels
        _backend, _model_loaded = "onnx", True
        logger.info(f"InLegalBERT ONNX model loaded from {ONNX_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to load ONNX model: {e}")
        _onnx_session = None
        return False


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


def _classify_onnx(clause_text: str) -> dict:
    enc = _onnx_tokenizer.encode(clause_text)
    ids = np.array([enc.ids], dtype=np.int64)
    mask = np.array([enc.attention_mask], dtype=np.int64)
    risk_logits, type_logits = _onnx_session.run(
        ["risk_logits", "type_logits"], {"input_ids": ids, "attention_mask": mask}
    )
    risk_p, type_p = _softmax(risk_logits[0]), _softmax(type_logits[0])
    r, t = int(risk_p.argmax()), int(type_p.argmax())
    return {
        "risk_level": _labels["risk"][r],
        "clause_type": _labels["type"][t],
        "risk_confidence": round(float(risk_p[r]) * 100),
        "type_confidence": round(float(type_p[t]) * 100),
        "source": "bert",
    }


# ── PyTorch path (local dev) ──────────────────────────────────────────────────

def _load_torch() -> bool:
    global _tokenizer, _model, _risk_encoder, _type_encoder, _model_loaded, _backend

    if not os.path.exists(MODEL_PATH):
        return False
    weights_path = os.path.join(MODEL_PATH, "model.safetensors")
    if not os.path.exists(weights_path):
        logger.error(
            f"No model.safetensors at {weights_path} - refusing to serve "
            f"predictions from untrained heads. Using rules only."
        )
        return False

    try:
        import torch.nn as nn
        from safetensors.torch import load_file
        from transformers import AutoConfig, AutoModel, AutoTokenizer

        class InLegalBERTMultiHead(nn.Module):
            def __init__(self, path, num_risk, num_type):
                super().__init__()
                self.config = AutoConfig.from_pretrained(path)
                self.bert = AutoModel.from_pretrained(path)
                self.dropout = nn.Dropout(0.1)
                self.risk_head = nn.Linear(self.config.hidden_size, num_risk)
                self.type_head = nn.Linear(self.config.hidden_size, num_type)

            def forward(self, input_ids=None, attention_mask=None, **kwargs):
                out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
                # Raw CLS token: 91.1% on the diagnostic check vs 24.4% for
                # pooler_output. This is what the model was trained on.
                pooled = self.dropout(out.last_hidden_state[:, 0, :])
                return self.risk_head(pooled), self.type_head(pooled)

        with open(os.path.join(MODEL_PATH, "label_encoders.pkl"), "rb") as f:
            enc = pickle.load(f)
        risk_enc, type_enc = enc["risk_encoder"], enc["type_encoder"]

        model = InLegalBERTMultiHead(MODEL_PATH, len(risk_enc.classes_), len(type_enc.classes_))
        missing, unexpected = model.load_state_dict(load_file(weights_path), strict=False)
        critical = [k for k in missing if k.startswith(("risk_head", "type_head"))]
        if critical:
            logger.error(f"Critical weights missing: {critical}. Using rules only.")
            return False
        if missing or unexpected:
            logger.warning(f"Non-critical state dict mismatch (missing={missing}, unexpected={unexpected})")

        model.eval()
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        _model, _risk_encoder, _type_encoder = model, risk_enc, type_enc
        _backend, _model_loaded = "torch", True
        logger.info("InLegalBERT PyTorch checkpoint loaded")
        return True
    except Exception as e:
        logger.error(f"Failed to load InLegalBERT: {e}")
        _model = None
        return False


def _classify_torch(clause_text: str) -> dict:
    import torch

    inputs = _tokenizer(clause_text, return_tensors="pt", max_length=MAX_LEN, truncation=True)
    with torch.no_grad():
        risk_logits, type_logits = _model(
            input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"]
        )
    risk_p = torch.softmax(risk_logits, dim=1)[0]
    type_p = torch.softmax(type_logits, dim=1)[0]
    r, t = risk_p.argmax().item(), type_p.argmax().item()
    return {
        "risk_level": str(_risk_encoder.classes_[r]),
        "clause_type": str(_type_encoder.classes_[t]),
        "risk_confidence": round(risk_p[r].item() * 100),
        "type_confidence": round(type_p[t].item() * 100),
        "source": "bert",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def _load_model() -> bool:
    if _model_loaded:
        return True
    with _lock:
        if _model_loaded:
            return True
        if _load_onnx() or _load_torch():
            return True
        logger.warning("No InLegalBERT model found (ONNX or PyTorch). Using rules only.")
        return False


def classify_clause(clause_text: str) -> dict:
    if not _load_model():
        return dict(FALLBACK)
    try:
        if _backend == "onnx":
            return _classify_onnx(clause_text)
        return _classify_torch(clause_text)
    except Exception as e:
        logger.error(f"BERT error: {e}")
        return dict(FALLBACK)


def is_available() -> bool:
    return _load_model()


def backend_name() -> str:
    """'onnx', 'torch' or 'none' - shown on /health."""
    return _backend if _model_loaded else "none"
