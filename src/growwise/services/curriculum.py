from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from growwise.adapters import curriculum_records_to_resources
from growwise.curriculum import curriculum_targets_for_child
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, ResourceRecord
from growwise.generators import MaterialGenerationService


class CurriculumSearchAdapter(Protocol):
    def search(
        self,
        *,
        stage: str,
        subject: str | None = None,
        query: str | None = None,
        offline: bool = False,
    ): ...


class CurriculumGroundedMaterialService:
    """Compose public curriculum retrieval with the existing safe material generator.

    Only public query dimensions cross the adapter boundary. Curriculum records are first
    persisted as ordinary GrowWise ResourceRecord objects, then referenced through the same
    `resource:<UUID>` provenance contract used by every other material source.
    """

    def __init__(
        self,
        *,
        curriculum: CurriculumSearchAdapter,
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
        external_records = result.records if result.source == "public_curriculum" else None
        curriculum_targets = curriculum_targets_for_child(
            child,
            kind,
            external_records=external_records,
        )
        material = self.materials.generate(
            child=child,
            kind=kind,
            topic=topic,
            goal=goal,
            source_refs=refs,
            curriculum_targets_override=curriculum_targets,
        )
        return material, curriculum_resources
