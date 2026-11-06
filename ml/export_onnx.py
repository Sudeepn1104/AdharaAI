"""
export_onnx.py - convert the trained dual-head InLegalBERT checkpoint to a
small int8 ONNX model that runs without PyTorch (fits Catalyst's 2 GB RAM).

Run in Colab or locally, after training:

    python ml/export_onnx.py \
        --checkpoint adharaai/backend/models/inlegalbert \
        --out adharaai/artifacts/inlegalbert_onnx \
        --check-csv adharaai/Data/adharaai_deployment_ready_v3.csv

The checkpoint folder must hold: config.json, tokenizer files,
model.safetensors and label_encoders.pkl (same layout classifier.py reads).

Output folder:
    model.onnx          int8-quantized, both heads (risk_logits, type_logits)
    tokenizer.json      fast tokenizer (loaded with the `tokenizers` library)
    labels.json         {"risk": [...], "type": [...]}  (no pickle in prod)
    export_report.json  parity check: ONNX int8 vs PyTorch agreement

Stops with exit code 1 if ONNX disagrees with PyTorch on more than 2% of
clauses, so a broken export never reaches deployment.
"""

import argparse
import json
import os
import pickle
import sys

import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import load_file
from transformers import AutoConfig, AutoModel, AutoTokenizer

MAX_LEN = 256
MIN_AGREEMENT = 0.98


class InLegalBERTMultiHead(nn.Module):
    """Same architecture as backend/services/classifier.py (CLS pooling)."""

    def __init__(self, path, num_risk, num_type):
        super().__init__()
        config = AutoConfig.from_pretrained(path)
        self.bert = AutoModel.from_pretrained(path)
        self.dropout = nn.Dropout(0.1)
        self.risk_head = nn.Linear(config.hidden_size, num_risk)
        self.type_head = nn.Linear(config.hidden_size, num_type)

    def forward(self, input_ids, attention_mask):
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.dropout(out.last_hidden_state[:, 0, :])
        return self.risk_head(cls), self.type_head(cls)


def load_checkpoint(path):
    with open(os.path.join(path, "label_encoders.pkl"), "rb") as f:
        enc = pickle.load(f)
    risk_labels = [str(c) for c in enc["risk_encoder"].classes_]
    type_labels = [str(c) for c in enc["type_encoder"].classes_]

    model = InLegalBERTMultiHead(path, len(risk_labels), len(type_labels))
    state = load_file(os.path.join(path, "model.safetensors"))
    missing, _ = model.load_state_dict(state, strict=False)
    bad = [k for k in missing if k.startswith(("risk_head", "type_head"))]
    if bad:
        sys.exit(f"Head weights missing from checkpoint: {bad}")
    model.eval()
    return model, AutoTokenizer.from_pretrained(path), risk_labels, type_labels


def export(model, tokenizer, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    fp32_path = os.path.join(out_dir, "model_fp32.onnx")
    sample = tokenizer("The tenant shall pay rent monthly.", return_tensors="pt",
                       truncation=True, max_length=MAX_LEN)
    torch.onnx.export(
        model,
        (sample["input_ids"], sample["attention_mask"]),
        fp32_path,
        input_names=["input_ids", "attention_mask"],
        output_names=["risk_logits", "type_logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "risk_logits": {0: "batch"},
            "type_logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )

    from onnxruntime.quantization import QuantType, quantize_dynamic
    int8_path = os.path.join(out_dir, "model.onnx")
    quantize_dynamic(fp32_path, int8_path, weight_type=QuantType.QInt8)
    os.remove(fp32_path)
    tokenizer.backend_tokenizer.save(os.path.join(out_dir, "tokenizer.json"))
    return int8_path


def parity_check(model, tokenizer, onnx_path, texts):
    import onnxruntime as ort
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    agree_risk = agree_type = 0
    for text in texts:
        enc = tokenizer(text, return_tensors="np", truncation=True, max_length=MAX_LEN)
        ids = enc["input_ids"].astype(np.int64)
        mask = enc["attention_mask"].astype(np.int64)
        with torch.no_grad():
            t_risk, t_type = model(torch.from_numpy(ids), torch.from_numpy(mask))
        o_risk, o_type = sess.run(None, {"input_ids": ids, "attention_mask": mask})
        agree_risk += int(t_risk.argmax(1).item() == o_risk.argmax(1)[0])
        agree_type += int(t_type.argmax(1).item() == o_type.argmax(1)[0])
    n = max(len(texts), 1)
    return agree_risk / n, agree_type / n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-csv", required=True, help="CSV with a clause_text column")
    args = ap.parse_args()

    import pandas as pd
    texts = pd.read_csv(args.check_csv)["clause_text"].dropna().astype(str).tolist()

    model, tokenizer, risk_labels, type_labels = load_checkpoint(args.checkpoint)
    onnx_path = export(model, tokenizer, args.out)
    with open(os.path.join(args.out, "labels.json"), "w") as f:
        json.dump({"risk": risk_labels, "type": type_labels}, f, indent=2)

    risk_agree, type_agree = parity_check(model, tokenizer, onnx_path, texts)
    report = {
        "clauses_checked": len(texts),
        "risk_agreement": round(risk_agree, 4),
        "type_agreement": round(type_agree, 4),
        "onnx_size_mb": round(os.path.getsize(onnx_path) / 1e6, 1),
        "min_agreement_required": MIN_AGREEMENT,
    }
    with open(os.path.join(args.out, "export_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))

    if min(risk_agree, type_agree) < MIN_AGREEMENT:
        sys.exit("ONNX int8 disagrees with PyTorch too often - do not deploy this export.")


if __name__ == "__main__":
    main()
