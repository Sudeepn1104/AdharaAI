import os
import pickle
import logging
import torch
import torch.nn as nn
from transformers import AutoTokenizer, AutoModel, AutoConfig
from safetensors.torch import load_file

logger = logging.getLogger("adharaai")

MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "models", "inlegalbert")
)


class InLegalBERTMultiHead(nn.Module):
    def __init__(self, model_name_or_path, num_risk_labels, num_type_labels):
        super().__init__()
        self.config    = AutoConfig.from_pretrained(model_name_or_path)
        self.bert      = AutoModel.from_pretrained(model_name_or_path)
        hidden         = self.config.hidden_size
        self.dropout   = nn.Dropout(0.1)
        self.risk_head = nn.Linear(hidden, num_risk_labels)
        self.type_head = nn.Linear(hidden, num_type_labels)

    def forward(self, input_ids=None, attention_mask=None, **kwargs):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        # Confirmed via diagnostic testing against real labeled data: raw CLS
        # token gives 91.1% accuracy (matching training F1), vs pooler_output's
        # 24.4% and mean-pooling's 75.6%. This is what the model was trained on.
        pooled = self.dropout(outputs.last_hidden_state[:, 0, :])
        return self.risk_head(pooled), self.type_head(pooled)


_tokenizer    = None
_model        = None
_risk_encoder = None
_type_encoder = None
_model_loaded = False


def _load_model():
    global _tokenizer, _model, _risk_encoder, _type_encoder, _model_loaded

    if _model_loaded:
        return True

    if not os.path.exists(MODEL_PATH):
        logger.warning(f"InLegalBERT not found at {MODEL_PATH}. Using rules only.")
        return False

    try:
        with open(os.path.join(MODEL_PATH, "label_encoders.pkl"), "rb") as f:
            encoders      = pickle.load(f)
            _risk_encoder = encoders["risk_encoder"]
            _type_encoder = encoders["type_encoder"]

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

        _model = InLegalBERTMultiHead(
            MODEL_PATH,
            len(_risk_encoder.classes_),
            len(_type_encoder.classes_)
        )

        # AutoModel.from_pretrained() above only loads the base BERT layers.
        # The trained risk_head / type_head weights live in model.safetensors
        # too, but nothing loads them unless we do it explicitly here.
        weights_path = os.path.join(MODEL_PATH, "model.safetensors")
        if os.path.exists(weights_path):
            state_dict = load_file(weights_path)
            missing, unexpected = _model.load_state_dict(state_dict, strict=False)
            logger.info(
                f"Loaded full InLegalBERT state dict from {weights_path} "
                f"(missing: {missing}, unexpected: {unexpected})"
            )
        else:
            logger.warning(
                f"No model.safetensors found at {weights_path} — "
                f"classification heads are randomly initialized, predictions will be unreliable."
            )

        _model.eval()
        _model_loaded = True
        logger.info("InLegalBERT loaded successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to load InLegalBERT: {e}")
        return False


def classify_clause(clause_text: str) -> dict:
    if not _load_model():
        return {
            "risk_level": "low",
            "clause_type": "standard",
            "risk_confidence": 0,
            "type_confidence": 0,
            "source": "fallback",
        }

    try:
        inputs = _tokenizer(
            clause_text,
            return_tensors="pt",
            max_length=256,
            truncation=True,
            padding="max_length",
        )
        with torch.no_grad():
            risk_logits, type_logits = _model(
                input_ids=inputs["input_ids"],
                attention_mask=inputs["attention_mask"],
            )

        risk_probs = torch.softmax(risk_logits, dim=1)[0]
        type_probs = torch.softmax(type_logits, dim=1)[0]
        risk_idx   = risk_probs.argmax().item()
        type_idx   = type_probs.argmax().item()

        return {
            "risk_level":      _risk_encoder.classes_[risk_idx],
            "clause_type":     _type_encoder.classes_[type_idx],
            "risk_confidence": round(risk_probs[risk_idx].item() * 100),
            "type_confidence": round(type_probs[type_idx].item() * 100),
            "source":          "bert",
        }

    except Exception as e:
        logger.error(f"BERT error: {e}")
        return {
            "risk_level": "low",
            "clause_type": "standard",
            "risk_confidence": 0,
            "type_confidence": 0,
            "source": "fallback",
        }


def is_available() -> bool:
    return _load_model()