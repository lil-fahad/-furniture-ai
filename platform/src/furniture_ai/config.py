from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FURNITURE_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/furniture.db"
    public_origin: str = "http://localhost:8000"
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    session_hours: int = Field(12, ge=1, le=72)
    storage_backend: Literal["local", "s3"] = "local"
    data_dir: Path = Path("data/objects")
    s3_bucket: str = ""
    s3_region: str = "eu-central-1"
    s3_endpoint: str | None = None
    s3_kms_key: str | None = None
    max_upload_bytes: int = Field(12 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    max_pixels: int = Field(24_000_000, ge=10_000, le=50_000_000)
    vision_url: str = "http://localhost:8001/v1"
    vision_model: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    vision_revision: str = "unconfigured"
    vision_api_key: SecretStr = SecretStr("")
    provider_timeout: int = Field(90, ge=5, le=300)
    ranking_mode: Literal["learned", "weighted"] = "weighted"
    perception_url: str = "http://localhost:8002"
    generation_url: str = "http://localhost:8003"
    scoring_url: str = "http://localhost:8004"
    model_api_key: SecretStr = SecretStr("")
    generation_timeout: int = Field(300, ge=30, le=900)
    layout_mode: Literal["transformer", "constraints"] = "constraints"
    lease_seconds: int = Field(180, ge=30, le=900)
    max_attempts: int = Field(3, ge=1, le=5)
    max_pending_per_tenant: int = Field(12, ge=1, le=1000)
    jobs_per_hour: int = Field(60, ge=1, le=10000)
    requests_per_minute: int = Field(240, ge=10, le=10000)
    retention_days: int = Field(30, ge=1, le=3650)
    metrics_token: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_deployment(self):
        origin = urlsplit(self.public_origin)
        if origin.scheme not in {"http", "https"} or not origin.netloc or origin.path not in {"", "/"}:
            raise ValueError("PUBLIC_ORIGIN must be an HTTP(S) origin, without a path")
        self.public_origin = self.public_origin.rstrip("/")
        if self.environment == "production":
            if not self.database_url.startswith("postgresql+psycopg://"):
                raise ValueError("Production requires PostgreSQL with the psycopg driver")
            if origin.scheme != "https" or "*" in self.allowed_hosts:
                raise ValueError("Production requires HTTPS and explicit ALLOWED_HOSTS")
            if self.storage_backend != "s3" or not self.s3_bucket:
                raise ValueError("Production requires a private S3 bucket")
            if len(self.metrics_token.get_secret_value()) < 32:
                raise ValueError("Production requires a 32+ character METRICS_TOKEN")
            if self.vision_revision == "unconfigured" or len(self.vision_api_key.get_secret_value()) < 32:
                raise ValueError("Configure a pinned VISION_REVISION and private VISION_API_KEY")
            if len(self.model_api_key.get_secret_value()) < 32:
                raise ValueError("Configure a private MODEL_API_KEY")
        for url in [self.vision_url, self.perception_url, self.generation_url, self.scoring_url]:
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                raise ValueError("Provider URLs must be configured HTTP(S) endpoints")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
