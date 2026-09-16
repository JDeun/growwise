"""Resource-library mutation routes with Source-of-Truth and RAG consistency."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.config import Settings
from growwise.domain import ResourceKind, ResourceRecord, Stage
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    SQLiteIdempotencyStore,
    request_fingerprint,
)
from growwise.rag import HybridRagIndex, OllamaEmbeddingProvider, ResourceIngestor
from growwise.storage import EntityStore

router = APIRouter(prefix="/resources", tags=["resources"])


class ResourceCreateRequest(BaseModel):
    kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    child_id: UUID | None = None
    summary: str | None = None
    content: str | None = None
    source_url: str | None = None
    source_name: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    stage_tags: list[Stage] = Field(default_factory=list)
    provenance: dict[str, str] = Field(default_factory=dict)


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


@lru_cache
def get_resource_idempotency_store() -> SQLiteIdempotencyStore:
    return SQLiteIdempotencyStore(get_resource_settings().idempotency_path)


def _resource(store: EntityStore, resource_id: UUID) -> ResourceRecord:
    payload = store.index.get_entity(str(resource_id), entity_type="resource")
    if payload is None:
        raise HTTPException(status_code=404, detail="resource_not_found")
    return ResourceRecord.model_validate(payload)


@router.post("", response_model=ResourceRecord)
def create_resource(
    request: ResourceCreateRequest,
    store: Annotated[EntityStore, Depends(get_resource_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> ResourceRecord:
    if request.child_id is not None and store.index.get_entity(
        str(request.child_id), entity_type="child_profile"
    ) is None:
        raise HTTPException(status_code=404, detail="child_not_found")

    idempotency_store = get_resource_idempotency_store()
    request_hash = request_fingerprint(request.model_dump(mode="json"))
    reserved_resource_id = uuid7()
    claim = None
    if idempotency_key is not None:
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="resource",
                resource_id=str(reserved_resource_id),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reserved_resource_id = UUID(claim.record.resource_id)
        if not claim.acquired:
            existing = store.index.get_entity(claim.record.resource_id, entity_type="resource")
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return ResourceRecord.model_validate(existing)
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    resource = ResourceRecord(id=reserved_resource_id, **request.model_dump())
    try:
        store.save(resource)
        ResourceIngestor(get_resource_rag_index()).ingest(resource)
        if claim is not None and claim.acquired:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return resource
    except Exception:
        if claim is not None and claim.acquired:
            # release() expires the lease but intentionally preserves the reserved UUID.
            idempotency_store.release(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        raise


@router.put("/{resource_id}", response_model=ResourceRecord)
def update_resource(
    resource_id: UUID,
    request: ResourceUpdateRequest,
    store: Annotated[EntityStore, Depends(get_resource_store)],
) -> ResourceRecord:
    current = _resource(store, resource_id)
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
) -> dict[str, bool]:
    current = _resource(store, resource_id)
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
    return {"deleted": True}
