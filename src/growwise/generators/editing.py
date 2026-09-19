from __future__ import annotations

from growwise.domain import GeneratedMaterial, MaterialStatus


class MaterialEditError(ValueError):
    pass


class MaterialEditService:
    """Create an immutable parent-edited child version that re-enters Parent Review."""

    def create_version(
        self,
        *,
        material: GeneratedMaterial,
        title: str,
        content_markdown: str,
        note: str | None = None,
    ) -> GeneratedMaterial:
        if material.status is MaterialStatus.ARCHIVED:
            raise MaterialEditError("archived material cannot be edited")
        normalized_title = title.strip()
        normalized_content = content_markdown.strip()
        if not normalized_title:
            raise MaterialEditError("edited material title cannot be empty")
        if not normalized_content:
            raise MaterialEditError("edited material content cannot be empty")

        curriculum_targets = [
            target.model_copy(deep=True) for target in material.curriculum_targets
        ]
        return GeneratedMaterial(
            child_id=material.child_id,
            kind=material.kind,
            title=normalized_title,
            content_markdown=normalized_content,
            parent_guide_markdown=material.parent_guide_markdown,
            status=MaterialStatus.REVIEW_PENDING,
            source_refs=list(material.source_refs),
            source_citations=[
                citation.model_copy(deep=True)
                for citation in material.source_citations
            ],
            curriculum_targets=curriculum_targets,
            generator_mode="parent_edit",
            review_note=None,
            request_topic=material.request_topic,
            request_goal=material.request_goal,
            version=material.version + 1,
            parent_material_id=material.id,
            version_note=note.strip() if note and note.strip() else None,
        )
