from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.config import Settings
from growwise.domain import (
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    MaterialKind,
    ResourceKind,
    ResourceRecord,
    Stage,
    WorkflowRun,
)
from growwise.idempotency import SQLiteIdempotencyStore, request_fingerprint
from growwise.jobs import SQLiteJobQueue
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore
from growwise.services.entity_links import EntityLinkService
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore
from growwise.workflows import build_observation_graph


def test_child_purge_removes_live_and_derived_data_without_touching_sibling(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="삭제 대상", nickname="삭제 대상", stage=Stage.INFANT_0_2)
    sibling = ChildProfile(name="보존 대상", nickname="보존 대상", stage=Stage.INFANT_0_2)
    store.save(child)
    store.save(sibling)

    log = LearningLog(child_id=child.id, parent_observation="삭제할 관찰")
    sibling_log = LearningLog(child_id=sibling.id, parent_observation="보존할 관찰")
    resource = ResourceRecord(
        child_id=child.id,
        kind=ResourceKind.NOTE,
        title="삭제할 자료",
        content="삭제할 내용",
    )
    material = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.ACTIVITY_GUIDE,
        title="삭제할 생성물",
        content_markdown="# 삭제",
    )
    workflow = WorkflowRun(
        child_id=child.id,
        workflow_type="observation_ingest",
        thread_id="purge-target-thread",
    )
    for entity in (log, sibling_log, resource, material, workflow):
        store.save(entity)
    # Create a .bak generation as well; privacy deletion must remove it.
    log.parent_observation = "삭제할 관찰 수정본"
    store.save(log)

    rag = HybridRagIndex(settings.rag_index_path)
    ResourceIngestor(rag).ingest(resource)
    sibling_resource = ResourceRecord(
        child_id=sibling.id,
        kind=ResourceKind.NOTE,
        title="보존할 자료",
        content="보존 키워드",
    )
    store.save(sibling_resource)
    ResourceIngestor(rag).ingest(sibling_resource)

    links = EntityLinkService(store)
    # Both directions matter for privacy cleanup: a surviving sibling-owned source shared into the
    # deleted child and a soon-to-be-deleted source shared out to a surviving sibling.
    inbound_share = links.share_with_children(
        source_id=sibling_resource.id,
        child_ids=[child.id],
    )[0]
    outbound_share = links.share_with_children(
        source_id=resource.id,
        child_ids=[sibling.id],
    )[0]

    conversations = SQLiteConversationStore(settings.conversations_path)
    target_session = ConversationSession(child_id=str(child.id))
    target_session.turns.append(ConversationTurn(role="user", content="삭제할 대화"))
    sibling_session = ConversationSession(child_id=str(sibling.id))
    sibling_session.turns.append(ConversationTurn(role="user", content="보존할 대화"))
    conversations.save(target_session)
    conversations.save(sibling_session)

    jobs = SQLiteJobQueue(settings.jobs_path)
    jobs.enqueue("child-work", {"child_id": str(child.id), "value": "delete"})
    jobs.enqueue("sibling-work", {"child_id": str(sibling.id), "value": "keep"})

    idempotency = SQLiteIdempotencyStore(settings.idempotency_path)
    idempotency.record(
        key="target-key",
        request_hash=request_fingerprint({"child_id": str(child.id)}),
        resource_type="learning_log",
        resource_id=str(log.id),
    )
    idempotency.record(
        key="sibling-key",
        request_hash=request_fingerprint({"child_id": str(sibling.id)}),
        resource_type="learning_log",
        resource_id=str(sibling_log.id),
    )

    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    graph = build_observation_graph(checkpointer=saver)
    target_config = {"configurable": {"thread_id": workflow.thread_id}}
    sibling_config = {"configurable": {"thread_id": "sibling-thread"}}
    graph.invoke(
        {"child_id": str(child.id), "observation": "삭제할 checkpoint"},
        config=target_config,
    )
    graph.invoke(
        {"child_id": str(sibling.id), "observation": "보존할 checkpoint"},
        config=sibling_config,
    )
    connection.close()

    result = ChildPurgeService(settings).purge(str(child.id))

    assert result.child_id == str(child.id)
    assert result.markdown_files_deleted >= 5
    assert result.links_deleted >= 2
    assert result.backups_may_contain_deleted_child is True
    assert store.index.get_entity(str(child.id), entity_type="child_profile") is None
    assert store.index.list_entities(child_id=str(child.id)) == []
    assert store.index.get_entity(str(sibling.id), entity_type="child_profile") is not None
    assert store.index.get_entity(str(sibling_log.id), entity_type="learning_log") is not None
    assert store.index.get_entity(str(sibling_resource.id), entity_type="resource") is not None
    assert store.index.get_entity(str(inbound_share.id), entity_type="entity_link") is None
    assert store.index.get_entity(str(outbound_share.id), entity_type="entity_link") is None
    assert links.child_scope_targets(sibling_resource.id) == []
    child_id_in_records = any(
        str(child.id) in path.read_text(errors="ignore")
        for path in settings.records_dir.rglob("*.*")
    )
    assert not child_id_in_records
    assert rag.search(query="삭제할", child_id=str(child.id), limit=10) == []
    assert rag.search(query="보존", child_id=str(sibling.id), limit=10)
    assert conversations.list_for_child(str(child.id)) == []
    assert conversations.list_for_child(str(sibling.id))
    assert idempotency.get("target-key") is None
    assert idempotency.get("sibling-key") is not None

    remaining_job = jobs.claim_next()
    assert remaining_job is not None
    assert remaining_job.payload["child_id"] == str(sibling.id)

    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    assert saver.get_tuple(target_config) is None
    assert saver.get_tuple(sibling_config) is not None
    connection.close()
