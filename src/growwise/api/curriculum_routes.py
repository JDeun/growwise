from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from growwise.api.curriculum import generate_curriculum_grounded_material
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind
from growwise.generators import MaterialGenerationService
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.storage import EntityStore


class CurriculumMaterialRequest(BaseModel):
    kind: MaterialKind = MaterialKind.ACTIVITY_GUIDE
    topic: str = Field(min_length=1, max_length=500)
    goal: str | None = Field(default=None, max_length=1000)
    subject: str | None = Field(default=None, max_length=100)
    source_refs: list[str] = Field(default_factory=list)


def build_curriculum_router(
    *,
    settings: Settings,
    store: EntityStore,
    rag_index: HybridRagIndex,
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["curriculum"])
    ingestor = ResourceIngestor(rag_index)

    @router.post(
        "/children/{child_id}/materials/curriculum",
        response_model=GeneratedMaterial,
    )
    def generate(
        child_id: UUID,
        request: CurriculumMaterialRequest,
    ) -> GeneratedMaterial:
        payload = store.index.get_entity(str(child_id), entity_type="child_profile")
        if payload is None:
            raise HTTPException(status_code=404, detail="child_not_found")
        child = ChildProfile.model_validate(payload)
        try:
            material = generate_curriculum_grounded_material(
                settings=settings,
                store=store,
                ingestor=ingestor,
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

    return router
