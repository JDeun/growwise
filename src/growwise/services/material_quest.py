from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from growwise.domain.links import EntityLinkRelation
from growwise.domain.models import ActivityPlan, ExperienceAxis, GeneratedMaterial, MaterialStatus
from growwise.services.child_lock import child_operation_lock
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore


def material_quest_ref(material_id: UUID) -> str:
    return f"material:{material_id}"


def material_quests(store: EntityStore, material: GeneratedMaterial) -> list[ActivityPlan]:
    ref = material_quest_ref(material.id)
    quests = [
        ActivityPlan.model_validate(payload)
        for payload in store.index.list_entities(
            entity_type="activity_plan",
            child_id=str(material.child_id),
        )
        if ref in payload.get("source_refs", [])
    ]
    quests.sort(key=lambda item: (item.created_at, str(item.id)))
    return quests


def ensure_material_quest(
    *,
    store: EntityStore,
    material: GeneratedMaterial,
    experience_axes: Iterable[ExperienceAxis] = (),
) -> ActivityPlan:
    """Return the single canonical quest for an approved generated material.

    Approval is the moment a printable material becomes actionable work. The material UUID is the
    stable idempotency key: repeated approval retries, history reads, or result submissions reuse
    the same ActivityPlan instead of creating another quest card. Older approved materials that
    predate this invariant self-heal on first use.
    """
    if material.status is not MaterialStatus.APPROVED:
        raise ValueError("material_must_be_approved_before_quest")

    child_id = str(material.child_id)
    with child_operation_lock(child_id):
        if store.index.get_entity(child_id, entity_type="child_profile") is None:
            raise KeyError("material_child_not_found")

        existing = material_quests(store, material)
        if existing:
            quest = existing[0]
        else:
            quest = ActivityPlan(
                child_id=material.child_id,
                title=material.title,
                description="GrowWise에서 승인한 교육자료를 실제로 수행하는 Quest",
                source_refs=[material_quest_ref(material.id)],
                experience_axes=list(dict.fromkeys(experience_axes)),
            )
            store.save(quest)

        merged_axes = list(dict.fromkeys([*quest.experience_axes, *experience_axes]))
        if merged_axes != quest.experience_axes:
            quest.experience_axes = merged_axes
            store.save(quest)

        EntityLinkService(store).create(
            source_id=material.id,
            target_id=quest.id,
            relation=EntityLinkRelation.SUPPORTS,
            label="이 생성 자료로 수행할 Quest",
        )
        return quest
