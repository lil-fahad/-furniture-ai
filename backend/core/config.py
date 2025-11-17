from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Furniture AI System"
    yolo_model_path: Path = Path("models/yolo/best.pt")
    recommender_model_path: Path = Path("models/recommender/model.pt")
    layout_model_path: Path = Path("models/layout3d/model.pt")
    checkpoints_dir: Path = Path("models/checkpoints")

    class Config:
        env_prefix = "FURNITURE_"
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    settings.yolo_model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.recommender_model_path.parent.mkdir(parents=True, exist_ok=True)
    settings.layout_model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
