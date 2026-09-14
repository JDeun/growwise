from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProvider(Protocol):
    """Provider boundary used by GrowWise workflows.

    Callers depend on this interface instead of a concrete local/remote model vendor.
    """

    def generate_text(self, *, system: str, user: str) -> str: ...

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T: ...
