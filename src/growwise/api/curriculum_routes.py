from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.api.curriculum import generate_curriculum_grounded_material
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind
from growwise.domain.models import SourceRef
from growwise.generators import MaterialGenerationService
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.maintenance import DATA_MAINTENANCE
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.storage import EntityStore

router = APIRouter(tags=["curriculum"])


class CurriculumMaterialRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    subject: str | None = Field(default=None, max_length=100)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=100)


@lru_cache
def get_curriculum_settings() -> Settings:
    return Settings()


def get_curriculum_store(
    settings: Annotated[Settings, Depends(get_curriculum_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache(maxsize=4)
def _get_curriculum_rag_index(generation: int) -> HybridRagIndex:
    del generation
    return HybridRagIndex(get_curriculum_settings().rag_index_path)


def get_curriculum_rag_index() -> HybridRagIndex:
    generation = DATA_MAINTENANCE.generation
    with DATA_MAINTENANCE.mutation(expected_generation=generation):
        return _get_curriculum_rag_index(generation)


get_curriculum_rag_index.cache_clear = _get_curriculum_rag_index.cache_clear  # type: ignore[attr-defined]


@router.post(
    "/children/{child_id}/materials/curriculum",
    response_model=GeneratedMaterial,
)
def generate_curriculum_material(
    child_id: UUID,
    request: CurriculumMaterialRequest,
    settings: Annotated[Settings, Depends(get_curriculum_settings)],
    store: Annotated[EntityStore, Depends(get_curriculum_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(payload)

    idempotency_store = (
        SQLiteIdempotencyStore(settings.idempotency_path)
        if idempotency_key is not None
        else None
    )
    request_hash = request_fingerprint(
        {"child_id": str(child_id), **request.model_dump(mode="json")}
    )
    reserved_material_id: UUID = uuid7()
    claim = None
    if idempotency_key is not None:
        assert idempotency_store is not None
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
                claim.record.resource_id,
                entity_type="generated_material",
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
        material = generate_curriculum_grounded_material(
            settings=settings,
            store=store,
            ingestor=ResourceIngestor(get_curriculum_rag_index()),
            child=child,
            kind=request.kind,
            topic=request.topic,
            goal=request.goal,
            subject=request.subject,
            source_refs=request.source_refs,
            materials=MaterialGenerationService(),
        )
        material.id = reserved_material_id
        store.save(material)
        if claim is not None and claim.acquired:
            assert idempotency_store is not None
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return material
    except ValueError as exc:
        if claim is not None and claim.acquired:
            assert idempotency_store is not None
            existing = store.index.get_entity(
                claim.record.resource_id,
                entity_type="generated_material",
            )
            if existing is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise
    except Exception:
        if claim is not None and claim.acquired:
            assert idempotency_store is not None
            existing = store.index.get_entity(
                claim.record.resource_id,
                entity_type="generated_material",
            )
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
