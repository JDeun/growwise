from __future__ import annotations

from growwise.config import Settings
from growwise.model import health as model_health


def test_model_name_matching_accepts_ollama_latest_alias() -> None:
    assert model_health._model_name_matches("example", "example:latest")
    assert model_health._model_name_matches("example:latest", "example")
    assert model_health._model_name_matches("qwen3.5:4b", "qwen3.5:4b")
    assert not model_health._model_name_matches("qwen3.5:4b", "qwen3.5:9b")


def test_ollama_runtime_requires_configured_model_to_be_present(
    monkeypatch,
    tmp_path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_provider="ollama",
        model_id="qwen3.5:4b",
        model_base_url="http://127.0.0.1:11434",
    )
    monkeypatch.setattr(model_health, "_tcp_reachable", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        model_health,
        "_ollama_model_available",
        lambda *_args, **_kwargs: False,
    )

    runtime = model_health.probe_model_runtime(settings)

    assert runtime.configured is True
    assert runtime.reachable is True
    assert runtime.model_id == "qwen3.5:4b"
    assert runtime.model_available is False


def test_ollama_runtime_reports_ready_model(
    monkeypatch,
    tmp_path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_provider="ollama",
        model_id="qwen3.5:4b",
        model_base_url="http://127.0.0.1:11434",
    )
    monkeypatch.setattr(model_health, "_tcp_reachable", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        model_health,
        "_ollama_model_available",
        lambda *_args, **_kwargs: True,
    )

    runtime = model_health.probe_model_runtime(settings)

    assert runtime.reachable is True
    assert runtime.model_available is True
