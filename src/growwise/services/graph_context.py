from __future__ import annotations

from collections.abc import Iterable

from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.storage import SQLiteProjection

from .visibility import entity_visible_to_child, shared_source_ids

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

    Semantic links remain traversable from either endpoint for retrieval, but every returned
    neighbor records whether traversal followed the stored source->target direction (``outgoing``)
    or walked back from target->source (``incoming``). This keeps directional relations such as
    ``derived_from``, ``documents``, and ``supports`` interpretable by downstream context builders.
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

        visible_shared_ids = self.shared_source_ids(child_id)
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
            direction: str | None = None
            if source_id in seeds:
                neighbor_id = target_id
                direction = "outgoing"
            elif target_id in seeds:
                neighbor_id = source_id
                direction = "incoming"
            if neighbor_id is None or direction is None or neighbor_id in seen:
                continue

            neighbor = self.index.get_entity(neighbor_id)
            if neighbor is None or neighbor.get("entity_type") in {"entity_link", "child_profile"}:
                continue
            if not entity_visible_to_child(
                self.index,
                entity_id=neighbor_id,
                child_id=child_id,
                shared_ids=visible_shared_ids,
            ):
                continue

            neighbors.append(
                {
                    **neighbor,
                    "graph_relation": link.relation.value,
                    "graph_direction": direction,
                    "graph_source_id": source_id,
                    "graph_target_id": target_id,
                    "graph_link_id": str(link.id),
                }
            )
            seen.add(neighbor_id)
            if len(neighbors) >= limit:
                break

        return neighbors

    def shared_source_ids(self, child_id: str) -> set[str]:
        return shared_source_ids(self.index, child_id)
