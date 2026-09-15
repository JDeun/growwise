from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.api.curriculum import generate_curriculum_grounded_material
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind
from growwise.generators import MaterialGenerationService
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.storage import EntityStore

router = APIRouter(prefix="/v1", tags=["curriculum"])


class CurriculumMaterialRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    subject: str | None = Field(default=None, max_length=100)
    source_refs: list[str] = Field(default_factory=list)


@lru_cache
def get_curriculum_settings() -> Settings:
    return Settings()


def get_curriculum_store(
    settings: Annotated[Settings, Depends(get_curriculum_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_curriculum_rag_index() -> HybridRagIndex:
    return HybridRagIndex(get_curriculum_settings().rag_index_path)


@router.post(
    "/children/{child_id}/materials/curriculum",
    response_model=GeneratedMaterial,
)
def generate_curriculum_material(
    child_id: UUID,
    request: CurriculumMaterialRequest,
    settings: Annotated[Settings, Depends(get_curriculum_settings)],
    store: Annotated[EntityStore, Depends(get_curriculum_store)],
) -> GeneratedMaterial:
    payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    child = ChildProfile.model_validate(payload)
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
    except ValueError as exc:
        if str(exc) == "curriculum_endpoint_not_configured":
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise
    store.save(material)
    return material
