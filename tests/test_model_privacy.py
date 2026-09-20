from __future__ import annotations

import pytest

from growwise.config import Settings
from growwise.model.factory import create_model_provider
from growwise.model.health import probe_model_runtime
from growwise.model.privacy import is_loopback_endpoint
from growwise.model.vision import OllamaVisionProvider
from growwise.rag import OllamaEmbeddingProvider


def test_loopback_endpoint_accepts_localhost_and_loopback_ips() -> None:
    assert is_loopback_endpoint("http://127.0.0.1:11434")
    assert is_loopback_endpoint("http://[::1]:11434")
    assert is_loopback_endpoint("http://localhost:11434")
    assert not is_loopback_endpoint("https://example.com/v1")
    assert not is_loopback_endpoint("http://192.168.0.10:11434")


def test_remote_ollama_requires_explicit_text_model_opt_in(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_provider="ollama",
        model_base_url="http://192.168.0.10:11434",
        model_remote_allowed=False,
    )

    with pytest.raises(ValueError, match="remote Ollama endpoint"):
        create_model_provider(settings)

    runtime = probe_model_runtime(settings)
    assert runtime.configured is False
    assert runtime.reachable is False


def test_embedding_endpoint_is_loopback_only() -> None:
    with pytest.raises(ValueError, match="embedding endpoint must be loopback"):
        OllamaEmbeddingProvider(
            model="nomic-embed-text",
            base_url="http://192.168.0.10:11434",
        )


def test_remote_vision_requires_explicit_photo_opt_in() -> None:
    with pytest.raises(ValueError, match="remote vision endpoint"):
        OllamaVisionProvider(
            model="qwen3.5:4b",
            base_url="http://192.168.0.10:11434",
        )
