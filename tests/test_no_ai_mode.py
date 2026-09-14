from uuid6 import uuid7

from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services import ConversationService, ConversationSession
from growwise.storage import EntityStore


class LocalContextStub:
    def __init__(self, entity_index, rag_index):
        self.entity_index = entity_index
        self.rag_index = rag_index

    def ask(self, *, child_id: str, query: str, limit: int = 8):
        from growwise.services import ContextAnswer

        records = self.entity_index.search_entities(
            child_id=child_id,
            query_text=query,
            entity_types=("learning_log",),
            limit=limit,
        )
        chunks = self.rag_index.search(query=query, child_id=child_id, limit=limit)
        source_ids = [f"record:{item['id']}" for item in records]
        source_ids.extend(f"chunk:{item['chunk_id']}" for item in chunks)
        return ContextAnswer(
            answer=f"관련 근거 {len(source_ids)}건",
            source_ids=source_ids,
            insufficient_evidence=not source_ids,
        )


def test_core_features_work_without_llm_or_embeddings(tmp_path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    rag_index = HybridRagIndex(tmp_path / "rag.sqlite3", embedding=None)

    child = ChildProfile(
        nickname="테스트 아이",
        stage=Stage.INFANT_0_2,
        age_months=9,
        interests=["동물"],
    )
    store.save(child)

    log = LearningLog(
        child_id=child.id,
        parent_observation="고양이 그림을 오래 바라봤다",
    )
    store.save(log)

    resource = ResourceRecord(
        id=uuid7(),
        kind=ResourceKind.BOOK,
        title="동물 그림책",
        content="고양이와 강아지를 관찰하는 그림책 활동 자료",
        tags=["고양이", "동물"],
    )
    store.save(resource)
    ResourceIngestor(rag_index).ingest(resource)

    record_hits = store.index.search_entities(
        child_id=str(child.id),
        query_text="고양이",
        entity_types=("learning_log",),
        limit=10,
    )
    resource_hits = rag_index.search(query="고양이", child_id=str(child.id), limit=10)

    assert record_hits
    assert resource_hits

    session = ConversationSession(child_id=str(child.id))
    conversation = ConversationService(
        context_service=LocalContextStub(store.index, rag_index),
        provider=None,
    )
    answer = conversation.ask(session=session, question="고양이 관련 기록")

    assert answer.source_ids
    assert len(session.turns) == 2
