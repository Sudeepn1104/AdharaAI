"""
train_and_register.py - one run = CV score + final model + ONNX export,
all tracked in MLflow. Built from train_inlegalbert_v3_1.py (same model,
loss, class weights, grouped folds).

Colab (GPU):
    !pip -q install mlflow onnx onnxruntime
    !python ml/train_and_register.py --seeds 42 --tag v1

Steps:
  1. Data quality gate (ml/validate_data.py) - stops on a bad CSV
  2. Grouped 5-fold CV -> risk_f1 / type_f1 mean+std logged to MLflow
  3. Final model trained on ALL rows -> checkpoint in the layout
     backend/services/classifier.py reads (keys bert.*, risk_head, type_head)
  4. int8 ONNX export + parity check (ml/export_onnx.py)
  5. Decision written to metrics.json: "hybrid" if type_f1 >= 0.75 else "shadow"

Outputs (under --out, default /content/drive/MyDrive/adharaai_models/<tag>):
    checkpoint/   PyTorch weights (for local dev / future retrains)
    onnx/         model.onnx, tokenizer.json, labels.json, export_report.json,
                  metrics.json  -> this folder is what gets uploaded to HF Hub
    mlflow.db     MLflow tracking store (open with:
                  mlflow ui --backend-store-uri sqlite:///<out>/mlflow.db)
"""

import argparse
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from safetensors.torch import save_file
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

MAX_LEN = 256
HYBRID_MIN_TYPE_F1 = 0.75


# ---------------- data ----------------
class ClauseDataset(Dataset):
    def __init__(self, tokenizer, texts, risk, typ):
        self.tok, self.texts, self.risk, self.typ = tokenizer, list(texts), list(risk), list(typ)

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, i):
        enc = self.tok(self.texts[i], max_length=MAX_LEN, truncation=True,
                       padding="max_length", return_tensors="pt")
        return {"input_ids": enc["input_ids"].squeeze(0),
                "attention_mask": enc["attention_mask"].squeeze(0),
                "risk_label": torch.tensor(self.risk[i]),
                "type_label": torch.tensor(self.typ[i])}


def build_groups(frame):
    # Real rows from the same source document stay in one fold (no leakage);
    # each synthetic row is its own group.
    return np.array([f"row_{i}" if "synthetic" in s.lower() else s
                     for i, s in enumerate(frame["source_file"].astype(str))])


# ---------------- model ----------------
class DualHead(nn.Module):
    """Attribute is named `bert` so saved keys match classifier.py."""

    def __init__(self, base, n_risk, n_type, dropout):
        super().__init__()
        self.bert = AutoModel.from_pretrained(base)
        hidden = self.bert.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.risk_head = nn.Linear(hidden, n_risk)
        self.type_head = nn.Linear(hidden, n_type)

    def forward(self, input_ids, attention_mask):
        out = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.dropout(out.last_hidden_state[:, 0, :])  # CLS pooling
        return self.risk_head(cls), self.type_head(cls)


def class_weights(labels, n):
    c = np.bincount(labels, minlength=n).astype(float)
    c[c == 0] = 1.0
    w = 1.0 / c
    return torch.tensor(w / w.mean(), dtype=torch.float32)


def train(cfg, tokenizer, train_df, n_risk, n_type, seed, device):
    torch.manual_seed(seed)
    np.random.seed(seed)
    ds = ClauseDataset(tokenizer, train_df["clause_text"], train_df["risk_label"], train_df["type_label"])
    loader = DataLoader(ds, batch_size=cfg.batch_size, shuffle=True)

    model = DualHead(cfg.base_model, n_risk, n_type, cfg.dropout).to(device)
    risk_loss = nn.CrossEntropyLoss(weight=class_weights(train_df["risk_label"].values, n_risk).to(device))
    type_loss = nn.CrossEntropyLoss(weight=class_weights(train_df["type_label"].values, n_type).to(device))
    opt = torch.optim.AdamW([
        {"params": model.bert.parameters(), "lr": cfg.lr_encoder},
        {"params": list(model.risk_head.parameters()) + list(model.type_head.parameters()), "lr": cfg.lr_heads},
    ], weight_decay=0.01)
    steps = len(loader) * cfg.epochs
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)

    model.train()
    for epoch in range(cfg.epochs):
        total = 0.0
        for b in loader:
            opt.zero_grad()
            rl, tl = model(b["input_ids"].to(device), b["attention_mask"].to(device))
            loss = (cfg.risk_weight * risk_loss(rl, b["risk_label"].to(device))
                    + cfg.type_weight * type_loss(tl, b["type_label"].to(device)))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            total += loss.item()
        if epoch == 0 or (epoch + 1) % 5 == 0 or epoch + 1 == cfg.epochs:
            print(f"    epoch {epoch + 1}/{cfg.epochs} loss={total / len(loader):.4f}")
    model.eval()
    return model


def evaluate(model, tokenizer, val_df, device, batch_size):
    ds = ClauseDataset(tokenizer, val_df["clause_text"], val_df["risk_label"], val_df["type_label"])
    rp, rt, tp, tt = [], [], [], []
    with torch.no_grad():
        for b in DataLoader(ds, batch_size=batch_size):
            rl, tl = model(b["input_ids"].to(device), b["attention_mask"].to(device))
            rp += rl.argmax(1).cpu().tolist(); rt += b["risk_label"].tolist()
            tp += tl.argmax(1).cpu().tolist(); tt += b["type_label"].tolist()
    return (f1_score(rt, rp, average="macro", zero_division=0),
            f1_score(tt, tp, average="macro", zero_division=0))


def save_checkpoint(model, tokenizer, risk_enc, type_enc, path):
    os.makedirs(path, exist_ok=True)
    model.bert.config.save_pretrained(path)
    tokenizer.save_pretrained(path)
    state = {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}
    save_file(state, os.path.join(path, "model.safetensors"))
    with open(os.path.join(path, "label_encoders.pkl"), "wb") as f:
        pickle.dump({"risk_encoder": risk_enc, "type_encoder": type_enc}, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "..", "adharaai", "Data", "adharaai_deployment_ready_v3.csv"))
    ap.add_argument("--base-model", default="law-ai/InLegalBERT")
    ap.add_argument("--tag", default="v1", help="model version, also the HF Hub tag")
    ap.add_argument("--out", default=None)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr-encoder", type=float, default=2e-5)
    ap.add_argument("--lr-heads", type=float, default=1e-3)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--risk-weight", type=float, default=0.7)
    ap.add_argument("--type-weight", type=float, default=1.0)
    ap.add_argument("--skip-cv", action="store_true", help="only train the final model")
    cfg = ap.parse_args()

    out = cfg.out or f"/content/drive/MyDrive/adharaai_models/{cfg.tag}"
    ckpt_dir, onnx_dir = os.path.join(out, "checkpoint"), os.path.join(out, "onnx")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  ->  {out}")

    # 1. data gate
    subprocess.run([sys.executable, os.path.join(HERE, "validate_data.py"), cfg.csv], check=True)
    df = pd.read_csv(cfg.csv)
    risk_enc = LabelEncoder().fit(df["risk_level"])
    type_enc = LabelEncoder().fit(df["clause_type"])
    df["risk_label"] = risk_enc.transform(df["risk_level"])
    df["type_label"] = type_enc.transform(df["clause_type"])
    n_risk, n_type = len(risk_enc.classes_), len(type_enc.classes_)
    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model)

    import mlflow
    os.makedirs(out, exist_ok=True)
    mlflow.set_tracking_uri("sqlite:///" + os.path.join(out, "mlflow.db"))
    mlflow.set_experiment("adharaai-inlegalbert")
    with mlflow.start_run(run_name=cfg.tag):
        mlflow.log_params({k: v for k, v in vars(cfg).items() if k not in ("out",)})
        mlflow.log_params({"rows": len(df), "n_risk": n_risk, "n_type": n_type,
                           "csv_file": os.path.basename(cfg.csv)})

        # 2. cross-validation
        metrics = {"tag": cfg.tag, "rows": len(df), "csv": os.path.basename(cfg.csv)}
        if not cfg.skip_cv:
            groups = build_groups(df)
            risk_f1s, type_f1s = [], []
            step = 0
            for seed in cfg.seeds:
                sgkf = StratifiedGroupKFold(n_splits=cfg.folds, shuffle=True, random_state=seed)
                for fold, (tr, va) in enumerate(sgkf.split(df, df["type_label"], groups=groups)):
                    print(f"\n-- seed {seed} fold {fold + 1}/{cfg.folds} --")
                    tr_df, va_df = df.iloc[tr].reset_index(drop=True), df.iloc[va].reset_index(drop=True)
                    m = train(cfg, tokenizer, tr_df, n_risk, n_type, seed, device)
                    r, t = evaluate(m, tokenizer, va_df, device, cfg.batch_size)
                    print(f"  risk_f1={r:.3f}  type_f1={t:.3f}")
                    mlflow.log_metrics({"fold_risk_f1": r, "fold_type_f1": t}, step=step)
                    risk_f1s.append(r); type_f1s.append(t); step += 1
                    del m
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
            metrics.update({
                "cv_risk_f1_mean": round(float(np.mean(risk_f1s)), 4),
                "cv_risk_f1_std": round(float(np.std(risk_f1s)), 4),
                "cv_type_f1_mean": round(float(np.mean(type_f1s)), 4),
                "cv_type_f1_std": round(float(np.std(type_f1s)), 4),
            })
            mlflow.log_metrics({k: v for k, v in metrics.items() if k.startswith("cv_")})
            metrics["decision"] = "hybrid" if metrics["cv_type_f1_mean"] >= HYBRID_MIN_TYPE_F1 else "shadow"
            print(f"\nCV: risk_f1 {metrics['cv_risk_f1_mean']} ± {metrics['cv_risk_f1_std']} | "
                  f"type_f1 {metrics['cv_type_f1_mean']} ± {metrics['cv_type_f1_std']} -> {metrics['decision']}")

        # 3. final model on all rows
        print("\n-- final model on all rows --")
        t0 = time.time()
        final = train(cfg, tokenizer, df, n_risk, n_type, cfg.seeds[0], device)
        final = final.cpu()
        save_checkpoint(final, tokenizer, risk_enc, type_enc, ckpt_dir)
        print(f"Checkpoint saved to {ckpt_dir} ({time.time() - t0:.0f}s)")

        # 4. ONNX export + parity check (exits non-zero if parity < 98%)
        subprocess.run([sys.executable, os.path.join(HERE, "export_onnx.py"),
                        "--checkpoint", ckpt_dir, "--out", onnx_dir, "--check-csv", cfg.csv], check=True)
        with open(os.path.join(onnx_dir, "export_report.json")) as f:
            report = json.load(f)
        metrics["onnx"] = report
        mlflow.log_metrics({"onnx_risk_agreement": report["risk_agreement"],
                            "onnx_type_agreement": report["type_agreement"],
                            "onnx_size_mb": report["onnx_size_mb"]})

        # 5. metrics.json travels with the model (model card numbers)
        with open(os.path.join(onnx_dir, "metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)
        mlflow.log_artifact(os.path.join(onnx_dir, "metrics.json"))
        print("\nDONE\n" + json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
