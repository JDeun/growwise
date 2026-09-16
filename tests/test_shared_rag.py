from __future__ import annotations

from pathlib import Path

from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.rag import HybridRagIndex
from growwise.rag.chunking import ResourceChunk
from growwise.services.context import ChildContextService
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


def test_child_scope_resource_becomes_rag_visible_without_becoming_public(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    first = ChildProfile(name="첫째", nickname="첫째", stage=Stage.ELEMENTARY)
    second = ChildProfile(name="둘째", nickname="둘째", stage=Stage.ELEMENTARY)
    store.save(first)
    store.save(second)

    resource = ResourceRecord(
        child_id=first.id,
        kind=ResourceKind.NOTE,
        title="공룡 관찰 노트",
        content="트리케라톱스는 세 개의 뿔과 큰 프릴이 특징이다.",
        tags=["공룡"],
    )
    store.save(resource)

    rag = HybridRagIndex(settings.rag_index_path, embedding=None)
    rag.replace_resource(
        [
            ResourceChunk(
                resource_id=str(resource.id),
                chunk_id=f"{resource.id}:0",
                child_id=str(first.id),
                title=resource.title,
                text=resource.content or "",
                source_url=None,
                source_name=None,
                tags=("공룡",),
            )
        ]
    )
    service = ChildContextService(entity_index=store.index, rag_index=rag, provider=None)

    before_share = service.ask(
        child_id=str(second.id),
        query="트리케라톱스 특징",
    )
    assert before_share.insufficient_evidence is True
    assert before_share.source_ids == []

    EntityLinkService(store).share_with_children(
        source_id=resource.id,
        child_ids=[second.id],
    )

    after_share = service.ask(
        child_id=str(second.id),
        query="트리케라톱스 특징",
    )
    assert after_share.insufficient_evidence is False
    assert after_share.source_ids == [f"chunk:{resource.id}:0"]

    unrelated_child = ChildProfile(name="셋째", nickname="셋째", stage=Stage.ELEMENTARY)
    store.save(unrelated_child)
    still_private = service.ask(
        child_id=str(unrelated_child.id),
        query="트리케라톱스 특징",
    )
    assert still_private.insufficient_evidence is True
    assert still_private.source_ids == []
