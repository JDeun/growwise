from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWWISE_", extra="ignore")

    data_dir: Path = Path.home() / ".growwise"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    model_provider: str = "ollama"
    model_id: str = "qwen3.5:9b"
    model_base_url: str = "http://127.0.0.1:11434"
    model_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    model_timeout_seconds: float = Field(default=12.0, gt=0.0, le=120.0)
    model_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    model_circuit_recovery_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    llm_features_enabled: bool = True

    # Child photos are more sensitive than ordinary public enrichment. Vision therefore has a
    # dedicated local endpoint rather than inheriting a potentially remote text-provider URL.
    vision_provider: str = "ollama"
    vision_model_id: str = "gemma3:4b"
    vision_base_url: str = "http://127.0.0.1:11434"
    vision_features_enabled: bool = True
    vision_timeout_seconds: float = Field(default=20.0, gt=0.0, le=180.0)
    photo_remote_text_allowed: bool = False

    embedding_model_id: str = "nomic-embed-text"
    embedding_timeout_seconds: float = Field(default=8.0, gt=0.0, le=120.0)
    embedding_features_enabled: bool = True

    photo_max_file_bytes: int = Field(default=15 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    photo_max_images_per_record: int = Field(default=8, ge=1, le=12)
    photo_max_total_bytes: int = Field(default=60 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)

    # Public curriculum enrichment is disabled unless an endpoint is explicitly configured.
    # Child identity/profile data must never be sent to this endpoint.
    curriculum_endpoint: str | None = None
    curriculum_cache_ttl_seconds: int = 604_800

    @property
    def records_dir(self) -> Path:
        return self.data_dir / "records"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def photo_assets_dir(self) -> Path:
        return self.assets_dir / "photos"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.sqlite3"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "langgraph-checkpoints.sqlite3"

    @property
    def jobs_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def rag_index_path(self) -> Path:
        return self.data_dir / "rag.sqlite3"

    @property
    def conversations_path(self) -> Path:
        return self.data_dir / "conversations.sqlite3"

    @property
    def idempotency_path(self) -> Path:
        return self.data_dir / "idempotency.sqlite3"

    @property
    def external_cache_path(self) -> Path:
        return self.data_dir / "external-cache.sqlite3"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"
