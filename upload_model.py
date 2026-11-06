import os
from huggingface_hub import HfApi

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise RuntimeError(
        "HF_TOKEN environment variable not set. "
        "Set it with: $env:HF_TOKEN = 'your_token_here' (PowerShell, current session only)"
    )

api = HfApi(token=HF_TOKEN)

MODEL_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "adharaai", "backend", "models", "inlegalbert")
)

api.upload_folder(
    folder_path=MODEL_PATH,
    repo_id="Sudeepn1104/adharaai-inlegalbert",
    repo_type="model"
)
print("Upload complete")