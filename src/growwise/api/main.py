from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field
from uuid6 import uuid7

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
from growwise.generators import MaterialGenerationService
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
    ChildContextService,
    ConversationService,
    ConversationSession,
    GrowthMapService,
    InfantActivityService,
    InvalidActivityTransition,
    NaturalLanguageSearch,
    ObservationEnricher,
    SQLiteConversationStore,
)
from growwise.storage import EntityStore
from growwise.workflows import build_observation_graph

app = FastAPI(title="GrowWise Core", version="0.1.0a0")


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
def get_observation_graph():
    settings = get_settings()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_observation_graph(checkpointer=checkpointer)


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
        "operation_mode": (
            "ai_enhanced_with_core_fallback" if llm_effective else "core_only"
        ),
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
) -> ActivityPlan:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    activity = ActivityPlan(
        child_id=child_id,
        title=request.title,
        source_refs=request.source_refs,
        parent_note=request.parent_note,
    )
    store.save(activity)
    return activity


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


@app.post("/v1/resources", response_model=ResourceRecord)
def create_resource(
    request: ResourceCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ResourceRecord:
    resource = ResourceRecord(**request.model_dump())
    store.save(resource)
    ResourceIngestor(get_rag_index()).ingest(resource)
    return resource


@app.get("/v1/resources")
def list_resources(
    store: Annotated[EntityStore, Depends(get_store)],
    child_id: UUID | None = None,
) -> list[dict]:
    return store.index.list_entities(
        entity_type="resource",
        child_id=str(child_id) if child_id else None,
    )


@app.post("/v1/rag/ask")
def ask_resources(request: RagQuestionRequest) -> dict:
    service = GroundedRagService(
        index=get_rag_index(),
        provider=get_model_provider(),
    )
    return service.ask(
        query=request.question,
        child_id=str(request.child_id) if request.child_id else None,
        limit=request.limit,
    ).model_dump(mode="json")


@app.post("/v1/children/{child_id}/ask")
def ask_child_context(
    child_id: UUID,
    request: ChildQuestionRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    return build_child_context_service(store).ask(
        child_id=str(child_id),
        query=request.question,
        limit=request.limit,
    ).model_dump(mode="json")


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
    material = MaterialGenerationService(provider=get_model_provider()).generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=request.source_refs,
    )
    store.save(material)
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
    try:
        MaterialReviewService().transition(material, request.status, note=request.note)
    except InvalidMaterialTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(material)
    return material


@app.post("/v1/observations", response_model=LearningLog)
def create_observation(
    request: ObservationRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> LearningLog:
    validate_activity_link(
        store=store,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
    )
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
                pass

        log = LearningLog(
            child_id=request.child_id,
            activity_plan_id=request.activity_plan_id,
            parent_observation=state["normalized_observation"],
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
        return log
    except HTTPException:
        raise
    except Exception:
        workflow.status = WorkflowStatus.FAILED
        workflow.last_error_code = "observation_workflow_failed"
        workflow.updated_at = datetime.now(UTC)
        store.save(workflow)
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
    activity = ActivityPlan.model_validate(payload)
    logs = store.index.list_entities(
        entity_type="learning_log",
        child_id=str(activity.child_id),
    )
    return [item for item in logs if item.get("activity_plan_id") == str(activity_id)]


@app.get("/v1/children/{child_id}/growth-map")
def get_growth_map(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    days: Annotated[int, Query(ge=1, le=3650)] = 30,
) -> dict:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    projection = GrowthMapService(store.index).project(
        child_id=str(child_id),
        period_days=days,
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
