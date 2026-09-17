from __future__ import annotations

import logging

from growwise.domain import ResourceRecord

from .chunking import chunk_resource
from .index import HybridRagIndex

logger = logging.getLogger(__name__)


class ResourceIngestor:
    """Project authoritative ResourceRecord data into the rebuildable RAG index.

    Markdown is the source-of-truth. A retrieval projection failure must therefore not turn an
    already-committed resource mutation into an apparent logical failure that a caller can retry
    with a fresh identifier. Projection failures are logged and may be repaired by rebuild paths.
    """

    def __init__(self, index: HybridRagIndex) -> None:
        self.index = index

    def ingest(self, resource: ResourceRecord, *, strict: bool = False) -> int:
        body_parts = [resource.title]
        if resource.summary:
            body_parts.append(resource.summary)
        if resource.content:
            body_parts.append(resource.content)
        text = "\n\n".join(part.strip() for part in body_parts if part and part.strip())
        chunks = chunk_resource(
            resource_id=str(resource.id),
            child_id=str(resource.child_id) if resource.child_id else None,
            title=resource.title,
            text=text,
            source_url=resource.source_url,
            source_name=resource.source_name,
            tags=resource.tags,
            recorded_at=resource.created_at.isoformat(),
        )
        try:
            return self.index.replace_resource(chunks)
        except Exception:
            logger.exception(
                "RAG projection update failed for resource %s; source record remains authoritative",
                resource.id,
            )
            if strict:
                raise
            return 0
