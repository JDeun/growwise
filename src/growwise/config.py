from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWWISE_", extra="ignore")

    data_dir: Path = Path.home() / ".growwise"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    @property
    def records_dir(self) -> Path:
        return self.data_dir / "records"

    @property
    def index_path(self) -> Path:
        return self.data_dir / "index.sqlite3"
