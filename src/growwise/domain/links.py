from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import Field, model_validator

from .models import EntityBase


class EntityLinkRelation(StrEnum):
    """Stable relation vocabulary for GrowWise's local document graph.

    ``child_scope`` means the source entity should also appear in the target child's context
    without copying the source document. The remaining relations describe provenance and loose
    knowledge connections and are intentionally non-diagnostic.
    """

    CHILD_SCOPE = "child_scope"
    RELATED = "related"
    DERIVED_FROM = "derived_from"
    DOCUMENTS = "documents"
    SUPPORTS = "supports"


class EntityLink(EntityBase):
    """A directed, local-only link between two GrowWise entities.

    Links are first-class Markdown records so backlinks survive index rebuilds. ``child_id`` is
    populated for child-scoped shares so privacy deletion can remove the association without
    duplicating or mutating the source document.
    """

    entity_type: str = "entity_link"
    child_id: UUID | None = None
    source_id: UUID
    target_id: UUID
    relation: EntityLinkRelation
    label: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_link(self) -> EntityLink:
        if self.source_id == self.target_id:
            raise ValueError("entity links cannot point to themselves")
        if (
            self.relation is EntityLinkRelation.CHILD_SCOPE
            and (self.child_id is None or self.child_id != self.target_id)
        ):
            raise ValueError("child_scope links must use target child as child_id")
        return self
