from __future__ import annotations

from uuid6 import uuid7

from growwise.domain import GeneratedMaterial, MaterialKind, MaterialStatus
from growwise.generators import MaterialEditService


def test_parent_edit_preserves_existing_parent_guide() -> None:
    material = GeneratedMaterial(
        child_id=uuid7(),
        kind=MaterialKind.ACTIVITY_GUIDE,
        title="원본",
        content_markdown="# 아이용 자료",
        parent_guide_markdown="# 부모용 교안\n진행 안내",
        status=MaterialStatus.APPROVED,
    )

    edited = MaterialEditService().create_version(
        material=material,
        title="수정본",
        content_markdown="# 아이용 자료 수정",
        note="문장을 간결하게 수정",
    )

    assert edited.parent_guide_markdown == material.parent_guide_markdown
    assert edited.parent_material_id == material.id
    assert edited.version == material.version + 1
    assert edited.status is MaterialStatus.REVIEW_PENDING
