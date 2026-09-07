"""Write a private development configuration without displaying generated secrets."""

import json
import os
import secrets
from pathlib import Path

path = Path(".env")
lock = json.loads(Path("models.lock.json").read_text())
revision = lock["models"]["evaluator"]["revision"]
model_key, vision_key, metrics = [secrets.token_urlsafe(48) for _ in range(3)]
db_password = secrets.token_urlsafe(32)
lines = [
    "FURNITURE_ENVIRONMENT=development",
    f"FURNITURE_DATABASE_URL=postgresql+psycopg://furniture:{db_password}@db:5432/furniture",
    f"FURNITURE_DB_PASSWORD={db_password}",
    "VLLM_IMAGE=vllm/vllm-openai:v0.12.0",
    "FURNITURE_PUBLIC_ORIGIN=http://localhost:8000",
    'FURNITURE_ALLOWED_HOSTS=["localhost","127.0.0.1"]',
    "FURNITURE_DATA_DIR=/data/objects",
    "FURNITURE_VISION_URL=http://evaluator:8000/v1",
    "FURNITURE_VISION_MODEL=Qwen/Qwen2.5-VL-7B-Instruct",
    f"FURNITURE_VISION_REVISION={revision}",
    f"FURNITURE_VISION_API_KEY={vision_key}",
    f"FURNITURE_MODEL_API_KEY={model_key}",
    f"FURNITURE_ML_API_KEY={model_key}",
    f"FURNITURE_METRICS_TOKEN={metrics}",
    "FURNITURE_PERCEPTION_URL=http://perception:8000",
    "FURNITURE_GENERATION_URL=http://generation:8000",
    "FURNITURE_SCORING_URL=http://scoring:8000",
    "FURNITURE_LAYOUT_MODE=constraints",
    "FURNITURE_RANKING_MODE=weighted",
    "FURNITURE_ML_MODELS_DIR=/models",
    "FURNITURE_ML_LOCK_PATH=/app/models.lock.json",
    "FURNITURE_ML_FLOORPLAN_BACKEND=vlm",
    "FURNITURE_ML_CPU_OFFLOAD=true",
]
fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
with os.fdopen(fd, "w") as f:
    f.write("\n".join(lines) + "\n")
print("Created .env with random service credentials. See README for local or Docker setup.")
