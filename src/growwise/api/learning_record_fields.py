"""Shared validation for optional source references in parent-authored learning records."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from growwise.domain import ResourceKind
from growwise.services.visibility import entity_visible_to_child
from growwise.storage import EntityStore


def validate_learning_book(*, book_id: UUID | None, child_id: UUID, store: EntityStore) -> None:
    if book_id is None:
        return
    book = store.index.get_entity(str(book_id), entity_type="resource")
    if book is None or not entity_visible_to_child(
        store.index, entity_id=str(book_id), child_id=str(child_id), entity_type="resource",
    ):
        raise HTTPException(status_code=404, detail="book_not_found")
    if book.get("kind") != ResourceKind.BOOK.value:
        raise HTTPException(status_code=422, detail="book_reference_must_be_book")
