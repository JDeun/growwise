"""Read bounded sets of current, child-visible sources before model dispatch."""

from contextlib import ExitStack
from uuid import UUID

from growwise.maintenance import DATA_MAINTENANCE
from growwise.storage import SQLiteProjection


def current_source_payloads(
    index: SQLiteProjection, *, entity_ids: list[str], child_id: str | None,
) -> dict[str, dict]:
    # Import at call time: the public rag package is also imported by services.__init__.
    from growwise.services.entity_lock import entity_operation_lock
    from growwise.services.learning_wiki import (
        _MAX_SOURCES,
        _SOURCE_ENTITY_TYPES,
        LearningWikiService,
    )

    identifiers = set()
    for raw_identifier in entity_ids:
        try:
            identifiers.add(UUID(raw_identifier))
        except (ValueError, TypeError, AttributeError):
            continue
    requested = identifiers.copy()
    wiki_sources: dict[str, list[tuple[str, str]]] = {}
    for identifier in requested:
        wiki = index.get_current_entity(str(identifier), entity_type="learning_wiki")
        if wiki is None:
            continue
        refs = wiki.get("source_refs")
        if not isinstance(refs, list) or len(refs) > _MAX_SOURCES:
            continue
        parsed = []
        try:
            for ref in refs:
                kind, raw_id = ref.split(":", 1)
                source_id = UUID(raw_id)
                if kind not in _SOURCE_ENTITY_TYPES:
                    raise ValueError("unsupported Wiki source")
                parsed.append((kind, str(source_id)))
            if len(set(parsed)) != len(parsed):
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        wiki_sources[str(identifier)] = parsed
        identifiers.update(UUID(source_id) for _kind, source_id in parsed)
    # Lock stripes in a stable order, matching mutation order (maintenance -> entity -> path).
    # Release the entire snapshot before network/model work; an in-flight request is authorized
    # at this snapshot, and a later edit/delete applies to subsequent requests.
    locks = {id(lock): lock for identifier in identifiers
             for lock in [entity_operation_lock(identifier)]}
    with DATA_MAINTENANCE.mutation(), ExitStack() as stack:
        for lock_key in sorted(locks):
            stack.enter_context(locks[lock_key])
        if child_id is not None and index.get_current_entity(
            child_id, entity_type="child_profile",
        ) is None:
            return {}
        visible: dict[str, dict] = {}
        for entity_uuid in sorted(identifiers):
            key = str(entity_uuid)
            payload = index.get_current_entity(key)
            if payload is None:
                continue
            owner = payload.get("child_id")
            allowed = owner is None and payload.get("entity_type") == "resource"
            if child_id is not None:
                allowed = allowed or str(owner) == child_id
                if not allowed:
                    # The link index is a candidate list too: deleted/revoked raw grants cannot
                    # authorize evidence just because their disposable projection survived.
                    for candidate in index.list_entity_links(
                        source_id=key, target_id=child_id, relation="child_scope",
                    ):
                        grant = index.get_current_entity(str(candidate["id"]),
                                                         entity_type="entity_link")
                        if grant and all((grant.get("relation") == "child_scope",
                                          str(grant.get("source_id")) == key,
                                          str(grant.get("target_id")) == child_id,
                                          str(grant.get("child_id")) == child_id)):
                            allowed = True
                            break
            if allowed and not (payload.get("entity_type") == "photo_activity_record"
                                and payload.get("status") != "committed"):
                visible[key] = payload
        for key, payload in list(visible.items()):
            if payload.get("entity_type") != "learning_wiki":
                continue
            refs = wiki_sources.get(key)
            # A current derived file can still quote deleted, edited or revoked originals.
            # Lock all declared originals above, and discard a Wiki changed during lock setup.
            if refs is None or payload.get("source_refs") != [
                f"{kind}:{source_id}" for kind, source_id in refs
            ]:
                visible.pop(key)
                continue
            sources = [visible[source_id] for _kind, source_id in refs if source_id in visible]
            if (len(sources) != len(refs)
                    or any(source.get("entity_type") != kind
                           for (kind, _source_id), source in zip(refs, sources, strict=True))
                    or LearningWikiService._fingerprint(sources)
                    != payload.get("source_fingerprint")):
                visible.pop(key)
        return {str(identifier): visible[str(identifier)] for identifier in requested
                if str(identifier) in visible}


def current_rag_hits(index: SQLiteProjection, *, hits: list[dict],
                     child_id: str | None) -> list[dict]:
    """Use RAG only for candidate IDs/ranking; compose current source text, never cached text."""
    payloads = current_source_payloads(
        index, entity_ids=[str(hit.get("resource_id") or "") for hit in hits], child_id=child_id,
    )
    return rag_hits_from_payloads(hits, payloads)


def rag_hits_from_payloads(hits: list[dict], payloads: dict[str, dict]) -> list[dict]:
    result = []
    seen: set[str] = set()
    for hit in hits:
        identifier = str(hit.get("resource_id") or "")
        payload = payloads.get(identifier)
        if (payload is None or identifier in seen
                or payload.get("entity_type") not in {"resource", "learning_wiki"}):
            continue
        title = str(payload.get("title") or "저장된 자료")[:500]
        remaining = 12_000
        parts = []
        for field in ("summary", "content", "content_markdown"):
            value = payload.get(field)
            if isinstance(value, str) and value.strip() and remaining > 0:
                part = value.strip()[:remaining]
                parts.append(part)
                remaining -= len(part) + 2
        result.append({"chunk_id": hit["chunk_id"], "resource_id": identifier,
                       "title": title, "text": "\n\n".join(parts)[:12_000]})
        seen.add(identifier)
    return result
