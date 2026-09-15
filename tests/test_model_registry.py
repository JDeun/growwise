from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from growwise.model.registry import ModelArtifact, ModelIntegrityError, ModelRegistry


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fetcher(data: bytes):
    def fetch() -> bytes:
        return data

    return fetch


def test_download_with_correct_hash_succeeds_and_lists(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    data = b"model-weights-v1"

    artifact = registry.download(
        name="tiny-llm",
        tag="1.0",
        sha256=_sha256(data),
        fetcher=_fetcher(data),
    )

    assert isinstance(artifact, ModelArtifact)
    assert artifact.path.exists()
    assert artifact.path.read_bytes() == data
    assert artifact.size == len(data)

    listed = registry.list_artifacts()
    assert [a.key for a in listed] == ["tiny-llm@1.0"]
    assert registry.get("tiny-llm", "1.0") is not None
    assert registry.verify("tiny-llm", "1.0") is True


def test_download_with_wrong_hash_raises_and_leaves_no_file(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    data = b"corrupted-bytes"
    wrong = _sha256(b"what-was-expected")

    with pytest.raises(ModelIntegrityError):
        registry.download(
            name="tiny-llm",
            tag="1.0",
            sha256=wrong,
            fetcher=_fetcher(data),
        )

    assert registry.list_artifacts() == []
    assert registry.get("tiny-llm", "1.0") is None
    # No artifact file and no partial temp file left behind.
    assert list(tmp_path.glob("*.bin")) == []
    assert list(tmp_path.glob(".*")) == []


def test_verify_detects_post_hoc_corruption(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    data = b"genuine-weights"
    artifact = registry.download(
        name="tiny-llm",
        tag="1.0",
        sha256=_sha256(data),
        fetcher=_fetcher(data),
    )

    assert registry.verify("tiny-llm", "1.0") is True

    artifact.path.write_bytes(b"tampered-weights")
    assert registry.verify("tiny-llm", "1.0") is False


def test_delete_removes_file_and_entry(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    data = b"deletable"
    artifact = registry.download(
        name="tiny-llm",
        tag="1.0",
        sha256=_sha256(data),
        fetcher=_fetcher(data),
    )

    assert registry.remove("tiny-llm", "1.0") is True
    assert not artifact.path.exists()
    assert registry.get("tiny-llm", "1.0") is None
    assert registry.list_artifacts() == []
    # Removing again is a safe no-op.
    assert registry.remove("tiny-llm", "1.0") is False


def test_interrupted_download_leaves_no_partial_file(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)

    def failing_fetcher() -> bytes:
        raise ConnectionError("network dropped mid-download")

    with pytest.raises(ConnectionError):
        registry.download(
            name="tiny-llm",
            tag="1.0",
            sha256=_sha256(b"never-arrives"),
            fetcher=failing_fetcher,
        )

    assert registry.list_artifacts() == []
    assert list(tmp_path.glob("*.bin")) == []
    assert list(tmp_path.glob(".*")) == []


def test_verify_unknown_and_missing_file(tmp_path: Path) -> None:
    registry = ModelRegistry(tmp_path)
    with pytest.raises(KeyError):
        registry.verify("absent", "1.0")

    data = b"weights"
    artifact = registry.download(
        name="tiny-llm",
        tag="1.0",
        sha256=_sha256(data),
        fetcher=_fetcher(data),
    )
    artifact.path.unlink()
    with pytest.raises(FileNotFoundError):
        registry.verify("tiny-llm", "1.0")
