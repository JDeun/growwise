from __future__ import annotations

import sqlite3
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field

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
from growwise.material_versions import serialize_material_successor
from growwise.services.visibility import entity_visible_to_child, shared_source_ids
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph

router = APIRouter(tags=["background-writes"])
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
def get_background_material_review_graph():
    settings = get_background_write_settings()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_material_review_graph(checkpointer=checkpointer)


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
    get_background_material_review_graph().invoke(
        {
            "material_id": str(material.id),
            "child_id": str(material.child_id),
            "title": material.title,
        },
        config={"configurable": {"thread_id": f"material-review:{material.id}"}},
    )


@router.post("/observations/background", response_model=LearningLog)
def create_observation_background(
    request: BackgroundObservationRequest,
    store: Annotated[EntityStore, Depends(get_background_write_store)],
) -> LearningLog:
    _validate_activity_link(
        store=store,
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
    )
    normalized = " ".join(request.observation.split())
    if not normalized:
        raise HTTPException(status_code=422, detail="empty_observation")

    log = LearningLog(
        child_id=request.child_id,
        activity_plan_id=request.activity_plan_id,
        parent_observation=request.observation,
        experience_axes=list(request.experience_axes),
    )
    store.save(log)
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

    # Always return a complete deterministic draft immediately. Slow model personalization and
    # parent-guide refinement happen later against this same stable material ID.
    material = MaterialGenerationService(provider=None).generate(
        child=child,
        kind=request.kind,
        topic=request.topic,
        goal=request.goal,
        source_refs=source_refs,
        source_evidence=evidence,
    )
    material.request_topic = request.topic
    material.request_goal = request.goal
    store.save(material)
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

    try:
        revised = MaterialRevisionService(MaterialGenerationService(provider=None)).revise(
            material=material,
            child=child,
            note=request.note,
            source_evidence=_source_evidence(source_refs=material.source_refs, store=store),
        )
    except MaterialRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    store.save(revised)
    _init_review(revised)
    queue_material_enhancement(material=revised, store=store)
    return revised