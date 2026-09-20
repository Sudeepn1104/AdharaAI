"""
Run this from your project root (Desktop\\AdharaAI\\adharaai) with venv active:
    python pooling_diagnostic.py

Tests 3 pooling strategies against real labeled clauses from your training CSV
and reports accuracy for each, so we can identify which one the model
was actually trained with -- no more guessing.
"""
import os
import pickle
import torch
import torch.nn as nn
import pandas as pd
from transformers import AutoTokenizer, AutoModel, AutoConfig
from safetensors.torch import load_file

MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "backend", "models", "inlegalbert")
)
CSV_PATH = r"C:\Users\Sudeep Nayak\Downloads\combined_training_data.csv"
N_SAMPLES = 15  # per risk class, for a decent read on accuracy

with open(os.path.join(MODEL_PATH, "label_encoders.pkl"), "rb") as f:
    encoders = pickle.load(f)
    risk_encoder = encoders["risk_encoder"]
    type_encoder = encoders["type_encoder"]

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
config = AutoConfig.from_pretrained(MODEL_PATH)
bert = AutoModel.from_pretrained(MODEL_PATH)

state_dict = load_file(os.path.join(MODEL_PATH, "model.safetensors"))

hidden = config.hidden_size
risk_head = nn.Linear(hidden, len(risk_encoder.classes_))
type_head = nn.Linear(hidden, len(type_encoder.classes_))

# Build a combined module so load_state_dict keys line up (bert.*, risk_head.*, type_head.*)
class Combined(nn.Module):
    def __init__(self):
        super().__init__()
        self.bert = bert
        self.risk_head = risk_head
        self.type_head = type_head

model = Combined()
missing, unexpected = model.load_state_dict(state_dict, strict=False)
model.eval()

df = pd.read_csv(CSV_PATH)
parts = []
for label in df["risk_level"].unique():
    subset = df[df["risk_level"] == label]
    parts.append(subset.sample(min(N_SAMPLES, len(subset)), random_state=1))
sample = pd.concat(parts, ignore_index=True)

strategies = ["cls", "pooler", "mean"]
results = {s: {"correct": 0, "total": 0} for s in strategies}

with torch.no_grad():
    for _, row in sample.iterrows():
        text = str(row["clause_text"])
        true_label = row["risk_level"]

        inputs = tokenizer(
            text, return_tensors="pt", max_length=256,
            truncation=True, padding="max_length"
        )
        outputs = model.bert(
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"]
        )

        pooled_variants = {
            "cls": outputs.last_hidden_state[:, 0, :],
            "pooler": outputs.pooler_output,
            "mean": (outputs.last_hidden_state * inputs["attention_mask"].unsqueeze(-1)).sum(1)
                    / inputs["attention_mask"].sum(1, keepdim=True),
        }

        for strat, pooled in pooled_variants.items():
            logits = model.risk_head(pooled)
            pred_idx = logits.argmax(dim=1).item()
            pred_label = risk_encoder.classes_[pred_idx]
            results[strat]["total"] += 1
            if pred_label == true_label:
                results[strat]["correct"] += 1

print(f"\nTested on {len(sample)} real labeled clauses\n")
print(f"{'Strategy':<10} {'Accuracy':<12} {'Correct/Total'}")
print("-" * 40)
for strat in strategies:
    c, t = results[strat]["correct"], results[strat]["total"]
    acc = (c / t * 100) if t else 0
    print(f"{strat:<10} {acc:>6.1f}%      {c}/{t}")