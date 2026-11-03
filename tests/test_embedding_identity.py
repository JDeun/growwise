import json
import sqlite3
import threading
from pathlib import Path

import pytest

from growwise.rag import HybridRagIndex, ResourceChunk


class Embedding:
    def __init__(self, model: str, *, dimensions: int = 2, port: int = 11434) -> None:
        self.model = model
        self.base_url = f"http://127.0.0.1:{port}"
        self.dimensions = dimensions
        self.documents: list[str] = []
        self.fail_documents = False
        self.fail_query = False

    def _vector(self, text: str) -> list[float]:
        cat = "고양이" in text or text == "meow"
        vector = [1.0, 0.0] if cat else [0.0, 1.0]
        if self.model == "model-b":
            vector.reverse()
        return [*vector, *([0.0] * (self.dimensions - 2))]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents.extend(texts)
        if self.fail_documents:
            raise ConnectionError("local model unavailable")
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if self.fail_query:
            raise ConnectionError("local model unavailable")
        return self._vector(text)


def chunk(resource_id: str, text: str, child_id: str = "a") -> ResourceChunk:
    return ResourceChunk(chunk_id=f"{resource_id}:0", resource_id=resource_id,
                         child_id=child_id, title=resource_id, text=text,
                         source_url=None, source_name=None, tags=())


def baseline(path: Path) -> None:
    index = HybridRagIndex(path, embedding=Embedding("model-a"))
    index.replace_resource([chunk("cat", "고양이를 관찰한다")])
    index.replace_resource([chunk("dog", "강아지를 관찰한다")])
    index.replace_resource([chunk("private", "다른아이 비공개 고양이", "b")])


def wait_for_refresh(index: HybridRagIndex) -> None:
    assert index._refresh_thread is not None
    index._refresh_thread.join(timeout=5)
    assert not index._refresh_thread.is_alive()


@pytest.mark.parametrize("model, dimensions, port", [
    ("model-b", 2, 11434),
    ("model-a", 3, 11434),
    ("model-a", 2, 14444),
])
def test_model_endpoint_or_dimension_change_reembeds_visible_source_text(
    tmp_path: Path, model: str, dimensions: int, port: int
) -> None:
    path = tmp_path / "rag.sqlite3"
    baseline(path)
    provider = Embedding(model, dimensions=dimensions, port=port)
    index = HybridRagIndex(path, embedding=provider)

    # Equal dimensions are insufficient: model-b reverses the same two-dimensional vector space.
    assert index.search(query="meow", child_id="a") == []
    wait_for_refresh(index)
    hits = index.search(query="meow", child_id="a")
    assert [hit["resource_id"] for hit in hits] == ["cat"]
    assert hits[0]["vector_score"] == pytest.approx(1)
    assert set(provider.documents) == {"고양이를 관찰한다", "강아지를 관찰한다"}
    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT child_id, text, embedding_json, embedding_identity FROM rag_chunks"
        ).fetchall()
    assert len(rows) == 3
    visible = [row for row in rows if row[0] == "a"]
    assert all(len(json.loads(row[2])) == dimensions for row in visible)
    assert len({row[3] for row in visible}) == 1
    private = next(row for row in rows if row[0] == "b")
    assert len(json.loads(private[2])) == 2
    if model != "model-a" or port != 11434:
        assert private[3] != visible[0][3]

    provider.documents.clear()
    assert index.search(query="meow", child_id="a")
    assert provider.documents == []


def test_failed_reembedding_never_compares_stale_vectors_and_retries_after_recovery(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rag.sqlite3"
    baseline(path)
    provider = Embedding("model-b")
    provider.fail_documents = True
    index = HybridRagIndex(path, embedding=provider)
    assert index.search(query="meow", child_id="a") == []
    wait_for_refresh(index)
    hits = index.search(query="고양이", child_id="a")
    assert [hit["resource_id"] for hit in hits] == ["cat"]
    assert hits[0]["vector_score"] == 0
    wait_for_refresh(index)
    provider.fail_query = True
    assert index.search(query="고양이", child_id="a")[0]["vector_score"] == 0

    provider.fail_query = False
    provider.fail_documents = False
    assert index.search(query="meow", child_id="a") == []
    wait_for_refresh(index)
    assert index.search(query="meow", child_id="a")[0]["resource_id"] == "cat"


def test_legacy_vectors_without_model_identity_are_migrated_from_preserved_text(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rag.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE rag_chunks (
            chunk_id TEXT PRIMARY KEY, resource_id TEXT NOT NULL, child_id TEXT,
            title TEXT NOT NULL, text TEXT NOT NULL, source_url TEXT, source_name TEXT,
            tags_json TEXT NOT NULL, embedding_json TEXT)""")
        connection.execute(
            "INSERT INTO rag_chunks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("cat:0", "cat", "a", "cat", "고양이를 관찰한다", None, None, "[]", "[1, 0]"),
        )
    provider = Embedding("model-b")
    index = HybridRagIndex(path, embedding=provider)
    assert index.search(query="meow", child_id="a") == []
    wait_for_refresh(index)
    hits = index.search(query="meow", child_id="a")
    assert [hit["resource_id"] for hit in hits] == ["cat"]
    assert provider.documents == ["고양이를 관찰한다"]
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT text, embedding_json, embedding_identity FROM rag_chunks"
        ).fetchone()
    assert row is not None
    assert row[0] == "고양이를 관찰한다"
    assert json.loads(row[1]) == [0, 1]
    assert len(row[2]) == 64


def test_reembedding_cannot_attach_stale_vectors_after_source_text_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rag.sqlite3"
    baseline(path)
    provider = Embedding("model-b")
    embed = provider.embed_documents

    def replace_during_inference(texts: list[str]) -> list[list[float]]:
        HybridRagIndex(path).replace_resource([chunk("cat", "부모가 새로 고친 원문")])
        return embed(texts)

    monkeypatch.setattr(provider, "embed_documents", replace_during_inference)
    index = HybridRagIndex(path, embedding=provider)
    index.search(query="meow", child_id="a")
    wait_for_refresh(index)
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT text, embedding_json, embedding_identity FROM rag_chunks "
            "WHERE resource_id='cat'"
        ).fetchone()
    assert row == ("부모가 새로 고친 원문", None, None)


def test_slow_reembedding_returns_lexical_hits_without_queuing_more_work(tmp_path: Path) -> None:
    started, release = threading.Event(), threading.Event()

    class SlowEmbedding(Embedding):
        def __init__(self) -> None:
            super().__init__("model-b")
            self.batches: list[int] = []

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            self.batches.append(len(texts))
            started.set()
            assert release.wait(timeout=5)
            return super().embed_documents(texts)

    path = tmp_path / "rag.sqlite3"
    original = HybridRagIndex(path)
    for number in range(65):
        original.replace_resource([chunk(f"cat-{number:03}", "고양이 관찰")])
    original.replace_resource([chunk("other", "다른 아이의 고양이", "b")])
    provider = SlowEmbedding()
    index = HybridRagIndex(path, embedding=provider)
    try:
        hits = index.search(query="고양이", child_id="a", limit=1)
        assert len(hits) == 1 and hits[0]["vector_score"] == 0
        assert started.wait(timeout=2)
        first_worker = index._refresh_thread
        for _ in range(8):
            assert len(index.search(query="고양이", child_id="a", limit=1)) == 1
        assert index._refresh_thread is first_worker
        assert provider.batches == [32]
    finally:
        release.set()
        wait_for_refresh(index)
    assert provider.batches == [32, 32, 1]
    assert "다른 아이의 고양이" not in provider.documents
    assert index.search(query="meow", child_id="a", limit=1)[0]["vector_score"] == 1


def test_reembedding_does_not_write_after_restore_generation_changes(tmp_path: Path) -> None:
    from growwise.maintenance import DATA_MAINTENANCE

    started, release = threading.Event(), threading.Event()

    class PausedEmbedding(Embedding):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            started.set()
            assert release.wait(timeout=5)
            return super().embed_documents(texts)

    path = tmp_path / "rag.sqlite3"
    baseline(path)
    index = HybridRagIndex(path, embedding=PausedEmbedding("model-b"))
    try:
        index.search(query="고양이", child_id="a")
        assert started.wait(timeout=2)
        with DATA_MAINTENANCE.maintenance(invalidate_generation=True):
            pass
    finally:
        release.set()
        wait_for_refresh(index)
    with sqlite3.connect(path) as connection:
        identities = connection.execute(
            "SELECT DISTINCT embedding_identity FROM rag_chunks WHERE child_id='a'"
        ).fetchall()
    assert len(identities) == 1
    assert identities[0][0] != index._embedding_identity()
