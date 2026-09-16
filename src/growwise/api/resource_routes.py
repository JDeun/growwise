"""Resource-library mutation routes with Source-of-Truth and RAG consistency."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from growwise.config import Settings
from growwise.domain import ResourceKind, ResourceRecord, Stage
from growwise.rag import HybridRagIndex, OllamaEmbeddingProvider, ResourceIngestor
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore

router = APIRouter(prefix="/resources", tags=["resources"])


class ResourceUpdateRequest(BaseModel):
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    stage_tags: list[Stage] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


@lru_cache
def get_resource_settings() -> Settings:
    return Settings()


def get_resource_store(
    settings: Annotated[Settings, Depends(get_resource_settings)],
) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_resource_rag_index() -> HybridRagIndex:
    settings = get_resource_settings()
    embedding = None
    if settings.embedding_features_enabled:
        try:
            embedding = OllamaEmbeddingProvider(
                model=settings.embedding_model_id,
                base_url=settings.model_base_url,
            )
        except Exception:
            embedding = None
    return HybridRagIndex(settings.rag_index_path, embedding=embedding)


def _resource(store: EntityStore, resource_id: UUID) -> ResourceRecord:
    payload = store.index.get_entity(str(resource_id), entity_type="resource")
    if payload is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    return ResourceRecord.model_validate(payload)


def _require_mutation_scope(
    resource: ResourceRecord,
    *,
    acting_child_id: UUID | None,
) -> None:
    """Keep child-scoped shared resources read-only outside their owning child context.

    A resource with no child_id is a parent-wide library item and remains mutable from any child
    view. A child-owned resource may be visible to siblings through CHILD_SCOPE, but visibility is
    not ownership and must not grant edit/delete rights.
    """
    if resource.child_id is None:
        return
    if acting_child_id != resource.child_id:
        raise HTTPException(status_code=403, detail="shared_resource_read_only")


@router.put("/{resource_id}", response_model=ResourceRecord)
def update_resource(
    resource_id: UUID,
    request: ResourceUpdateRequest,
    store: Annotated[EntityStore, Depends(get_resource_store)],
    acting_child_id: UUID | None = None,
) -> ResourceRecord:
    current = _resource(store, resource_id)
    _require_mutation_scope(current, acting_child_id=acting_child_id)
    updated = current.model_copy(
        update={
            **request.model_dump(),
            "updated_at": datetime.now(UTC),
        }
    )
    rag_index = get_resource_rag_index()

    # Remove old retrieval chunks before changing the authoritative record. If the SoT write fails,
    # restore the old chunks. If re-ingesting the new generation fails, retrieval remains empty for
    # this resource rather than serving stale pre-edit evidence.
    rag_index.delete_resource(str(resource_id))
    try:
        store.save(updated)
    except Exception:
        ResourceIngestor(rag_index).ingest(current)
        raise
    ResourceIngestor(rag_index).ingest(updated)
    return updated


@router.delete("/{resource_id}")
def delete_resource(
    resource_id: UUID,
    store: Annotated[EntityStore, Depends(get_resource_store)],
    acting_child_id: UUID | None = None,
) -> dict[str, bool]:
    current = _resource(store, resource_id)
    _require_mutation_scope(current, acting_child_id=acting_child_id)
    rag_index = get_resource_rag_index()
    rag_index.delete_resource(str(resource_id))
    try:
        deleted = store.delete(current)
    except Exception:
        # The Markdown source still exists when EntityStore.delete raises. Rebuild this resource's
        # RAG projection so a failed source deletion cannot silently remove it from retrieval.
        ResourceIngestor(rag_index).ingest(current)
        raise
    if not deleted:
        raise HTTPException(status_code=404, detail="resource_not_found")

    # CHILD_SCOPE and semantic backlinks are projections around the source entity. Once the source
    # is gone, remove all touching links so shared-resource visibility cannot leave dangling graph
    # records behind.
    EntityLinkService(store).delete_for_entities({str(resource_id)})
    return {"deleted": True}
