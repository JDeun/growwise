from __future__ import annotations

from growwise.domain import ChildProfile, GeneratedMaterial, MaterialStatus

from .material import MaterialGenerationService


class MaterialRevisionError(ValueError):
    pass


class MaterialRevisionService:
    """Create a new reviewable material version from a parent revision request."""

    def __init__(self, generation: MaterialGenerationService) -> None:
        self.generation = generation

    def revise(
        self,
        *,
        material: GeneratedMaterial,
        child: ChildProfile,
        note: str | None = None,
    ) -> GeneratedMaterial:
        if material.status is not MaterialStatus.REVISION_REQUESTED:
            raise MaterialRevisionError(
                "material must be revision_requested before regeneration"
            )
        revision_note = (
            note or material.review_note or "부모 수정 요청을 반영해 다시 구성한다."
        ).strip()
        topic = material.request_topic or material.title
        previous_goal = material.request_goal or ""
        goal = "\n".join(
            part
            for part in (
                previous_goal.strip(),
                f"부모 수정 요청: {revision_note}",
            )
            if part
        )
        revised = self.generation.generate(
            child=child,
            kind=material.kind,
            topic=topic,
            goal=goal,
            source_refs=material.source_refs,
        )
        revised.title = material.title
        revised.version = material.version + 1
        revised.parent_material_id = material.id
        revised.request_topic = topic
        revised.request_goal = goal
        return revised
