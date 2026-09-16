from __future__ import annotations

from uuid import UUID

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

        for existing in self._all_links():
            if (
                existing.source_id == source_id
                and existing.target_id == target_id
                and existing.relation is relation
            ):
                return existing

        link = EntityLink(
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
            link.target_id
            for link in self._all_links()
            if link.source_id == source_id and link.relation is EntityLinkRelation.CHILD_SCOPE
        ]

    def backlinks(self, entity_id: UUID) -> dict[str, list[dict[str, object]]]:
        incoming: list[dict[str, object]] = []
        outgoing: list[dict[str, object]] = []
        for link in self._all_links():
            payload = link.model_dump(mode="json")
            if link.target_id == entity_id:
                source = self.store.index.get_entity(str(link.source_id))
                incoming.append({"link": payload, "entity": source})
            if link.source_id == entity_id:
                target = self.store.index.get_entity(str(link.target_id))
                outgoing.append({"link": payload, "entity": target})
        return {"incoming": incoming, "outgoing": outgoing}

    def delete(self, link_id: UUID) -> bool:
        payload = self.store.index.get_entity(str(link_id), entity_type="entity_link")
        if payload is None:
            return False
        return self.store.delete(EntityLink.model_validate(payload))

    def delete_for_entities(self, entity_ids: set[str]) -> int:
        deleted = 0
        for link in self._all_links():
            touches_entity = str(link.source_id) in entity_ids or str(link.target_id) in entity_ids
            if touches_entity and self.store.delete(link):
                deleted += 1
        return deleted

    def _all_links(self) -> list[EntityLink]:
        return [
            EntityLink.model_validate(payload)
            for payload in self.store.index.list_entities(entity_type="entity_link")
        ]
