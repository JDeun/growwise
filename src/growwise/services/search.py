from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.model import ModelProvider
from growwise.storage import SQLiteProjection


class SearchPlan(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=lambda: ["learning_log", "activity_plan"])
    limit: int = Field(default=20, ge=1, le=50)


class SearchResponse(BaseModel):
    query: str
    plan: SearchPlan
    results: list[dict]


class NaturalLanguageSearch:
    SYSTEM = """Convert a parent's natural-language GrowWise search request
into a conservative local search plan.
Do not answer the question. Extract only search keywords and relevant entity types.
Never remove child scoping: child isolation is enforced outside the model.
Allowed entity types: learning_log, activity_plan.
Prefer a few concrete Korean or English content keywords over generic temporal words."""

    def __init__(self, index: SQLiteProjection, provider: ModelProvider | None = None) -> None:
        self.index = index
        self.provider = provider

    def _fallback_plan(self, query: str, limit: int) -> SearchPlan:
        terms = [term.strip(".,?!()[]{}\"'") for term in query.split()]
        keywords = [term for term in terms if len(term) >= 2]
        return SearchPlan(keywords=keywords, limit=limit)

    def plan(self, query: str, *, limit: int = 20) -> SearchPlan:
        if self.provider is None:
            return self._fallback_plan(query, limit)
        try:
            plan = self.provider.generate_structured(
                system=self.SYSTEM,
                user=query,
                schema=SearchPlan,
            )
            plan.limit = min(plan.limit, limit)
            return plan
        except Exception:
            return self._fallback_plan(query, limit)

    def search(self, *, child_id: str, query: str, limit: int = 20) -> SearchResponse:
        plan = self.plan(query, limit=limit)
        query_text = " ".join(plan.keywords) or query
        allowed = {"learning_log", "activity_plan"}
        entity_types = tuple(item for item in plan.entity_types if item in allowed)
        if not entity_types:
            entity_types = ("learning_log", "activity_plan")
        results = self.index.search_entities(
            child_id=child_id,
            query_text=query_text,
            entity_types=entity_types,
            limit=plan.limit,
        )
        return SearchResponse(query=query, plan=plan, results=results)
