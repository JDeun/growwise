from __future__ import annotations

from uuid import UUID, uuid5

from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.storage import EntityStore


class EntityLinkError(ValueError):
    pass


class EntityLinkService:
    """Create and query first-class entity links without copying source records."""

    def __init__(self, store: EntityStore) -> None:
        self.store = store

    def create(
        self,
        *,
        source_id: UUID,
        target_id: UUID,
        relation: EntityLinkRelation,
        label: str | None = None,
    ) -> EntityLink:
        if source_id == target_id:
            raise EntityLinkError("link_self_reference")
        if self.store.index.get_entity(str(source_id)) is None:
            raise EntityLinkError("link_source_not_found")
        target = self.store.index.get_entity(str(target_id))
        if target is None:
            raise EntityLinkError("link_target_not_found")
        child_id = target_id if relation is EntityLinkRelation.CHILD_SCOPE else None
        if (
            relation is EntityLinkRelation.CHILD_SCOPE
            and target.get("entity_type") != "child_profile"
        ):
            raise EntityLinkError("child_scope_target_must_be_child")

        existing_links = self.store.index.list_entity_links(
            source_id=str(source_id),
            target_id=str(target_id),
            relation=relation.value,
        )
        if existing_links:
            return EntityLink.model_validate(existing_links[0])

        link = EntityLink(
            id=uuid5(source_id, f"{relation.value}:{target_id}"),
            child_id=child_id,
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            label=label,
        )
        self.store.save(link)
        return link

    def share_with_children(
        self,
        *,
        source_id: UUID,
        child_ids: list[UUID],
    ) -> list[EntityLink]:
        created: list[EntityLink] = []
        for child_id in dict.fromkeys(child_ids):
            created.append(
                self.create(
                    source_id=source_id,
                    target_id=child_id,
                    relation=EntityLinkRelation.CHILD_SCOPE,
                )
            )
        return created

    def child_scope_targets(self, source_id: UUID) -> list[UUID]:
        return [
            EntityLink.model_validate(payload).target_id
            for payload in self.store.index.list_entity_links(
                source_id=str(source_id),
                relation=EntityLinkRelation.CHILD_SCOPE.value,
            )
        ]

    def backlinks(self, entity_id: UUID) -> dict[str, list[dict[str, object]]]:
        incoming: list[dict[str, object]] = []
        outgoing: list[dict[str, object]] = []
        for payload in self.store.index.list_entity_links(target_id=str(entity_id)):
            link = EntityLink.model_validate(payload)
            source = self.store.index.get_entity(str(link.source_id))
            incoming.append({"link": link.model_dump(mode="json"), "entity": source})
        for payload in self.store.index.list_entity_links(source_id=str(entity_id)):
            link = EntityLink.model_validate(payload)
            target = self.store.index.get_entity(str(link.target_id))
            outgoing.append({"link": link.model_dump(mode="json"), "entity": target})
        return {"incoming": incoming, "outgoing": outgoing}

    def delete(self, link_id: UUID) -> bool:
        payload = self.store.index.get_entity(str(link_id), entity_type="entity_link")
        if payload is None:
            return False
        return self.store.delete(EntityLink.model_validate(payload))

    def delete_for_entities(self, entity_ids: set[str]) -> int:
        deleted = 0
        for payload in self.store.index.entity_links_touching(entity_ids):
            if self.store.delete(EntityLink.model_validate(payload)):
                deleted += 1
        return deleted
