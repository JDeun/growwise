from __future__ import annotations

from growwise.adapters import PublicCurriculumAdapter, SQLiteExternalCache
from growwise.config import Settings
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, ResourceRecord
from growwise.generators import MaterialGenerationService
from growwise.rag import ResourceIngestor
from growwise.services import CurriculumGroundedMaterialService
from growwise.storage import EntityStore


def generate_curriculum_grounded_material(
    *,
    settings: Settings,
    store: EntityStore,
    ingestor: ResourceIngestor,
    child: ChildProfile,
    kind: MaterialKind,
    topic: str,
    goal: str | None,
    subject: str | None,
    source_refs: list[str],
    materials: MaterialGenerationService,
) -> GeneratedMaterial:
    """Generate material grounded in public curriculum resources."""
    if not settings.curriculum_endpoint:
        raise ValueError("curriculum_endpoint_not_configured")

    curriculum = PublicCurriculumAdapter(
        endpoint=settings.curriculum_endpoint,
        cache=SQLiteExternalCache(settings.external_cache_path),
        ttl_seconds=settings.curriculum_cache_ttl_seconds,
    )
    service = CurriculumGroundedMaterialService(
        curriculum=curriculum,
        materials=materials,
    )

    def persist(resource: ResourceRecord) -> None:
        store.save(resource)
        ingestor.ingest(resource)

    material, _resources = service.generate(
        child=child,
        kind=kind,
        topic=topic,
        goal=goal,
        subject=subject,
        source_refs=source_refs,
        persist_resource=persist,
    )
    return material
