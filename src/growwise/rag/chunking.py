from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(slots=True, frozen=True)
class ResourceChunk:
    resource_id: str
    chunk_id: str
    child_id: str | None
    title: str
    text: str
    source_url: str | None
    source_name: str | None
    tags: tuple[str, ...]
    recorded_at: str | None = None


def chunk_resource(
    *,
    resource_id: str,
    child_id: str | None,
    title: str,
    text: str,
    source_url: str | None,
    source_name: str | None,
    tags: list[str],
    recorded_at: str | None = None,
    chunk_size: int = 900,
    chunk_overlap: int = 120,
) -> list[ResourceChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = [piece.strip() for piece in splitter.split_text(text) if piece.strip()]
    return [
        ResourceChunk(
            resource_id=resource_id,
            chunk_id=f"{resource_id}:{index}",
            child_id=child_id,
            title=title,
            text=piece,
            source_url=source_url,
            source_name=source_name,
            tags=tuple(tags),
            recorded_at=recorded_at,
        )
        for index, piece in enumerate(pieces)
    ]
