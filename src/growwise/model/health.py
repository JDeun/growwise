from __future__ import annotations

import socket
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlparse

from growwise.config import Settings


@dataclass(frozen=True, slots=True)
class ModelRuntimeHealth:
    configured: bool
    reachable: bool
    provider: str


def _loopback_host(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().strip("[]").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _tcp_reachable(url: str, *, timeout_seconds: float) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def probe_model_runtime(settings: Settings, *, timeout_seconds: float = 0.15) -> ModelRuntimeHealth:
    """Cheap TCP probe for the configured optional text-model endpoint."""
    if not settings.llm_features_enabled:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.model_provider,
        )

    provider = settings.model_provider.casefold().replace("-", "_")
    if provider not in {"ollama", "openai_compatible"}:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.model_provider,
        )

    parsed = urlparse(settings.model_base_url)
    if (
        provider == "openai_compatible"
        and not _loopback_host(parsed.hostname)
        and not settings.model_remote_allowed
    ):
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.model_provider,
        )

    return ModelRuntimeHealth(
        configured=True,
        reachable=_tcp_reachable(settings.model_base_url, timeout_seconds=timeout_seconds),
        provider=settings.model_provider,
    )


def probe_embedding_runtime(
    settings: Settings,
    *,
    timeout_seconds: float = 0.15,
) -> ModelRuntimeHealth:
    """Probe the independently configured embedding endpoint."""
    if not settings.embedding_features_enabled:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.embedding_provider,
        )
    provider = settings.embedding_provider.casefold().replace("-", "_")
    if provider != "ollama":
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.embedding_provider,
        )
    return ModelRuntimeHealth(
        configured=True,
        reachable=_tcp_reachable(settings.embedding_base_url, timeout_seconds=timeout_seconds),
        provider=settings.embedding_provider,
    )
