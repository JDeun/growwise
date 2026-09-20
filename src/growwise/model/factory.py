from __future__ import annotations

from growwise.config import Settings

from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .provider import ModelProvider


def create_model_provider(
    settings: Settings,
    *,
    allow_remote: bool | None = None,
) -> ModelProvider:
    provider = settings.model_provider.casefold().replace("-", "_")
    remote_allowed = settings.model_remote_allowed if allow_remote is None else allow_remote
    if provider == "ollama":
        return OllamaProvider(
            model=settings.model_id,
            base_url=settings.model_base_url,
            allow_remote=remote_allowed,
            temperature=settings.model_temperature,
            timeout_seconds=settings.model_timeout_seconds,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            model=settings.model_id,
            base_url=settings.model_base_url,
            api_key=(
                settings.model_api_key.get_secret_value()
                if settings.model_api_key is not None
                else None
            ),
            allow_remote=remote_allowed,
            temperature=settings.model_temperature,
            timeout_seconds=settings.model_timeout_seconds,
            max_output_tokens=settings.model_max_output_tokens,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    raise ValueError(f"Unsupported model provider: {settings.model_provider}")
