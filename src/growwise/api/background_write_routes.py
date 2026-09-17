from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.api.background_ai import (
    queue_learning_log_enrichment,
    queue_material_enhancement,
)
from growwise.config import Settings
from growwise.domain import (
    ActivityPlan,
    ChildProfile,
    ExperienceAxis,
    GeneratedMaterial,
    LearningLog,
    MaterialKind,
    MaterialStatus,
    ResourceRecord,
)
from growwise.generators import (
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
from growwise.services.material_feedback import MaterialFeedbackService
from growwise.services.visibility import entity_visible_to_child, shared_source_ids
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph

router = APIRouter(tags=["background-writes"])
logger = logging.getLogger(__name__)
_MATERIAL_SOURCE_EXCERPT_CHARS = 4_000


class BackgroundObservationRequest(BaseModel):
    child_id: UUID
    observation: str = Field(min_length=1, max_length=10_000)
    experience_axes: list[ExperienceAxis] = Field(default_factory=list)
    activity_plan_id: UUID | None = None


class BackgroundMaterialRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    source_refs: list[str] = Field(default_factory=list)


class BackgroundRevisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


@lru_cache
def get_background_write_settings() -> Settings:
    return Settings()


def get_background_write_store(
    settings: Annotated[Settings, Depends(get_background_write_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_background_idempotency_store() -> SQLiteIdempotencyStore:
    return SQLiteIdempotencyStore(get_background_write_settings().idempotency_path)


@lru_cache
def get_background_material_review_graph():
    settings = get_background_write_settings()
    try:
        settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        return build_material_review_graph(checkpointer=checkpointer)
    except Exception:
        logger.exception(
            "background material checkpoint unavailable; using rebuildable in-memory projection"
        )
        return build_material_review_graph(checkpointer=None)


def _validate_activity_link(
    *, store: EntityStore, child_id: UUID, activity_plan_id: UUID | None
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


def _validate_source_refs(
    *, child_id: UUID, source_refs: list[str], store: EntityStore
) -> list[str]:
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


def _source_evidence(
    *, source_refs: list[str], store: EntityStore
) -> list[MaterialSourceEvidence]:
    evidence: list[MaterialSourceEvidence] = []
    for ref in source_refs:
        payload = store.index.get_entity(ref.removeprefix("resource:"), entity_type="resource")
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
        evidence.append(
            MaterialSourceEvidence(
                source_ref=ref,
                title=resource.title,
                excerpt="\n\n".join(parts)[:_MATERIAL_SOURCE_EXCERPT_CHARS],
            )
        )
    return evidence


def _init_review(material: GeneratedMaterial) -> None:
    try:
        get_background_material_review_graph().invoke(
            {
                "material_id": str(material.id),
                "child_id": str(material.child_id),
                "title": material.title,
            },
            config={"configurable": {"thread_id": f"material-review:{material.id}"}},
        )
    except Exception:
        # Review checkpoints are rebuildable workflow projections. The material Markdown record is
        # authoritative and must not look failed after it has already been committed.
        logger.exception("material review projection initialization failed for %s", material.id)


@router.post("/observations/background", response_model=LearningLog)
def create_observation_background(
    request: BackgroundObservationRequest,
    store: Annotated[EntityStore, Depends(get_background_write_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> LearningLog:
    _validate_activity_link(
        store=store,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
    )
    normalized = " ".join(request.observation.split())
    if not normalized:
        raise HTTPException(status_code=422, detail="empty_observation")

    idempotency_store = get_background_idempotency_store()
    request_hash = request_fingerprint(request.model_dump(mode="json"))
    reserved_log_id = uuid7()
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

    log = LearningLog(
        id=reserved_log_id,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
        parent_observation=request.observation,
        experience_axes=list(request.experience_axes),
    )
    try:
        store.save(log)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
    except Exception:
        if claim is not None and claim.acquired:
            idempotency_store.release(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        raise

    queue_learning_log_enrichment(log=log, store=store)
    return log


@router.post(
    "/children/{child_id}/materials/background",
    response_model=GeneratedMaterial,
)
def generate_material_background(
    child_id: UUID,
    request: BackgroundMaterialRequest,
    store: Annotated[EntityStore, Depends(get_background_write_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> GeneratedMaterial:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(child_payload)
    source_refs = _validate_source_refs(
        child_id=child.id,
        source_refs=request.source_refs,
        store=store,
    )
    evidence = _source_evidence(source_refs=source_refs, store=store)
    feedback = MaterialFeedbackService(store.index).snapshot(child_id=str(child.id))

    idempotency_store = get_background_idempotency_store()
    request_hash = request_fingerprint(
        {"child_id": str(child_id), **request.model_dump(mode="json")}
    )
    reserved_material_id = uuid7()
    claim = None
    if idempotency_key is not None:
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="generated_material",
                resource_id=str(reserved_material_id),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reserved_material_id = UUID(claim.record.resource_id)
        if not claim.acquired:
            existing = store.index.get_entity(
                claim.record.resource_id, entity_type="generated_material"
            )
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return GeneratedMaterial.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    try:
        # Always return a complete deterministic draft immediately. The public goal is the only goal
        # rendered in the learner-facing sheet. Closed-loop continuity is private generation guidance
        # for the background model and a local parent-guide block; raw feedback is never sent to the
        # model and internal guidance is never printed as learner metadata.
        material = MaterialGenerationService(provider=None).generate(
            child=child,
            kind=request.kind,
            topic=request.topic,
            goal=request.goal,
            generation_guidance=feedback.generation_guidance(),
            source_refs=source_refs,
            source_evidence=evidence,
        ).model_copy(update={"id": reserved_material_id})
        material.request_topic = request.topic
        material.request_goal = request.goal
        material.parent_guide_markdown = feedback.with_parent_guide(material.parent_guide_markdown)
        store.save(material)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
    except Exception:
        if claim is not None and claim.acquired:
            idempotency_store.release(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        raise

    _init_review(material)
    queue_material_enhancement(material=material, store=store)
    return material


@router.post(
    "/materials/{material_id}/revise-background",
    response_model=GeneratedMaterial,
)
@serialize_material_successor
def revise_material_background(
    material_id: UUID,
    request: BackgroundRevisionRequest,
    store: Annotated[EntityStore, Depends(get_background_write_store)],
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

    feedback = MaterialFeedbackService(store.index).snapshot(child_id=str(material.child_id))
    try:
        revised = MaterialRevisionService(MaterialGenerationService(provider=None)).revise(
            material=material,
            child=child,
            note=request.note,
            source_evidence=_source_evidence(source_refs=material.source_refs, store=store),
            generation_guidance=feedback.generation_guidance(),
        )
    except MaterialRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    revised.parent_guide_markdown = feedback.with_parent_guide(revised.parent_guide_markdown)
    store.save(revised)
    _init_review(revised)
    queue_material_enhancement(material=revised, store=store)
    return revised
