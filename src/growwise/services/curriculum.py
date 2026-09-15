from __future__ import annotations

from growwise.adapters import PublicCurriculumAdapter, curriculum_records_to_resources, curriculum_refs
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, ResourceRecord
from growwise.generators import MaterialGenerationService


class CurriculumGroundedMaterialService:
    """Compose public curriculum retrieval with the existing safe material generator.

    Only public query dimensions cross the adapter boundary. The child profile remains local
    and is used by MaterialGenerationService after curriculum retrieval has completed.
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
    ) -> tuple[GeneratedMaterial, list[ResourceRecord]]:
        result = self.curriculum.search(
            stage=child.stage.value,
            subject=subject,
            query=topic,
            offline=offline,
        )
        curriculum_resources = curriculum_records_to_resources(result)
        refs = list(dict.fromkeys([*(source_refs or []), *curriculum_refs(result)]))
        material = self.materials.generate(
            child=child,
            kind=kind,
            topic=topic,
            goal=goal,
            source_refs=refs,
        )
        return material, curriculum_resources
