"""
AdharaAI - InLegalBERT dual-head retraining script (v3)
Changes vs v2:
  1. EPOCHS 8 -> 20
  2. HEAD_WEIGHTS (0.3, 1.0) -> (0.7, 1.0)
  3. Separate LRs: encoder 2e-5, heads 1e-3 (+10% warmup, grad clipping)
  4. StratifiedGroupKFold grouped by source_file (real docs stay in one fold;
     synthetic rows get one group each - see build_groups)
  5. Summary reports mean/std + confusion matrix pooled over ALL runs
     (no best-run cherry-picking)
Run in Colab (GPU). Set CSV_PATH to your v2/v3 CSV.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, classification_report, confusion_matrix
from sklearn.preprocessing import LabelEncoder
from transformers import AutoTokenizer, AutoModel, get_linear_schedule_with_warmup

# ---------------- CONFIG ----------------
CSV_PATH = "AdharaAI/adharaai/Data/adharaai_deployment_ready_v2.csv"
MODEL_NAME = "law-ai/InLegalBERT"
MAX_LEN = 256
BATCH_SIZE = 8
EPOCHS = 20
LR_ENCODER = 2e-5
LR_HEADS = 1e-3
WARMUP_FRAC = 0.1
N_FOLDS = 5
SEEDS = [42, 7, 123]          # use [42] for a quick first test
HEAD_WEIGHTS = (0.7, 1.0)     # (risk, type)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------- DATA ----------------
df = pd.read_csv(CSV_PATH)
print(f"Loaded {len(df)} rows")
print(df["clause_type"].value_counts())
print(df["risk_level"].value_counts())

risk_encoder = LabelEncoder().fit(df["risk_level"])
type_encoder = LabelEncoder().fit(df["clause_type"])
df["risk_label"] = risk_encoder.transform(df["risk_level"])
df["type_label"] = type_encoder.transform(df["clause_type"])
N_RISK = len(risk_encoder.classes_)
N_TYPE = len(type_encoder.classes_)


def build_groups(frame):
    """Real rows: group = source_file. Synthetic rows share one source_file
    (would land in a single fold), so each gets its own group instead.
    Near-duplicate synthetic clauses can still leak across folds."""
    groups = []
    for i, src in enumerate(frame["source_file"].astype(str)):
        groups.append(f"row_{i}" if "synthetic" in src.lower() else src)
    return np.array(groups)


df["group"] = build_groups(df)
print("Groups:", df["group"].nunique())

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


class ClauseDataset(Dataset):
    def __init__(self, texts, risk_labels, type_labels):
        self.texts = list(texts)
        self.risk_labels = list(risk_labels)
        self.type_labels = list(type_labels)

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = tokenizer(self.texts[idx], truncation=True, max_length=MAX_LEN,
                        padding="max_length", return_tensors="pt")
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "risk_label": torch.tensor(self.risk_labels[idx], dtype=torch.long),
            "type_label": torch.tensor(self.type_labels[idx], dtype=torch.long),
        }


# ---------------- MODEL ----------------
class DualHeadClassifier(nn.Module):
    def __init__(self, n_risk, n_type):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(MODEL_NAME)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(0.2)
        self.risk_head = nn.Linear(hidden, n_risk)
        self.type_head = nn.Linear(hidden, n_type)

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.dropout(out.last_hidden_state[:, 0, :])  # CLS pooling
        return self.risk_head(cls), self.type_head(cls)


def class_weights_for(labels, n_classes):
    counts = np.bincount(labels, minlength=n_classes).astype(float)
    counts[counts == 0] = 1.0
    w = 1.0 / counts
    return torch.tensor(w / w.mean(), dtype=torch.float32)


def run_one_fold(train_df, val_df, seed):
    torch.manual_seed(seed)
    np.random.seed(seed)

    train_ds = ClauseDataset(train_df["clause_text"], train_df["risk_label"], train_df["type_label"])
    val_ds = ClauseDataset(val_df["clause_text"], val_df["risk_label"], val_df["type_label"])
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

    model = DualHeadClassifier(N_RISK, N_TYPE).to(DEVICE)
    risk_loss_fn = nn.CrossEntropyLoss(weight=class_weights_for(train_df["risk_label"].values, N_RISK).to(DEVICE))
    type_loss_fn = nn.CrossEntropyLoss(weight=class_weights_for(train_df["type_label"].values, N_TYPE).to(DEVICE))

    optimizer = torch.optim.AdamW([
        {"params": model.encoder.parameters(), "lr": LR_ENCODER},
        {"params": list(model.risk_head.parameters()) + list(model.type_head.parameters()), "lr": LR_HEADS},
    ], weight_decay=0.01)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(WARMUP_FRAC * total_steps), num_training_steps=total_steps)

    lam_risk, lam_type = HEAD_WEIGHTS
    model.train()
    for epoch in range(EPOCHS):
        epoch_loss = 0.0
        for batch in train_loader:
            optimizer.zero_grad()
            risk_logits, type_logits = model(batch["input_ids"].to(DEVICE), batch["attention_mask"].to(DEVICE))
            loss = (lam_risk * risk_loss_fn(risk_logits, batch["risk_label"].to(DEVICE))
                    + lam_type * type_loss_fn(type_logits, batch["type_label"].to(DEVICE)))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            epoch_loss += loss.item()
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"    epoch {epoch+1}/{EPOCHS}  loss={epoch_loss/len(train_loader):.4f}")

    model.eval()
    rp, rt, tp, tt = [], [], [], []
    with torch.no_grad():
        for batch in val_loader:
            risk_logits, type_logits = model(batch["input_ids"].to(DEVICE), batch["attention_mask"].to(DEVICE))
            rp += risk_logits.argmax(1).cpu().tolist(); rt += batch["risk_label"].tolist()
            tp += type_logits.argmax(1).cpu().tolist(); tt += batch["type_label"].tolist()

    del model, optimizer
    torch.cuda.empty_cache()
    return {
        "risk_f1": f1_score(rt, rp, average="macro", zero_division=0),
        "type_f1": f1_score(tt, tp, average="macro", zero_division=0),
        "rt": rt, "rp": rp, "tt": tt, "tp": tp,
    }


# ---------------- MAIN ----------------
all_results = []
for seed in SEEDS:
    print(f"\n{'='*70}\nSEED {seed}\n{'='*70}")
    sgkf = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
    for fold_idx, (tr, va) in enumerate(sgkf.split(df, df["type_label"], groups=df["group"])):
        print(f"\n-- Fold {fold_idx+1}/{N_FOLDS} --")
        res = run_one_fold(df.iloc[tr].reset_index(drop=True), df.iloc[va].reset_index(drop=True), seed)
        res["seed"], res["fold"] = seed, fold_idx + 1
        all_results.append(res)
        print(f"  risk_f1={res['risk_f1']:.3f}  type_f1={res['type_f1']:.3f}")

# ---------------- SUMMARY ----------------
risk_f1s = [r["risk_f1"] for r in all_results]
type_f1s = [r["type_f1"] for r in all_results]
print(f"\n{'='*70}\nFINAL SUMMARY: {len(SEEDS)} SEEDS x {N_FOLDS} FOLDS\n{'='*70}")
print(f"risk_f1: mean={np.mean(risk_f1s):.3f}  std={np.std(risk_f1s):.3f}  min={min(risk_f1s):.3f}  max={max(risk_f1s):.3f}")
print(f"type_f1: mean={np.mean(type_f1s):.3f}  std={np.std(type_f1s):.3f}  min={min(type_f1s):.3f}  max={max(type_f1s):.3f}")
print("Baselines: v2 CV run  risk_f1=0.385  type_f1=0.682 | old single split  risk_f1=0.615  type_f1=0.336")

# Pooled over ALL runs (no best-run cherry-picking)
tt = sum([r["tt"] for r in all_results], []); tp = sum([r["tp"] for r in all_results], [])
rt = sum([r["rt"] for r in all_results], []); rp = sum([r["rp"] for r in all_results], [])
print("\nPooled TYPE report (all runs):")
print(classification_report(tt, tp, target_names=type_encoder.classes_, zero_division=0))
print("Pooled TYPE confusion matrix (rows=true, cols=pred):")
print(type_encoder.classes_)
print(confusion_matrix(tt, tp))
print("\nPooled RISK report (all runs):")
print(classification_report(rt, rp, target_names=risk_encoder.classes_, zero_division=0))
print(risk_encoder.classes_)
print(confusion_matrix(rt, rp))
