from pathlib import Path

import pytest

from growwise.config import Settings


def test_current_local_model_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROWWISE_MODEL_ID", raising=False)
    monkeypatch.delenv("GROWWISE_VISION_MODEL_ID", raising=False)
    monkeypatch.delenv("GROWWISE_EMBEDDING_MODEL_ID", raising=False)

    settings = Settings(data_dir=tmp_path)

    assert settings.model_id == "qwen3.5:9b"
    assert settings.vision_model_id == "qwen3.5:9b"
    assert settings.embedding_model_id == "nomic-embed-text"
