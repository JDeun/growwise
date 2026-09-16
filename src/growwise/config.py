from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWWISE_", extra="ignore")

    data_dir: Path = Path.home() / ".growwise"
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    # When set, every Core HTTP endpoint requires `Authorization: Bearer <token>`.
    # The packaged Tauri shell generates a fresh per-process token and passes it to
    # the sidecar through the environment. Keeping the default `None` preserves the
    # explicit standalone/development Core workflow.
    api_token: str | None = None

    model_provider: str = "ollama"
    model_id: str = "qwen3.5:9b"
    model_base_url: str = "http://127.0.0.1:11434"
    model_temperature: float = 0.1
    llm_features_enabled: bool = True

    embedding_model_id: str = "nomic-embed-text"
    embedding_features_enabled: bool = True

    # Public curriculum enrichment is disabled unless an endpoint is explicitly configured.
    # Child identity/profile data must never be sent to this endpoint.
    curriculum_endpoint: str | None = None
    curriculum_cache_ttl_seconds: int = 604_800

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
