from __future__ import annotations

from growwise.config import Settings

from .ollama import OllamaProvider
from .openai_compatible import OpenAICompatibleProvider
from .provider import ModelProvider


def create_model_provider(
    settings: Settings,
    *,
    allow_remote: bool | None = None,
    background: bool = False,
) -> ModelProvider:
    provider = settings.model_provider.casefold().replace("-", "_")
    remote_allowed = settings.model_remote_allowed if allow_remote is None else allow_remote
    timeout = (
        settings.background_ai_model_timeout_seconds
        if background
        else settings.model_timeout_seconds
    )
    output_tokens = (
        settings.background_ai_max_output_tokens if background else settings.model_max_output_tokens
    )
    if provider == "ollama":
        return OllamaProvider(
            model=settings.model_id,
            base_url=settings.model_base_url,
            allow_remote=remote_allowed,
            temperature=settings.model_temperature,
            timeout_seconds=timeout,
            max_output_tokens=output_tokens,
            reasoning=settings.background_ai_reasoning_enabled if background else False,
            context_tokens=settings.background_ai_model_context_tokens if background else None,
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
            timeout_seconds=timeout,
            max_output_tokens=output_tokens,
            failure_threshold=settings.model_circuit_failure_threshold,
            recovery_seconds=settings.model_circuit_recovery_seconds,
        )
    raise ValueError(f"Unsupported model provider: {settings.model_provider}")
