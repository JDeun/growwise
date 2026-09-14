from __future__ import annotations

import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from growwise.config import Settings


@dataclass(frozen=True, slots=True)
class ModelRuntimeHealth:
    configured: bool
    reachable: bool
    provider: str


def probe_model_runtime(settings: Settings, *, timeout_seconds: float = 0.15) -> ModelRuntimeHealth:
    """Probe model runtime availability without making Core availability depend on it.

    The probe intentionally checks only whether the configured local provider accepts TCP
    connections. It does not invoke a model or download anything, so `/health` stays cheap and
    deterministic. Unsupported providers are reported as configured but not locally reachable;
    future provider adapters can supply their own probe strategy.
    """
    configured = settings.llm_features_enabled
    if not configured:
        return ModelRuntimeHealth(configured=False, reachable=False, provider=settings.model_provider)

    if settings.model_provider.casefold() != "ollama":
        return ModelRuntimeHealth(configured=True, reachable=False, provider=settings.model_provider)

    parsed = urlparse(settings.model_base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return ModelRuntimeHealth(configured=True, reachable=True, provider=settings.model_provider)
    except OSError:
        return ModelRuntimeHealth(configured=True, reachable=False, provider=settings.model_provider)
