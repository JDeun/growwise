from __future__ import annotations

import logging

from growwise.domain import ResourceRecord

from .chunking import chunk_resource
from .index import HybridRagIndex

logger = logging.getLogger(__name__)


class ResourceIngestor:
    """Project authoritative ResourceRecord data into the rebuildable RAG index.

    RAG is deliberately downstream of the Markdown source-of-truth. Projection failure therefore
    must not turn an already-committed resource mutation into a logical failure that a caller might
    retry with a new identifier. Failures are logged and the resource remains recoverable from the
    authoritative library; startup/backup rebuild paths can repopulate retrieval later.
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
