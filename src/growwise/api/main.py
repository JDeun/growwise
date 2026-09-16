from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.api.backup_routes import router as backup_router
from growwise.api.photo_routes import (
    router as photo_router,
    start_photo_job_runner,
    stop_photo_job_runner,
)
from growwise.api.privacy_routes import router as privacy_router
from growwise.api.study_routes import router as study_router
from growwise.config import Settings
from growwise.domain import (
    ActivityPlan,
    ActivityStatus,
    ChildProfile,
    ExperienceAxis,
    GeneratedMaterial,
    LearningLog,
    MaterialKind,
    MaterialStatus,
    ResourceKind,
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
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph, build_observation_graph


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_photo_job_runner()
    try:
        yield
    finally:
        stop_photo_job_runner()


app = FastAPI(title="GrowWise Core", version="0.1.0a0", lifespan=lifespan)
app.include_router(backup_router)
app.include_router(study_router)
app.include_router(photo_router)
app.include_router(privacy_router, prefix="/v1")


class ChildCreateRequest(BaseModel):
    nickname: str
    stage: Stage
    age_months: int | None = None
    interests: list[str] = Field(default_factory=list)


class ObservationRequest(BaseModel):
    child_id: UUID
    observation: str = Field(min_length=1, max_length=10_000)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)
    activity_plan_id: UUID | None = None


class ActivityCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    source_refs: list[str] = Field(default_factory=list)
    parent_note: str | None = Field(default=None, max_length=2000)


class ActivityTransitionRequest(BaseModel):
    status: ActivityStatus
    parent_note: str | None = Field(default=None, max_length=2000)


class ResourceCreateRequest(BaseModel):
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    child_id: UUID | None = None
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    stage_tags: list[Stage] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


class RagQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    child_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)


class ChildQuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationTurnRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class MaterialGenerateRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    source_refs: list[str] = Field(default_factory=list)


class MaterialReviewRequest(BaseModel):
    status: MaterialStatus
    note: str | None = Field(default=None, max_length=2000)


class MaterialRevisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class MaterialEditRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    content_markdown: str = Field(min_length=1, max_length=100_000)
    note: str | None = Field(default=None, max_length=2000)


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
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_material_review_graph(checkpointer=checkpointer)


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
    activity = ActivityPlan.model_validate(payload)
    if activity.child_id != child_id:
        raise HTTPException(status_code=409, detail="activity_child_mismatch")
    return activity


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
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
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
        transitioned = ActivityPlanService().transition(
            activity,
            request.status,
            parent_note=request.parent_note,
        )
    except InvalidActivityTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(transitioned)
    return transitioned


@app.get("/v1/activities/{activity_id}/observations", response_model=list[LearningLog])
def list_activity_observations(
    activity_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[LearningLog]:
    payload = store.index.get_entity(str(activity_id), entity_type="activity_plan")
    if payload is None:
        raise HTTPException(status_code=404, detail="activity_not_found")
    return [
        LearningLog.model_validate(item)
        for item in store.index.list_entities(entity_type="learning_log")
        if item.get("activity_plan_id") == str(activity_id)
    ]


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
    request_hash = request_fingerprint(request.model_dump(mode="json"))
    reserved_log_id: UUID = uuid7()
    claim = None
    if idempotency_key is not None:
        try:
            claim = get_idempotency_store().claim(
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
                    get_idempotency_store().complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return LearningLog.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    enrichment = None
    provider = get_model_provider()
    if provider is not None:
        try:
            enrichment = ObservationEnricher(provider).enrich(request.observation)
        except Exception:
            enrichment = None

    log = LearningLog(
        id=reserved_log_id,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
        parent_observation=request.observation,
        tags=enrichment.tags if enrichment else [],
        experience_axes=(
            request.experience_axes or (enrichment.experience_axes if enrichment else [])
        ),
        interest=enrichment.interest if enrichment else None,
        difficulty_note=enrichment.difficulty_note if enrichment else None,
        next_activity=enrichment.next_activity if enrichment else None,
    )
    try:
        store.save(log)
        if claim is not None and claim.acquired:
            get_idempotency_store().complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return log
    except Exception:
        if claim is not None and claim.acquired:
            get_idempotency_store().release(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        raise


@app.get("/v1/children/{child_id}/observations", response_model=list[LearningLog])
def list_observations(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[LearningLog]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return [
        LearningLog.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="learning_log",
            child_id=str(child_id),
        )
    ]


@app.get("/v1/children/{child_id}/growth-map")
def growth_map(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    logs = [
        LearningLog.model_validate(payload)
        for payload in store.index.list_entities(entity_type="learning_log", child_id=str(child_id))
    ]
    return GrowthMapService().build(
        child_id=child_id,
        logs=logs,
        stage=child.stage,
        period_days=days,
    ).model_dump(mode="json")


@app.post("/v1/children/{child_id}/materials")
def generate_material(
    child_id: UUID,
    request: MaterialGenerateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    service = MaterialGenerationService(
        provider=get_model_provider(),
        source_lookup=store.index,
    )
    material = service.generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=request.source_refs,
    )
    store.save(material)
    return material.model_dump(mode="json")


@app.get("/v1/children/{child_id}/materials")
def list_materials(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return store.index.list_entities(entity_type="generated_material", child_id=str(child_id))


@app.post("/v1/materials/{material_id}/review")
def review_material(
    material_id: UUID,
    request: MaterialReviewRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    try:
        reviewed = MaterialReviewService().transition(
            material,
            request.status,
            note=request.note,
        )
    except InvalidMaterialTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(reviewed)
    return reviewed.model_dump(mode="json")


@app.post("/v1/materials/{material_id}/revise")
def revise_material(
    material_id: UUID,
    request: MaterialRevisionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    service = MaterialRevisionService(provider=get_model_provider())
    try:
        revised = service.revise(material, note=request.note)
    except MaterialRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(revised)
    return revised.model_dump(mode="json")


@app.post("/v1/materials/{material_id}/edit")
def edit_material(
    material_id: UUID,
    request: MaterialEditRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    material = GeneratedMaterial.model_validate(payload)
    try:
        edited = MaterialEditService().edit(
            material,
            title=request.title,
            content_markdown=request.content_markdown,
            note=request.note,
        )
    except MaterialEditError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(edited)
    return edited.model_dump(mode="json")


@app.post("/v1/rag/resources/{resource_id}/ingest")
def ingest_resource(
    resource_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    payload = store.index.get_entity(str(resource_id), entity_type="resource")
    if payload is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    resource = ResourceRecord.model_validate(payload)
    chunks = ResourceIngestor(get_rag_index()).ingest(resource)
    return {"resource_id": str(resource_id), "chunks": chunks}


@app.post("/v1/rag/ask")
def ask_rag(request: RagQuestionRequest) -> dict:
    service = GroundedRagService(
        index=get_rag_index(),
        provider=get_model_provider(),
    )
    return service.answer(
        request.question,
        child_id=str(request.child_id) if request.child_id else None,
        limit=request.limit,
    ).model_dump(mode="json")


@app.get("/v1/children/{child_id}/search")
def search_child(
    child_id: UUID,
    q: Annotated[str, Query(min_length=1, max_length=2000)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    service = NaturalLanguageSearch(build_child_context_service(get_store(get_settings())))
    return service.search(str(child_id), q, limit=limit).model_dump(mode="json")


@app.post("/v1/children/{child_id}/conversations")
def create_conversation(
    child_id: UUID,
    request: ConversationCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    session = ConversationSession(child_id=child_id, title=request.title)
    get_conversation_store().save(session)
    return session.model_dump(mode="json")


@app.get("/v1/children/{child_id}/conversations")
def list_conversations(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict]:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return [
        session.model_dump(mode="json")
        for session in get_conversation_store().list_for_child(child_id, limit=limit)
    ]


@app.post("/v1/conversations/{session_id}/turns")
def append_conversation_turn(
    session_id: UUID,
    request: ConversationTurnRequest,
) -> dict:
    service = ConversationService(
        store=get_conversation_store(),
        search=NaturalLanguageSearch(build_child_context_service(get_store(get_settings()))),
        provider=get_model_provider(),
    )
    return service.ask(
        session_id,
        request.question,
        limit=request.limit,
    ).model_dump(mode="json")


@app.post("/v1/resources")
def create_resource(
    request: ResourceCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    resource = ResourceRecord(**request.model_dump())
    store.save(resource)
    return resource.model_dump(mode="json")


@app.get("/v1/resources")
def list_resources(
    store: Annotated[EntityStore, Depends(get_store)],
    child_id: UUID | None = None,
) -> list[dict]:
    resources = store.index.list_entities(entity_type="resource")
    if child_id is None:
        return resources
    return [item for item in resources if item.get("child_id") in (None, str(child_id))]


@app.put("/v1/resources/{resource_id}")
def update_resource(
    resource_id: UUID,
    request: ResourceCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    existing = store.index.get_entity(str(resource_id), entity_type="resource")
    if existing is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    resource = ResourceRecord(id=resource_id, **request.model_dump())
    store.save(resource)
    return resource.model_dump(mode="json")


@app.delete("/v1/resources/{resource_id}")
def delete_resource(
    resource_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict[str, bool]:
    payload = store.index.get_entity(str(resource_id), entity_type="resource")
    if payload is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    store.delete(ResourceRecord.model_validate(payload))
    return {"deleted": True}


@app.get("/v1/workflows/{thread_id}")
def get_workflow_state(thread_id: str) -> dict:
    graph = get_material_review_graph()
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    return {"values": state.values, "next": state.next}


@app.post("/v1/workflows/{thread_id}/resume")
def resume_workflow(thread_id: str, command: dict) -> dict:
    graph = get_material_review_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(Command(resume=command), config=config)
    return result


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

    resource_payloads = store.index.list_entities(entity_type="resource")
    resources = [
        ResourceRecord.model_validate(payload)
        for payload in resource_payloads
        if payload.get("child_id") in (None, str(child_id))
    ]
    result = BoardBookRecommendationService().recommend(
        resources=resources,
        interests=child.interests,
        limit=limit,
    )
    return result.model_dump(mode="json")


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "growwise.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
