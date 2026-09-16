from __future__ import annotations

from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.storage import SQLiteProjection


def shared_source_ids(index: SQLiteProjection, child_id: str) -> set[str]:
    """Return entity IDs explicitly shared into ``child_id`` through child_scope links.

    ``child_scope`` is an authorization/visibility relation only. Callers must not interpret it as
    a semantic graph edge.
    """
    source_ids: set[str] = set()
    for payload in index.list_entities(entity_type="entity_link", child_id=child_id):
        try:
            link = EntityLink.model_validate(payload)
        except Exception:
            continue
        if link.relation is EntityLinkRelation.CHILD_SCOPE:
            source_ids.add(str(link.source_id))
    return source_ids


def entity_visible_to_child(
    index: SQLiteProjection,
    *,
    entity_id: str,
    child_id: str,
    entity_type: str | None = None,
    shared_ids: set[str] | None = None,
) -> bool:
    """Return whether an entity may be used in the given child's context."""
    payload = index.get_entity(entity_id, entity_type=entity_type)
    if payload is None:
        return False
    owner = payload.get("child_id")
    if owner is None or str(owner) == child_id:
        return True
    visible_shared_ids = shared_ids if shared_ids is not None else shared_source_ids(index, child_id)
    return entity_id in visible_shared_ids
