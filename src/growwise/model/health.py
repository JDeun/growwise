from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from growwise.config import Settings


@dataclass(frozen=True, slots=True)
class ModelRuntimeHealth:
    configured: bool
    reachable: bool
    provider: str
    model_id: str | None = None
    model_available: bool | None = None


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


def _model_name_matches(configured: str, candidate: str) -> bool:
    configured_name = configured.strip()
    candidate_name = candidate.strip()
    if not configured_name or not candidate_name:
        return False
    if configured_name == candidate_name:
        return True
    if ":" not in configured_name and candidate_name == f"{configured_name}:latest":
        return True
    if ":" not in candidate_name and configured_name == f"{candidate_name}:latest":
        return True
    return False


def _ollama_model_available(
    base_url: str,
    model_id: str,
    *,
    timeout_seconds: float,
) -> bool:
    """Return whether the configured model is actually present in the local Ollama catalog.

    A TCP-open Ollama port is not enough to call AI "ready": requesting a missing model will fail
    later. Keep this probe cheap and read-only by using Ollama's local /api/tags endpoint.
    """

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not _loopback_host(parsed.hostname):
        return False

    endpoint = f"{base_url.rstrip('/')}/api/tags"
    request = Request(endpoint, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - loopback only
            payload = json.load(response)
    except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        return False

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return False

    for item in models:
        if not isinstance(item, dict):
            continue
        for key in ("name", "model"):
            candidate = item.get(key)
            if isinstance(candidate, str) and _model_name_matches(model_id, candidate):
                return True
    return False


def probe_model_runtime(settings: Settings, *, timeout_seconds: float = 0.15) -> ModelRuntimeHealth:
    """Probe the configured optional text-model endpoint and, for Ollama, the model itself."""
    if not settings.llm_features_enabled:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.model_provider,
            model_id=settings.model_id,
        )

    provider = settings.model_provider.casefold().replace("-", "_")
    if provider not in {"ollama", "openai_compatible"}:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.model_provider,
            model_id=settings.model_id,
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
            model_id=settings.model_id,
        )

    reachable = _tcp_reachable(settings.model_base_url, timeout_seconds=timeout_seconds)
    model_available = (
        _ollama_model_available(
            settings.model_base_url,
            settings.model_id,
            timeout_seconds=max(timeout_seconds, 0.25),
        )
        if provider == "ollama" and reachable
        else None
    )
    return ModelRuntimeHealth(
        configured=True,
        reachable=reachable,
        provider=settings.model_provider,
        model_id=settings.model_id,
        model_available=model_available,
    )


def probe_embedding_runtime(
    settings: Settings,
    *,
    timeout_seconds: float = 0.15,
) -> ModelRuntimeHealth:
    """Probe the independently configured embedding endpoint and Ollama model availability."""
    if not settings.embedding_features_enabled:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.embedding_provider,
            model_id=settings.embedding_model_id,
        )
    provider = settings.embedding_provider.casefold().replace("-", "_")
    if provider != "ollama":
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.embedding_provider,
            model_id=settings.embedding_model_id,
        )
    reachable = _tcp_reachable(settings.embedding_base_url, timeout_seconds=timeout_seconds)
    return ModelRuntimeHealth(
        configured=True,
        reachable=reachable,
        provider=settings.embedding_provider,
        model_id=settings.embedding_model_id,
        model_available=(
            _ollama_model_available(
                settings.embedding_base_url,
                settings.embedding_model_id,
                timeout_seconds=max(timeout_seconds, 0.25),
            )
            if reachable
            else None
        ),
    )


def probe_vision_runtime(
    settings: Settings,
    *,
    timeout_seconds: float = 0.15,
) -> ModelRuntimeHealth:
    """Probe the local vision endpoint independently from text generation."""
    if not settings.vision_features_enabled:
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.vision_provider,
            model_id=settings.vision_model_id,
        )
    provider = settings.vision_provider.casefold().replace("-", "_")
    if provider != "ollama":
        return ModelRuntimeHealth(
            configured=False,
            reachable=False,
            provider=settings.vision_provider,
            model_id=settings.vision_model_id,
        )
    reachable = _tcp_reachable(settings.vision_base_url, timeout_seconds=timeout_seconds)
    return ModelRuntimeHealth(
        configured=True,
        reachable=reachable,
        provider=settings.vision_provider,
        model_id=settings.vision_model_id,
        model_available=(
            _ollama_model_available(
                settings.vision_base_url,
                settings.vision_model_id,
                timeout_seconds=max(timeout_seconds, 0.25),
            )
            if reachable
            else None
        ),
    )
