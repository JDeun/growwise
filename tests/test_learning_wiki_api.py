from pathlib import Path

from fastapi.testclient import TestClient

from growwise.api import learning_wiki_routes
from growwise.api.dependencies import get_rag_index, get_store
from growwise.api.main import app
from growwise.config import Settings
from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.rag import HybridRagIndex
from growwise.storage import EntityStore


def test_learning_wiki_read_and_rebuild_routes_preserve_original_and_child_scope(
    tmp_path: Path, monkeypatch
) -> None:
    settings = Settings(data_dir=tmp_path, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="테스트아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른테스트아이", stage=Stage.ELEMENTARY)
    store.save(child)
    store.save(sibling)
    log = LearningLog(child_id=child.id, parent_observation="씨앗을 살펴보았다.",
                      child_question="씨앗은 왜 날아가?")
    original = store.save(log)
    original_bytes = original.read_bytes()
    store.save(LearningLog(child_id=sibling.id, parent_observation="다른아이의 비공개 기록"))
    rag = HybridRagIndex(settings.rag_index_path)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_rag_index] = lambda: rag
    monkeypatch.setattr(learning_wiki_routes, "get_model_provider", lambda: None)
    try:
        client = TestClient(app)
        first = client.get(f"/v1/children/{child.id}/learning-wiki")
        assert first.status_code == 200
        wiki = first.json()
        assert wiki["child_id"] == str(child.id)
        assert wiki["derived"] is True
        assert f"learning_log:{log.id}" in wiki["source_refs"]
        assert "다른아이의 비공개" not in wiki["content_markdown"]
        assert original.read_bytes() == original_bytes

        rebuilt = client.post(f"/v1/children/{child.id}/learning-wiki/rebuild")
        assert rebuilt.status_code == 200
        assert rebuilt.json()["revision"] == wiki["revision"] + 1
        assert original.read_bytes() == original_bytes
        missing = client.get("/v1/children/00000000-0000-0000-0000-000000000000/learning-wiki")
        assert missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_store, None)
        app.dependency_overrides.pop(get_rag_index, None)
