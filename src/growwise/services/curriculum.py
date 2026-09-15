from __future__ import annotations

from collections.abc import Callable

from growwise.adapters import PublicCurriculumAdapter, curriculum_records_to_resources
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, ResourceRecord
from growwise.generators import MaterialGenerationService


class CurriculumGroundedMaterialService:
    """Compose public curriculum retrieval with the existing safe material generator.

    Only public query dimensions cross the adapter boundary. Curriculum records are first
    persisted as ordinary GrowWise ResourceRecord objects, then referenced through the same
    `resource:<UUID>` provenance contract used by every other material source.
    """

    def __init__(
        self,
        *,
        curriculum: PublicCurriculumAdapter,
        materials: MaterialGenerationService,
    ) -> None:
        self.curriculum = curriculum
        self.materials = materials

    def generate(
        self,
        *,
        child: ChildProfile,
        kind: MaterialKind,
        topic: str,
        goal: str | None = None,
        subject: str | None = None,
        source_refs: list[str] | None = None,
        offline: bool = False,
        persist_resource: Callable[[ResourceRecord], None] | None = None,
    ) -> tuple[GeneratedMaterial, list[ResourceRecord]]:
        result = self.curriculum.search(
            stage=child.stage.value,
            subject=subject,
            query=topic,
            offline=offline,
        )
        curriculum_resources = curriculum_records_to_resources(result)
        if persist_resource is not None:
            for resource in curriculum_resources:
                persist_resource(resource)
        curriculum_source_refs = [f"resource:{resource.id}" for resource in curriculum_resources]
        refs = list(dict.fromkeys([*(source_refs or []), *curriculum_source_refs]))
        material = self.materials.generate(
            child=child,
            kind=kind,
            topic=topic,
            goal=goal,
            source_refs=refs,
        )
        return material, curriculum_resources
