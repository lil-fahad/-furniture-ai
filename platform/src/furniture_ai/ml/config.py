import json
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FURNITURE_ML_", extra="ignore")
    role: Literal["perception", "generation", "scoring", "evaluator", "all"] = "perception"
    device: str = "cuda"
    api_key: SecretStr = SecretStr("")
    models_dir: Path = Path("data/models")
    lock_path: Path = Path("models.lock.json")
    layout_checkpoint: Path | None = None
    rank_checkpoint: Path | None = None
    floorplan_checkpoint: Path | None = None
    floorplan_backend: Literal["vlm", "trained", "cubicasa_research"] = "vlm"
    cubicasa_checkpoint: Path | None = None
    cubicasa_sha256: str = ""
    cubicasa_code_dir: Path | None = None
    research_only: bool = False
    cpu_offload: bool = True
    sdxl_lora: bool = False
    max_detections: int = Field(24, ge=1, le=64)

    def model_path(self, alias):
        lock = json.loads(self.lock_path.read_text())
        record = lock["models"][alias]
        path = self.models_dir / record.get("local_subdir", alias)
        if not path.resolve().is_relative_to(self.models_dir.resolve()):
            raise ValueError("Invalid model directory in lock file")
        installed = json.loads((path / "installed.json").read_text())
        if any(installed[k] != record[k] for k in ("repo_id", "revision")):
            raise ValueError(f"Model revision mismatch for {alias}")
        return str(path), record["revision"]
