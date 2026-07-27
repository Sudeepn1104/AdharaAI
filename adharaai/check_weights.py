from backend.services.classifier import InLegalBERTMultiHead, MODEL_PATH
from safetensors.torch import load_file
import pickle, torch

with open(MODEL_PATH + r'\label_encoders.pkl', 'rb') as f:
    enc = pickle.load(f)

m = InLegalBERTMultiHead(MODEL_PATH, len(enc['risk_encoder'].classes_), len(enc['type_encoder'].classes_))
sd = load_file(MODEL_PATH + r'\model.safetensors')
missing, unexpected = m.load_state_dict(sd, strict=False)
print('MISSING:', missing)
print('UNEXPECTED:', unexpected)
print('Weights match:', torch.equal(m.risk_head.weight, sd['risk_head.weight']))