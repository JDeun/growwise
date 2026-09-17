from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from uuid6 import uuid7

from growwise.api.backup_routes import router as backup_router
from growwise.api.contracts import (
    ActivityCreateRequest,
    ActivityTransitionRequest,
    ChildCreateRequest,
    ChildQuestionRequest,
    ConversationCreateRequest,
    ConversationTurnRequest,
    MaterialEditRequest,
    MaterialGenerateRequest,
    MaterialReviewRequest,
    MaterialRevisionRequest,
    ObservationRequest,
    RagQuestionRequest,
    ResourceCreateRequest,
)
from growwise.api.study_routes import router as study_router
from growwise.config import Settings
from growwise.domain import (
    ActivityPlan,
    ChildProfile,
    GeneratedMaterial,
    LearningLog,
    MaterialStatus,
    ResourceRecord,
    Stage,
    WorkflowRun,
    WorkflowStatus,
)
from growwise.generators import (
    MaterialEditError,
    MaterialEditService,
    MaterialGenerationService,
    MaterialRevisionError,
    MaterialRevisionService,
    MaterialSourceEvidence,
)
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.material_versions import serialize_material_successor
from growwise.model import ModelProvider, create_model_provider
from growwise.model.health import probe_model_runtime
from growwise.rag import (
    GroundedRagService,
    HybridRagIndex,
    OllamaEmbeddingProvider,
    ResourceIngestor,
)
from growwise.review import InvalidMaterialTransition, MaterialReviewService
from growwise.services import (
    ActivityPlanService,
    BoardBookRecommendationService,
    ChildContextService,
    ConversationService,
    ConversationSession,
    GrowthMapService,
    InfantActivityService,
    InfantObservationHintService,
    InvalidActivityTransition,
    NaturalLanguageSearch,
    ObservationEnricher,
    SQLiteConversationStore,
)
from growwise.services.visibility import entity_visible_to_child, shared_source_ids
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph, build_observation_graph

logger = logging.getLogger(__name__)

app = FastAPI(title="GrowWise Core", version="0.1.0a0")
app.include_router(backup_router)
app.include_router(study_router)

_MATERIAL_SOURCE_EXCERPT_CHARS = 4_000


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_model_provider() -> ModelProvider | None:
    settings = get_settings()
    if not settings.llm_features_enabled:
        return None
    try:
        return create_model_provider(settings)
    except Exception:
        logger.exception("model provider unavailable; continuing in deterministic core-only mode")
        return None


@lru_cache
def get_rag_index() -> HybridRagIndex:
    settings = get_settings()
    embedding = None
    if settings.embedding_features_enabled:
        try:
            embedding = OllamaEmbeddingProvider(
                model=settings.embedding_model_id,
                base_url=settings.model_base_url,
            )
        except Exception:
            logger.exception("embedding provider unavailable; RAG will use lexical search")
            embedding = None
    return HybridRagIndex(settings.rag_index_path, embedding=embedding)


@lru_cache
def get_conversation_store() -> SQLiteConversationStore:
    return SQLiteConversationStore(get_settings().conversations_path)


@lru_cache
def get_idempotency_store() -> SQLiteIdempotencyStore:
    return SQLiteIdempotencyStore(get_settings().idempotency_path)


@lru_cache
def get_observation_graph():
    settings = get_settings()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_observation_graph(checkpointer=checkpointer)


@lru_cache
def get_material_review_graph():
    settings = get_settings()
    try:
        settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        return build_material_review_graph(checkpointer=checkpointer)
    except Exception:
        logger.exception(
            "material review checkpoint unavailable; using rebuildable in-memory projection"
        )
        return build_material_review_graph(checkpointer=None)


def build_child_context_service(store: EntityStore) -> ChildContextService:
    return ChildContextService(
        entity_index=store.index,
        rag_index=get_rag_index(),
        provider=get_model_provider(),
    )


def validate_activity_link(
    *,
    store: EntityStore,
    child_id: UUID,
    activity_plan_id: UUID | None,
) -> ActivityPlan | None:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    if activity_plan_id is None:
        return None
    payload = store.index.get_entity(str(activity_plan_id), entity_type="activity_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="activity_not_found")
    if not entity_visible_to_child(
        store.index,
        entity_id=str(activity_plan_id),
        child_id=str(child_id),
        entity_type="activity_plan",
    ):
        raise HTTPException(status_code=409, detail="activity_child_mismatch")
    return ActivityPlan.model_validate(payload)


@app.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    runtime = probe_model_runtime(settings)
    llm_effective = settings.llm_features_enabled and runtime.reachable
    embedding_effective = settings.embedding_features_enabled and runtime.reachable
    return {
        "status": "ok",
        "operation_mode": ("ai_enhanced_with_core_fallback" if llm_effective else "core_only"),
        "core_requires_llm": False,
        "llm_configured": runtime.configured,
        "llm_reachable": runtime.reachable,
        "llm_features_enabled": llm_effective,
        "embedding_features_enabled": embedding_effective,
        "model_provider": settings.model_provider,
    }


@app.post("/v1/children", response_model=ChildProfile)
def create_child(
    request: ChildCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ChildProfile:
    profile = ChildProfile(**request.model_dump())
    store.save(profile)
    return profile


@app.get("/v1/children", response_model=list[ChildProfile])
def list_children(
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[ChildProfile]:
    return [
        ChildProfile.model_validate(payload)
        for payload in store.index.list_entities(entity_type="child_profile")
    ]


@app.post("/v1/children/{child_id}/activities", response_model=ActivityPlan)
def create_activity(
    child_id: UUID,
    request: ActivityCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> ActivityPlan:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")

    idempotency_store = get_idempotency_store()
    request_hash = request_fingerprint(
        {"child_id": str(child_id), **request.model_dump(mode="json")}
    )
    reserved_activity_id: UUID = uuid7()
    claim = None
    if idempotency_key is not None:
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="activity_plan",
                resource_id=str(reserved_activity_id),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reserved_activity_id = UUID(claim.record.resource_id)
        if not claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type="activity_plan")
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return ActivityPlan.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    activity = ActivityPlan(
        id=reserved_activity_id,
        child_id=child_id,
        title=request.title,
        source_refs=request.source_refs,
        parent_note=request.parent_note,
    )
    try:
        store.save(activity)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return activity
    except Exception:
        if claim is not None and claim.acquired:
            idempotency_store.release(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        raise


@app.get("/v1/children/{child_id}/activities")
def list_activities(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    return store.index.list_entities(entity_type="activity_plan", child_id=str(child_id))


@app.post("/v1/activities/{activity_id}/transition", response_model=ActivityPlan)
def transition_activity(
    activity_id: UUID,
    request: ActivityTransitionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ActivityPlan:
    payload = store.index.get_entity(str(activity_id), entity_type="activity_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="activity_not_found")
    activity = ActivityPlan.model_validate(payload)
    try:
        ActivityPlanService().transition(
            activity,
            request.status,
            parent_note=request.parent_note,
        )
    except InvalidActivityTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(activity)
    return activity


# Compatibility helpers for direct service-level tests. HTTP /v1/resources collection routes are
# owned solely by growwise.api.resource_routes to prevent duplicate FastAPI route registration.
def create_resource(
    request: ResourceCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ResourceRecord:
    resource = ResourceRecord(**request.model_dump())
    store.save(resource)
    ResourceIngestor(get_rag_index()).ingest(resource)
    return resource


def list_resources(
    store: Annotated[EntityStore, Depends(get_store)],
    child_id: UUID | None = None,
) -> list[dict]:
    return store.index.list_entities(
        entity_type="resource",
        child_id=str(child_id) if child_id else None,
    )


@app.post("/v1/rag/ask")
def ask_resources(
    request: RagQuestionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    child_id = str(request.child_id) if request.child_id else None
    if (
        child_id is not None
        and store.index.get_entity(child_id, entity_type="child_profile") is None
    ):
        raise HTTPException(status_code=404, detail="child_not_found")
    service = GroundedRagService(
        index=get_rag_index(),
        provider=get_model_provider(),
    )
    return service.ask(
        query=request.question,
        child_id=child_id,
        limit=request.limit,
        shared_resource_ids=(shared_source_ids(store.index, child_id) if child_id else None),
    ).model_dump(mode="json")


@app.post("/v1/children/{child_id}/ask")
def ask_child_context(
    child_id: UUID,
    request: ChildQuestionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return (
        build_child_context_service(store)
        .ask(
            child_id=str(child_id),
            query=request.question,
            limit=request.limit,
        )
        .model_dump(mode="json")
    )


@app.post("/v1/children/{child_id}/conversations", response_model=ConversationSession)
def create_conversation(
    child_id: UUID,
    request: ConversationCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ConversationSession:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    session = ConversationSession(child_id=str(child_id), title=request.title)
    get_conversation_store().save(session)
    return session


@app.get("/v1/children/{child_id}/conversations")
def list_conversations(
    child_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict]:
    sessions = get_conversation_store().list_for_child(str(child_id), limit=limit)
    return [session.model_dump(mode="json") for session in sessions]


@app.get("/v1/conversations/{session_id}", response_model=ConversationSession)
def get_conversation(session_id: str) -> ConversationSession:
    session = get_conversation_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return session


@app.post("/v1/conversations/{session_id}/turns")
def append_conversation_turn(
    session_id: str,
    request: ConversationTurnRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    conversation_store = get_conversation_store()
    session = conversation_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    if store.index.get_entity(session.child_id, entity_type="child_profile") is None:
        raise HTTPException(status_code=409, detail="conversation_child_not_found")

    service = ConversationService(
        context_service=build_child_context_service(store),
        provider=get_model_provider(),
    )
    answer = service.ask(session=session, question=request.question, limit=request.limit)
    conversation_store.save(session)
    return {
        "session_id": session.id,
        "thread_id": session.id,
        "answer": answer.model_dump(mode="json"),
        "turn_count": len(session.turns),
    }


@app.delete("/v1/conversations/{session_id}")
def delete_conversation(session_id: str) -> dict[str, bool]:
    return {"deleted": get_conversation_store().delete(session_id)}


def validate_material_source_refs(
    *,
    child_id: UUID,
    source_refs: list[str],
    store: EntityStore,
) -> list[str]:
    """Resolve material provenance to existing resources within the child's scope."""
    validated: list[str] = []
    visible_shared_ids = shared_source_ids(store.index, str(child_id))
    for ref in dict.fromkeys(source_refs):
        if not ref.startswith("resource:"):
            raise HTTPException(status_code=422, detail="material_source_ref_invalid")
        raw_id = ref.removeprefix("resource:")
        try:
            resource_id = UUID(raw_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="material_source_ref_invalid") from exc
        payload = store.index.get_entity(str(resource_id), entity_type="resource")
        if payload is None:
            raise HTTPException(status_code=422, detail="material_source_not_found")
        if not entity_visible_to_child(
            store.index,
            entity_id=str(resource_id),
            child_id=str(child_id),
            entity_type="resource",
            shared_ids=visible_shared_ids,
        ):
            raise HTTPException(status_code=409, detail="material_source_child_mismatch")
        resource = ResourceRecord.model_validate(payload)
        validated.append(f"resource:{resource.id}")
    return validated


def material_source_evidence(
    *,
    source_refs: list[str],
    store: EntityStore,
) -> list[MaterialSourceEvidence]:
    """Load bounded excerpts for already validated resource refs.

    Source content remains untrusted. The generator wraps these excerpts as evidence and applies
    its own total prompt budget, so a large saved resource cannot monopolize the model context.
    """
    evidence: list[MaterialSourceEvidence] = []
    for ref in source_refs:
        raw_id = ref.removeprefix("resource:")
        payload = store.index.get_entity(raw_id, entity_type="resource")
        if payload is None:
            continue
        resource = ResourceRecord.model_validate(payload)
        parts: list[str] = []
        if resource.summary:
            parts.append(f"요약: {resource.summary.strip()}")
        if resource.content:
            content = resource.content.strip()
            if content and content != (resource.summary or "").strip():
                parts.append(f"내용: {content}")
        excerpt = "\n\n".join(parts)[:_MATERIAL_SOURCE_EXCERPT_CHARS]
        evidence.append(
            MaterialSourceEvidence(
                source_ref=ref,
                title=resource.title,
                excerpt=excerpt,
            )
        )
    return evidence


@app.post("/v1/children/{child_id}/materials", response_model=GeneratedMaterial)
def generate_material(
    child_id: UUID,
    request: MaterialGenerateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    source_refs = validate_material_source_refs(
        child_id=child.id,
        source_refs=request.source_refs,
        store=store,
    )
    source_evidence = material_source_evidence(source_refs=source_refs, store=store)
    material = MaterialGenerationService(provider=get_model_provider()).generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=source_refs,
        source_evidence=source_evidence,
    )
    material.request_topic = request.topic
    material.request_goal = request.goal
    store.save(material)
    review_config = {"configurable": {"thread_id": f"material-review:{material.id}"}}
    get_material_review_graph().invoke(
        {
            "material_id": str(material.id),
            "child_id": str(child.id),
            "title": material.title,
        },
        config=review_config,
    )
    return material


@app.get("/v1/children/{child_id}/materials")
def list_materials(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    return store.index.list_entities(entity_type="generated_material", child_id=str(child_id))


@app.get("/v1/materials/{material_id}", response_model=GeneratedMaterial)
def get_material(
    material_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    return GeneratedMaterial.model_validate(payload)


@app.post("/v1/materials/{material_id}/review", response_model=GeneratedMaterial)
def review_material(
    material_id: UUID,
    request: MaterialReviewRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    if material.status is MaterialStatus.REVIEW_PENDING:
        config = {"configurable": {"thread_id": f"material-review:{material.id}"}}
        try:
            review_state = get_material_review_graph().invoke(
                Command(
                    resume={
                        "status": request.status.value,
                        "note": request.note,
                    }
                ),
                config=config,
            )
            if review_state.get("decision_status") != request.status.value:
                raise HTTPException(status_code=409, detail="review_decision_mismatch")
        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "material review projection unavailable; applying domain transition directly"
            )
    try:
        MaterialReviewService().transition(material, request.status, note=request.note)
    except InvalidMaterialTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(material)
    return material


@app.post("/v1/materials/{material_id}/revise", response_model=GeneratedMaterial)
@serialize_material_successor
def revise_material(
    material_id: UUID,
    request: MaterialRevisionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    if material.status is not MaterialStatus.REVISION_REQUESTED:
        raise HTTPException(
            status_code=409,
            detail="material must be revision_requested before regeneration",
        )

    child_payload = store.index.get_entity(str(material.child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=409, detail="material_child_not_found")
    child = ChildProfile.model_validate(child_payload)

    existing_revisions = store.index.list_entities(
        entity_type="generated_material",
        child_id=str(material.child_id),
    )
    for candidate in existing_revisions:
        if candidate.get("parent_material_id") == str(material.id):
            return GeneratedMaterial.model_validate(candidate)

    source_evidence = material_source_evidence(source_refs=material.source_refs, store=store)
    try:
        revised = MaterialRevisionService(
            MaterialGenerationService(provider=get_model_provider())
        ).revise(
            material=material,
            child=child,
            note=request.note,
            source_evidence=source_evidence,
        )
    except MaterialRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    store.save(revised)
    review_config = {"configurable": {"thread_id": f"material-review:{revised.id}"}}
    get_material_review_graph().invoke(
        {
            "material_id": str(revised.id),
            "child_id": str(child.id),
            "title": revised.title,
        },
        config=review_config,
    )
    return revised


@app.post("/v1/materials/{material_id}/edit", response_model=GeneratedMaterial)
@serialize_material_successor
def edit_material(
    material_id: UUID,
    request: MaterialEditRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    versions = store.index.list_entities(
        entity_type="generated_material", child_id=str(material.child_id)
    )
    if any(candidate.get("parent_material_id") == str(material.id) for candidate in versions):
        raise HTTPException(status_code=409, detail="material_has_newer_version")
    try:
        edited = MaterialEditService().create_version(
            material=material,
            title=request.title,
            content_markdown=request.content_markdown,
            note=request.note,
        )
    except MaterialEditError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(edited)
    get_material_review_graph().invoke(
        {"material_id": str(edited.id), "child_id": str(edited.child_id), "title": edited.title},
        config={"configurable": {"thread_id": f"material-review:{edited.id}"}},
    )
    return edited


@app.post("/v1/observations", response_model=LearningLog)
def create_observation(
    request: ObservationRequest,
    store: Annotated[EntityStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> LearningLog:
    validate_activity_link(
        store=store,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
    )

    idempotency_store = get_idempotency_store()
    request_hash = request_fingerprint(request.model_dump(mode="json"))
    reserved_log_id: UUID = uuid7()
    claim = None
    if idempotency_key is not None:
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="learning_log",
                resource_id=str(reserved_log_id),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        reserved_log_id = UUID(claim.record.resource_id)
        if not claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type="learning_log")
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return LearningLog.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    workflow = WorkflowRun(
        child_id=request.child_id,
        workflow_type="observation_ingest",
        thread_id=str(uuid7()),
    )
    store.save(workflow)

    try:
        graph = get_observation_graph()
        state = graph.invoke(
            {"child_id": str(request.child_id), "observation": request.observation},
            config={"configurable": {"thread_id": workflow.thread_id}},
        )
        if state.get("safety_flags"):
            workflow.status = WorkflowStatus.FAILED
            workflow.last_error_code = "observation_validation_failed"
            workflow.updated_at = datetime.now(UTC)
            store.save(workflow)
            raise HTTPException(status_code=422, detail={"flags": state["safety_flags"]})

        tags: list[str] = []
        interest: str | None = None
        difficulty_note: str | None = None
        next_activity: str | None = None
        experience_axes = list(request.experience_axes)
        provider = get_model_provider()
        if provider is not None:
            try:
                enrichment = ObservationEnricher(provider).enrich(state["normalized_observation"])
                tags = enrichment.tags
                interest = enrichment.interest
                difficulty_note = enrichment.difficulty_note
                next_activity = enrichment.next_activity
                experience_axes = list(
                    dict.fromkeys([*experience_axes, *enrichment.experience_axes])
                )
            except Exception:
                logger.exception("observation enrichment failed; deterministic record will persist")

        log = LearningLog(
            id=reserved_log_id,
            child_id=request.child_id,
            activity_plan_id=request.activity_plan_id,
            parent_observation=request.observation,
            tags=tags,
            experience_axes=experience_axes,
            interest=interest,
            difficulty_note=difficulty_note,
            next_activity=next_activity,
        )
        store.save(log)
        workflow.status = WorkflowStatus.COMPLETED
        workflow.output_ref = str(log.id)
        workflow.updated_at = datetime.now(UTC)
        store.save(workflow)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return log
    except HTTPException:
        if claim is not None and claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type="learning_log")
            if existing is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
            else:
                idempotency_store.complete(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise
    except Exception:
        workflow.status = WorkflowStatus.FAILED
        workflow.last_error_code = "observation_workflow_failed"
        workflow.updated_at = datetime.now(UTC)
        store.save(workflow)
        if claim is not None and claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type="learning_log")
            if existing is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
            else:
                idempotency_store.complete(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise


@app.get("/v1/children/{child_id}/observations")
def list_observations(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    return store.index.list_entities(entity_type="learning_log", child_id=str(child_id))


@app.get("/v1/activities/{activity_id}/observations")
def list_activity_observations(
    activity_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    payload = store.index.get_entity(str(activity_id), entity_type="activity_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="activity_not_found")
    logs = store.index.list_entities(entity_type="learning_log")
    return [item for item in logs if item.get("activity_plan_id") == str(activity_id)]


@app.get("/v1/children/{child_id}/growth-map")
def get_growth_map(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    projection = GrowthMapService(store.index).project(
        child_id=str(child_id),
        period_days=days,
        stage=child.stage,
    )
    return projection.model_dump(mode="json")


@app.get("/v1/children/{child_id}/search")
def search_child_context(
    child_id: UUID,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    service = NaturalLanguageSearch(store.index, provider=get_model_provider())
    return service.search(child_id=str(child_id), query=q, limit=limit).model_dump(mode="json")


@app.get("/v1/children/{child_id}/infant-activities")
def suggest_infant_activities(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=5)] = 3,
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")

    child = ChildProfile.model_validate(child_payload)
    if child.stage is not Stage.INFANT_0_2:
        raise HTTPException(status_code=409, detail="child_is_not_in_infant_stage")

    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child_id))
    recent_observations = [
        str(item.get("parent_observation", ""))
        for item in logs[:8]
        if item.get("parent_observation")
    ]
    service = InfantActivityService(provider=get_model_provider())
    result = service.suggest(
        age_months=child.age_months,
        recent_observations=recent_observations,
        interests=child.interests,
        limit=limit,
    )
    return result.model_dump(mode="json")


@app.get("/v1/children/{child_id}/infant-observation-hints")
def suggest_infant_observation_hints(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    if child.stage is not Stage.INFANT_0_2:
        raise HTTPException(status_code=409, detail="child_is_not_in_infant_stage")

    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child_id))
    recent_observations = [
        str(item.get("parent_observation", ""))
        for item in logs[:8]
        if item.get("parent_observation")
    ]
    result = InfantObservationHintService(provider=get_model_provider()).suggest(
        age_months=child.age_months,
        recent_observations=recent_observations,
        interests=child.interests,
    )
    return result.model_dump(mode="json")


@app.get("/v1/children/{child_id}/board-books")
def recommend_board_books(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=5)] = 3,
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    if child.stage is not Stage.INFANT_0_2:
        raise HTTPException(status_code=409, detail="child_is_not_in_infant_stage")

    visible_shared_ids = shared_source_ids(store.index, str(child_id))
    resource_payloads = store.index.list_entities(entity_type="resource")
    resources = [
        ResourceRecord.model_validate(payload)
        for payload in resource_payloads
        if entity_visible_to_child(
            store.index,
            entity_id=str(payload.get("id") or ""),
            child_id=str(child_id),
            entity_type="resource",
            shared_ids=visible_shared_ids,
        )
    ]
    result = BoardBookRecommendationService().recommend(
        resources=resources,
        interests=child.interests,
        limit=limit,
    )
    return result.model_dump(mode="json")


def run() -> None:
    # Keep `python -m growwise.api.main` on the same guarded path as the console entrypoint.
    # Import lazily so normal ASGI imports do not pull the process runner into application setup.
    from growwise.api.entry import run as guarded_run

    guarded_run()


if __name__ == "__main__":
    run()
