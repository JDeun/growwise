from __future__ import annotations

from pathlib import Path

import pytest

from growwise.api import photo_routes
from growwise.config import Settings
from growwise.model.privacy import is_loopback_endpoint


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:11434",
        "http://127.1.2.3:11434",
        "http://localhost:11434",
        "http://[::1]:11434",
        "https://localhost:11434",
    ],
)
def test_photo_model_loopback_detection(url: str) -> None:
    assert is_loopback_endpoint(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://10.0.0.5:11434",
        "https://models.example.com",
        "not-a-url",
    ],
)
def test_photo_model_remote_detection(url: str) -> None:
    assert is_loopback_endpoint(url) is False


def test_remote_photo_model_endpoints_are_blocked_without_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=True,
        vision_features_enabled=True,
        model_provider="ollama",
        model_base_url="http://10.0.0.5:11434",
        vision_provider="ollama",
        vision_base_url="http://10.0.0.6:11434",
        photo_remote_text_allowed=False,
        photo_remote_vision_allowed=False,
    )
    calls: list[str] = []

    monkeypatch.setattr(photo_routes, "get_photo_settings", lambda: settings)
    monkeypatch.setattr(
        photo_routes,
        "create_model_provider",
        lambda *_args, **_kwargs: calls.append("text") or object(),
    )
    monkeypatch.setattr(
        photo_routes,
        "OllamaVisionProvider",
        lambda **_kwargs: calls.append("vision") or object(),
    )
    photo_routes.get_photo_text_provider.cache_clear()
    photo_routes.get_photo_vision_provider.cache_clear()

    assert photo_routes.get_photo_text_provider() is None
    assert photo_routes.get_photo_vision_provider() is None
    assert calls == []

    photo_routes.get_photo_text_provider.cache_clear()
    photo_routes.get_photo_vision_provider.cache_clear()


def test_remote_photo_model_endpoints_require_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=True,
        vision_features_enabled=True,
        model_provider="ollama",
        model_base_url="http://10.0.0.5:11434",
        vision_provider="ollama",
        vision_base_url="http://10.0.0.6:11434",
        photo_remote_text_allowed=True,
        photo_remote_vision_allowed=True,
    )
    calls: list[str] = []

    monkeypatch.setattr(photo_routes, "get_photo_settings", lambda: settings)
    monkeypatch.setattr(
        photo_routes,
        "create_model_provider",
        lambda *_args, **_kwargs: calls.append("text") or object(),
    )
    monkeypatch.setattr(
        photo_routes,
        "OllamaVisionProvider",
        lambda **_kwargs: calls.append("vision") or object(),
    )
    photo_routes.get_photo_text_provider.cache_clear()
    photo_routes.get_photo_vision_provider.cache_clear()

    assert photo_routes.get_photo_text_provider() is not None
    assert photo_routes.get_photo_vision_provider() is not None
    assert calls == ["text", "vision"]

    photo_routes.get_photo_text_provider.cache_clear()
    photo_routes.get_photo_vision_provider.cache_clear()
