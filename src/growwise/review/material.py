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
        if target is not MaterialStatus.ARCHIVED or note is not None:
            material.review_note = note
        material.updated_at = datetime.now(UTC)
        if target in {
            MaterialStatus.APPROVED, MaterialStatus.REJECTED, MaterialStatus.REVISION_REQUESTED,
        }:
            material.reviewed_at = material.updated_at
            material.review_decision = target.value
        return material

    def approve_for_use(
        self,
        material: GeneratedMaterial,
        *,
        note: str | None = None,
    ) -> GeneratedMaterial:
        """Apply one explicit parent 'use this' decision through the existing state machine."""
        if material.status is MaterialStatus.APPROVED:
            return material
        if material.status is MaterialStatus.DRAFT:
            self.transition(material, MaterialStatus.REVIEW_PENDING)
        if material.status is MaterialStatus.REVISION_REQUESTED:
            self.transition(material, MaterialStatus.REVIEW_PENDING)
        if material.status is not MaterialStatus.REVIEW_PENDING:
            raise InvalidMaterialTransition(
                f"material status {material.status.value} cannot be approved for use"
            )
        return self.transition(material, MaterialStatus.APPROVED, note=note)

    @staticmethod
    def can_export(material: GeneratedMaterial) -> bool:
        return material.status is MaterialStatus.APPROVED
