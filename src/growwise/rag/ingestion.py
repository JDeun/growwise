from __future__ import annotations

from growwise.domain import ResourceRecord

from .chunking import chunk_resource
from .index import HybridRagIndex


class ResourceIngestor:
    def __init__(self, index: HybridRagIndex) -> None:
        self.index = index

    def ingest(self, resource: ResourceRecord) -> int:
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
        return self.index.replace_resource(chunks)
