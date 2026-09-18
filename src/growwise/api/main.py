from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from uuid6 import uuid7

from growwise.api.backup_routes import router as backup_router
from growwise.api.contracts import (
    ActivityCreateRequest,
    ActivityTransitionRequest,
    ChildCreateRequest,
    ChildQuestionRequest,
    MaterialEditRequest,
    MaterialGenerateRequest,
    MaterialReviewRequest,
    MaterialRevisionRequest,
    ObservationRequest,
    RagQuestionRequest,
    ResourceCreateRequest,
)
from growwise.api.conversation_routes import (
    append_conversation_turn,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)
from growwise.api.conversation_routes import router as conversation_router
from growwise.api.dependencies import (
    build_child_context_service,
    get_conversation_store,
    get_idempotency_store,
    get_material_review_graph,
    get_model_provider,
    get_observation_graph,
    get_rag_index,
    get_settings,
    get_store,
)
from growwise.api.material_routes import (
    edit_material,
    generate_material,
    get_material,
    list_materials,
    material_source_evidence,
    review_material,
    revise_material,
    validate_material_source_refs,
)
from growwise.api.material_routes import router as material_router
from growwise.api.study_routes import router as study_router
from growwise.domain import (
    ActivityPlan,
    ChildProfile,
    LearningLog,
    ResourceRecord,
    Stage,
    WorkflowRun,
    WorkflowStatus,
)
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    request_fingerprint,
)
from growwise.model.health import probe_model_runtime
from growwise.rag import (
    GroundedRagService,
    ResourceIngestor,
)
from growwise.services import (
    ActivityPlanService,
    BoardBookRecommendationService,
    GrowthMapService,
    InfantActivityService,
    InfantObservationHintService,
    InvalidActivityTransition,
    NaturalLanguageSearch,
    ObservationEnricher,
)
from growwise.services.visibility import entity_visible_to_child, shared_source_ids
from growwise.storage import EntityStore

logger = logging.getLogger(__name__)

__all__ = [
    "MaterialEditRequest",
    "MaterialGenerateRequest",
    "MaterialReviewRequest",
    "MaterialRevisionRequest",
    "get_conversation_store",
    "get_material_review_graph",
    "append_conversation_turn",
    "create_conversation",
    "delete_conversation",
    "get_conversation",
    "list_conversations",
    "edit_material",
    "generate_material",
    "get_material",
    "list_materials",
    "material_source_evidence",
    "review_material",
    "revise_material",
    "validate_material_source_refs",
]

app = FastAPI(title="GrowWise Core", version="0.1.0a0")
app.include_router(backup_router)
app.include_router(conversation_router)
app.include_router(material_router)
app.include_router(study_router)


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
        with store.mutation_window():
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
    from growwise.api.entry import run as guarded_run

    guarded_run()


if __name__ == "__main__":
    run()
