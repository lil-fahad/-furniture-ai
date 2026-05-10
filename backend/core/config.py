from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Furniture AI System"
    yolo_model_path: Path = Path("models/yolo/best.pt")
    recommender_model_path: Path = Path("models/recommender/model.pt")
    layout_model_path: Path = Path("models/layout3d/model.pt")
    checkpoints_dir: Path = Path("models/checkpoints")

    # Alibaba Cloud / DashScope API
    alibaba_api_key: Optional[str] = None
    dashscope_api_key: Optional[str] = None

    # Qwen model to use (default: qwen-plus for balance of speed/quality)
    qwen_model: str = "qwen-plus"

    class Config:
        env_prefix = "FURNITURE_"
        env_file = ".env"
        # Allow extra fields so ALIBABA_API_KEY / DASHSCOPE_API_KEY (no prefix) load too
        extra = "allow"

    @property
    def effective_api_key(self) -> Optional[str]:
        """Return the first available Alibaba/DashScope API key."""
        return self.alibaba_api_key or self.dashscope_api_key


@lru_cache()
def get_settings() -> Settings:
    settings = Settings(
        _env_file=".env",
        _env_file_encoding="utf-8",
    )
    settings.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    settings.yolo_model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.recommender_model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.layout_model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
