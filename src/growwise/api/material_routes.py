from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command

from growwise.api.contracts import (
    MaterialEditRequest,
    MaterialGenerateRequest,
    MaterialReviewRequest,
    MaterialRevisionRequest,
)
from growwise.api.dependencies import get_store
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialStatus, ResourceRecord
from growwise.generators import (
    MaterialEditError,
    MaterialEditService,
    MaterialGenerationService,
    MaterialRevisionError,
    MaterialRevisionService,
    MaterialSourceEvidence,
)
from growwise.material_versions import serialize_material_successor
from growwise.review import InvalidMaterialTransition, MaterialReviewService
from growwise.services.visibility import entity_visible_to_child, shared_source_ids
from growwise.storage import EntityStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["materials"])
_MATERIAL_SOURCE_EXCERPT_CHARS = 4_000


def _model_provider():
    # Preserve the historical direct-call seam exposed by growwise.api.main. A number of
    # integration tests and downstream callers monkeypatch that accessor explicitly.
    from growwise.api import main as api_main

    return api_main.get_model_provider()


def _material_review_graph():
    from growwise.api import main as api_main

    return api_main.get_material_review_graph()


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
    """Load bounded excerpts for already validated resource refs."""
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


@router.post("/v1/children/{child_id}/materials", response_model=GeneratedMaterial)
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
    material = MaterialGenerationService(provider=_model_provider()).generate(
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
    with store.mutation_window():
        _material_review_graph().invoke(
            {
                "material_id": str(material.id),
                "child_id": str(child.id),
                "title": material.title,
            },
            config=review_config,
        )
    return material


@router.get("/v1/children/{child_id}/materials")
def list_materials(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    return store.index.list_entities(entity_type="generated_material", child_id=str(child_id))


@router.get("/v1/materials/{material_id}", response_model=GeneratedMaterial)
def get_material(
    material_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(material_id), entity_type="generated_material")
    if payload is None:
        raise HTTPException(status_code=404, detail="material_not_found")
    return GeneratedMaterial.model_validate(payload)


@router.post("/v1/materials/{material_id}/review", response_model=GeneratedMaterial)
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
            with store.mutation_window():
                review_state = _material_review_graph().invoke(
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


@router.post("/v1/materials/{material_id}/revise", response_model=GeneratedMaterial)
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
            MaterialGenerationService(provider=_model_provider())
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
    with store.mutation_window():
        _material_review_graph().invoke(
            {
                "material_id": str(revised.id),
                "child_id": str(child.id),
                "title": revised.title,
            },
            config=review_config,
        )
    return revised


@router.post("/v1/materials/{material_id}/edit", response_model=GeneratedMaterial)
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
    with store.mutation_window():
        _material_review_graph().invoke(
            {
                "material_id": str(edited.id),
                "child_id": str(edited.child_id),
                "title": edited.title,
            },
            config={"configurable": {"thread_id": f"material-review:{edited.id}"}},
        )
    return edited
