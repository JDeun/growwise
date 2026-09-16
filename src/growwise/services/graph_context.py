from __future__ import annotations

from collections.abc import Iterable

from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.storage import SQLiteProjection

_GRAPH_RELATIONS = {
    EntityLinkRelation.RELATED,
    EntityLinkRelation.DERIVED_FROM,
    EntityLinkRelation.DOCUMENTS,
    EntityLinkRelation.SUPPORTS,
}


class GraphContextExpander:
    """Expand retrieved entities by one safe document-graph hop.

    The graph is never an authorization boundary. A linked neighbor is returned only when it is
    public/unscoped, owned by the current child, or explicitly shared into the current child scope.
    ``child_scope`` itself controls visibility and is therefore excluded from semantic expansion.
    """

    def __init__(self, index: SQLiteProjection) -> None:
        self.index = index

    def expand(
        self,
        *,
        child_id: str,
        seed_ids: Iterable[str],
        limit: int = 6,
    ) -> list[dict]:
        if limit <= 0:
            return []
        seeds = {str(seed_id) for seed_id in seed_ids if seed_id}
        if not seeds:
            return []

        visible_shared_ids = self._child_scope_source_ids(child_id)
        neighbors: list[dict] = []
        seen = set(seeds)

        for payload in self.index.list_entities(entity_type="entity_link"):
            try:
                link = EntityLink.model_validate(payload)
            except Exception:
                continue
            if link.relation not in _GRAPH_RELATIONS:
                continue

            source_id = str(link.source_id)
            target_id = str(link.target_id)
            neighbor_id: str | None = None
            if source_id in seeds:
                neighbor_id = target_id
            elif target_id in seeds:
                neighbor_id = source_id
            if neighbor_id is None or neighbor_id in seen:
                continue

            neighbor = self.index.get_entity(neighbor_id)
            if neighbor is None or neighbor.get("entity_type") in {"entity_link", "child_profile"}:
                continue
            if not self._visible(
                neighbor,
                child_id=child_id,
                shared_ids=visible_shared_ids,
            ):
                continue

            neighbors.append(
                {
                    **neighbor,
                    "graph_relation": link.relation.value,
                    "graph_link_id": str(link.id),
                }
            )
            seen.add(neighbor_id)
            if len(neighbors) >= limit:
                break

        return neighbors

    def _child_scope_source_ids(self, child_id: str) -> set[str]:
        source_ids: set[str] = set()
        for payload in self.index.list_entities(
            entity_type="entity_link",
            child_id=child_id,
        ):
            try:
                link = EntityLink.model_validate(payload)
            except Exception:
                continue
            if link.relation is EntityLinkRelation.CHILD_SCOPE:
                source_ids.add(str(link.source_id))
        return source_ids

    @staticmethod
    def _visible(
        payload: dict,
        *,
        child_id: str,
        shared_ids: set[str],
    ) -> bool:
        owner = payload.get("child_id")
        if owner is None:
            return True
        if str(owner) == child_id:
            return True
        return str(payload.get("id") or "") in shared_ids
