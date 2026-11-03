from pathlib import Path

import pytest

from growwise.api import resource_routes
from growwise.backup import cli as backup_cli
from growwise.config import Settings


def test_resource_ingestion_uses_independent_embedding_endpoint_and_resilience(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_base_url="https://text.example.test/v1",
        embedding_base_url="http://127.0.0.1:14444",
        embedding_timeout_seconds=2.5,
        model_circuit_failure_threshold=5,
        model_circuit_recovery_seconds=45,
    )
    captured: dict = {}
    sentinel = object()

    def embedding(**kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(resource_routes, "get_resource_settings", lambda: settings)
    monkeypatch.setattr(resource_routes, "OllamaEmbeddingProvider", embedding)
    resource_routes._get_resource_rag_index.cache_clear()
    try:
        index = resource_routes.get_resource_rag_index()
        assert index.embedding is sentinel
        assert captured == {
            "model": settings.embedding_model_id,
            "base_url": "http://127.0.0.1:14444",
            "timeout_seconds": 2.5,
            "failure_threshold": 5,
            "recovery_seconds": 45,
        }
    finally:
        resource_routes._get_resource_rag_index.cache_clear()


@pytest.mark.parametrize("enabled, provider", [(False, "ollama"), (True, "unsupported")])
def test_resource_and_restore_do_not_call_unsupported_embedding_backends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool, provider: str
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        embedding_features_enabled=enabled,
        embedding_provider=provider,
    )

    calls: list[dict] = []

    def forbidden_embedding(**kwargs):
        calls.append(kwargs)
        return object()

    monkeypatch.setattr(resource_routes, "get_resource_settings", lambda: settings)
    monkeypatch.setattr(resource_routes, "OllamaEmbeddingProvider", forbidden_embedding)
    monkeypatch.setattr(backup_cli, "OllamaEmbeddingProvider", forbidden_embedding)
    resource_routes._get_resource_rag_index.cache_clear()
    try:
        assert resource_routes.get_resource_rag_index().embedding is None
        assert backup_cli.rebuild_rag_projection(settings) == 0
        assert calls == []
    finally:
        resource_routes._get_resource_rag_index.cache_clear()
