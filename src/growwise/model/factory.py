from __future__ import annotations

from growwise.config import Settings

from .ollama import OllamaProvider
from .provider import ModelProvider


def create_model_provider(settings: Settings) -> ModelProvider:
    if settings.model_provider == "ollama":
        return OllamaProvider(
            model=settings.model_id,
            base_url=settings.model_base_url,
            temperature=settings.model_temperature,
            timeout_seconds=settings.model_timeout_seconds,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    raise ValueError(f"Unsupported model provider: {settings.model_provider}")
