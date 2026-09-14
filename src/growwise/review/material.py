from __future__ import annotations

from datetime import UTC, datetime

from growwise.domain import GeneratedMaterial, MaterialStatus


class InvalidMaterialTransition(ValueError):
    pass


_ALLOWED: dict[MaterialStatus, set[MaterialStatus]] = {
    MaterialStatus.DRAFT: {MaterialStatus.REVIEW_PENDING},
    MaterialStatus.REVIEW_PENDING: {
        MaterialStatus.APPROVED,
        MaterialStatus.REVISION_REQUESTED,
        MaterialStatus.REJECTED,
    },
    MaterialStatus.REVISION_REQUESTED: {
        MaterialStatus.DRAFT,
        MaterialStatus.REVIEW_PENDING,
        MaterialStatus.REJECTED,
    },
    MaterialStatus.APPROVED: {MaterialStatus.ARCHIVED},
    MaterialStatus.REJECTED: {MaterialStatus.ARCHIVED},
    MaterialStatus.ARCHIVED: set(),
}


class MaterialReviewService:
    """Domain-level review gate. Approval cannot be bypassed by UI conventions."""

    def transition(
        self,
        material: GeneratedMaterial,
        target: MaterialStatus,
        *,
        note: str | None = None,
    ) -> GeneratedMaterial:
        allowed = _ALLOWED[material.status]
        if target not in allowed:
            raise InvalidMaterialTransition(
                f"material transition {material.status.value} -> {target.value} is not allowed"
            )
        material.status = target
        material.review_note = note
        material.updated_at = datetime.now(UTC)
        return material

    @staticmethod
    def can_export(material: GeneratedMaterial) -> bool:
        return material.status is MaterialStatus.APPROVED
