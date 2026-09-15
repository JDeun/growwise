from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWWISE_", extra="ignore")

    data_dir: Path = Path.home() / ".growwise"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    model_provider: str = "ollama"
    model_id: str = "qwen3.5:9b"
    model_base_url: str = "http://127.0.0.1:11434"
    model_temperature: float = 0.1
    llm_features_enabled: bool = True

    embedding_model_id: str = "nomic-embed-text"
    embedding_features_enabled: bool = True

    external_enrichment_enabled: bool = False
    data4library_auth_key: SecretStr | None = None
    external_cache_ttl_seconds: int = Field(default=86_400, ge=60, le=604_800)

    @property
    def records_dir(self) -> Path:
        return self.data_dir / "records"

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
