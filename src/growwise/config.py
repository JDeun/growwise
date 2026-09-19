from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GROWWISE_", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        # GrowWise stores child records, photos and conversations under one app-data root. On POSIX
        # systems the root itself is the confidentiality boundary: even if a third-party library
        # creates a database with a permissive process umask, other local users cannot traverse the
        # directory. Windows relies on the user's app-data ACL instead.
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            os.chmod(self.data_dir, 0o700)

    data_dir: Path = Path.home() / ".growwise"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    model_provider: str = "ollama"
    model_id: str = "qwen3.5:9b"
    model_base_url: str = "http://127.0.0.1:11434"
    model_api_key: SecretStr | None = None
    # Child learning context may be sent to the configured text endpoint. Non-loopback endpoints
    # therefore require an explicit privacy opt-in rather than becoming remote by accident.
    model_remote_allowed: bool = False
    model_max_output_tokens: int = Field(default=4096, ge=64, le=65_536)
    model_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    model_timeout_seconds: float = Field(default=12.0, gt=0.0, le=120.0)
    model_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    model_circuit_recovery_seconds: float = Field(default=30.0, ge=1.0, le=600.0)
    llm_features_enabled: bool = True

    # Non-interactive text-model work is durable and backgrounded. The user-visible Core record is
    # written first; this queue only enriches it later, so model failure cannot block persistence.
    background_ai_job_lease_seconds: int = Field(default=900, ge=60, le=86_400)
    background_ai_job_max_attempts: int = Field(default=3, ge=1, le=10)
    background_ai_job_poll_interval_seconds: float = Field(default=0.5, ge=0.1, le=30.0)

    # Child photos are more sensitive than ordinary public enrichment. Vision therefore has a
    # dedicated local endpoint rather than inheriting a potentially remote text-provider URL.
    # Photo analysis is deliberately long-running and background-friendly: consumer hardware may
    # need minutes rather than seconds for one multimodal inference.
    vision_provider: str = "ollama"
    # Text and vision remain separate roles so privacy/timeouts/providers can diverge, but the
    # default local setup intentionally shares one multimodal Qwen model to avoid duplicate model
    # downloads and model switching on consumer hardware.
    vision_model_id: str = "qwen3.5:9b"
    vision_base_url: str = "http://127.0.0.1:11434"
    vision_features_enabled: bool = True
    vision_timeout_seconds: float = Field(default=300.0, gt=0.0, le=1800.0)
    photo_text_timeout_seconds: float = Field(default=300.0, gt=0.0, le=1800.0)
    photo_remote_text_allowed: bool = False
    photo_remote_vision_allowed: bool = False
    photo_job_lease_seconds: int = Field(default=7200, ge=60, le=86_400)
    photo_job_max_attempts: int = Field(default=3, ge=1, le=10)
    photo_job_poll_interval_seconds: float = Field(default=1.0, ge=0.1, le=30.0)

    # Embeddings remain independently configurable so switching the text provider to an
    # OpenAI-compatible endpoint cannot silently redirect local RAG embedding traffic.
    embedding_provider: str = "ollama"
    embedding_model_id: str = "nomic-embed-text"
    embedding_base_url: str = "http://127.0.0.1:11434"
    embedding_timeout_seconds: float = Field(default=8.0, gt=0.0, le=120.0)
    embedding_features_enabled: bool = True

    photo_max_file_bytes: int = Field(default=15 * 1024 * 1024, ge=1024, le=50 * 1024 * 1024)
    photo_max_images_per_record: int = Field(default=8, ge=1, le=12)
    photo_max_total_bytes: int = Field(default=60 * 1024 * 1024, ge=1024, le=200 * 1024 * 1024)
    # Compressed byte limits alone do not bound decoder memory. 16K per axis and 64 MP admit
    # high-resolution phone photos while rejecting tiny compressed files that expand to gigapixels.
    photo_max_width: int = Field(default=16_384, ge=1, le=100_000)
    photo_max_height: int = Field(default=16_384, ge=1, le=100_000)
    photo_max_pixels: int = Field(default=64_000_000, ge=1_000_000, le=250_000_000)

    # Public education-resource discovery. These adapters receive public query dimensions only;
    # child IDs, names, observations, and notes must never be included in outbound requests.
    data4library_api_key: str | None = None
    data4library_endpoint: str = "https://data4library.kr/api/srchBooks"
    data4library_cache_ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)

    # Public, privacy-safe enrichment sources. They receive only allow-listed generic topics.
    public_enrichment_enabled: bool = True
    google_books_endpoint: str = "https://www.googleapis.com/books/v1/volumes"
    google_books_api_key: str | None = None
    national_library_api_key: str | None = None
    national_library_isbn_endpoint: str = "https://www.nl.go.kr/seoji/SearchApi.do"
    krdict_api_key: str | None = None
    krdict_endpoint: str = "https://krdict.korean.go.kr/api/search"
    data_go_kr_service_key: str | None = None
    kma_weather_endpoint: str = (
        "https://apis.data.go.kr/1360000/"
        "VilageFcstInfoService_2.0/getUltraSrtNcst"
    )
    museum_standard_endpoint: str = (
        "https://api.data.go.kr/openapi/tn_pubr_public_museum_artgr_info_api"
    )
    heritage_palace_endpoint: str = (
        "https://www.heritage.go.kr/heri/gungDetail/gogungListOpenApi.do"
    )
    nasa_images_endpoint: str = "https://images-api.nasa.gov/search"
    wikidata_endpoint: str = "https://www.wikidata.org/w/api.php"
    wikipedia_endpoint: str = "https://ko.wikipedia.org/w/rest.php/v1/search/page"
    wikimedia_commons_endpoint: str = "https://commons.wikimedia.org/w/api.php"
    gbif_species_endpoint: str = "https://api.gbif.org/v1/species/search"
    public_enrichment_cache_ttl_seconds: int = Field(default=604_800, ge=60, le=2_592_000)
    discovery_source_result_limit: int = Field(default=6, ge=1, le=20)

    overpass_endpoint: str = "https://overpass-api.de/api/interpreter"
    overpass_cache_ttl_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    discovery_place_radius_m: int = Field(default=2_000, ge=100, le=20_000)

    # Public curriculum enrichment is disabled unless an endpoint is explicitly configured.
    # A bundled official-source metadata catalog remains available without network access.
    curriculum_endpoint: str | None = None
    curriculum_cache_ttl_seconds: int = Field(default=604_800, ge=60, le=2_592_000)

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
