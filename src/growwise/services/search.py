from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from growwise.model import ModelProvider
from growwise.storage import SQLiteProjection

from .record_time import record_time

_RECORD_TYPES = ("learning_log", "activity_plan")
_AXIS_WORDS = {
    "physical": ("신체", "운동", "체육"),
    "emotional_character": ("정서", "인성"),
    "expression_art": ("예술", "미술", "음악"),
    "thinking_inquiry": ("사고", "탐구"),
    "social": ("사회성",),
    "reading": ("독서", "읽기", "읽은"),
    "speaking": ("말하기",),
    "writing": ("글쓰기", "쓰기"),
    "math": ("수학",),
    "exploration": ("탐색",),
}
_QUERY_FILLER = re.compile(
    r"(?<![가-힣])(?:최근|지난|이번|관련|주제|기록(?:들|만|을|은)?|활동(?:들|만|을|은)?|"
    r"찾아(?:줘|주세요)|보여(?:줘|주세요)|정리해(?:줘|주세요)|"
    r"마지막(?:으로)?|가장\s*최근|처음(?:으로)?|언제(?:야|인가요)?|"
    r"(?:한|일|달|주|개월|년|게|것|동안))(?![가-힣])"
)


def _ordered_on_line(text: str, first: str, second: str) -> bool:
    # Each line is scanned a constant number of times, even with repeated unmatched prefixes.
    return any(second in line.partition(first)[2] for line in text.split("\n"))


class SearchPlan(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    entity_types: list[str] = Field(default_factory=lambda: ["learning_log", "activity_plan"])
    limit: int = Field(default=20, ge=1, le=50)
    start_date: date | None = None
    end_date: date | None = None
    experience_axes: list[str] = Field(default_factory=list, max_length=10)
    order: Literal["relevance", "newest", "oldest"] = "relevance"

    @property
    def constrained(self) -> bool:
        return bool(self.start_date or self.end_date or self.experience_axes
                    or self.order != "relevance")

    def matches(self, payload: dict) -> bool:
        timestamp = record_time(payload)
        if self.start_date or self.end_date:
            if timestamp is None:
                return False
            event_date = timestamp.astimezone().date()
            if self.start_date and event_date < self.start_date:
                return False
            if self.end_date and event_date > self.end_date:
                return False
        if not self.experience_axes:
            return True
        axes = set(payload.get("experience_axes") or [])
        # A recorded subject or explicit record kind is also reliable metadata; requiring parents
        # to add a duplicate experience tag would hide valid school/study/reading records.
        subject = str(payload.get("subject") or "").casefold()
        for axis, words in _AXIS_WORDS.items():
            if subject and any(word in subject for word in (*words, axis)):
                axes.add(axis)
        if payload.get("record_kind") == "reading_reflection":
            axes.add("reading")
        return bool(set(self.experience_axes).intersection(axes))


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
Use the supplied local reference date for explicit time windows. Never invent a time or experience
axis restriction. Preserve explicit date/axis filters and distinguish the latest event from the most
recently edited record. Use newest/oldest order for last/first-event questions.
Prefer a few concrete Korean or English content keywords over generic temporal words."""

    def __init__(self, index: SQLiteProjection, provider: ModelProvider | None = None) -> None:
        self.index = index
        self.provider = provider

    @staticmethod
    def explicit_plan(query: str, limit: int, reference_date: date) -> SearchPlan:
        remaining = query
        start = end = None
        if match := re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:부터|~|에서)\s*"
                              r"(\d{4}-\d{2}-\d{2})(?:까지)?", remaining):
            try:
                start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
                if start > end:
                    start = end = None
                else:
                    remaining = remaining.replace(match[0], " ")
            except ValueError:
                pass
        elif match := re.search(r"(?<![가-힣])(오늘|어제)(?![가-힣])", remaining):
            start = end = reference_date - timedelta(days=match[1] == "어제")
            remaining = remaining.replace(match[0], " ")
        elif match := re.search(r"(지난|이번)\s*주(?![가-힣])", remaining):
            monday = reference_date - timedelta(days=reference_date.weekday())
            start, end = (monday - timedelta(days=7), monday - timedelta(days=1)) if (
                match[1] == "지난"
            ) else (monday, reference_date)
            remaining = remaining.replace(match[0], " ")
        elif "지난달" in remaining or "지난 달" in remaining:
            end = reference_date.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
            remaining = re.sub(r"지난\s*달", " ", remaining)
        elif "이번 달" in remaining or "이번달" in remaining:
            start, end = reference_date.replace(day=1), reference_date
            remaining = re.sub(r"이번\s*달", " ", remaining)
        else:
            match = re.search(r"(?:최근|지난)\s*(?:(\d+)\s*(일|주|개월|달|년)|"
                              r"(한\s*달|일주일|한\s*주|한\s*해|일\s*년))", remaining)
            if match:
                unit_days = {"일": 1, "주": 7, "개월": 30, "달": 30, "년": 365}
                days = (int(match[1]) * unit_days[match[2]] if match[1] else
                        30 if "달" in match[3] else 365 if any(
                            word in match[3] for word in ("년", "해")
                        ) else 7)
                # Inclusive calendar window; cap hostile values before timedelta construction.
                days = min(max(1, days), 36_500)
                start, end = reference_date - timedelta(days=days - 1), reference_date
                remaining = remaining.replace(match[0], " ")

        axes = []
        for axis, words in _AXIS_WORDS.items():
            for word in words:
                # A topic substring such as '사회성장' is not an explicit axis filter.
                pattern = rf"(?<![가-힣]){word}(?:에서|으로|의|만|을|를)?(?=\s|[,.?!]|$)"
                if re.search(pattern, remaining):
                    axes.append(axis)
                    remaining = re.sub(pattern, " ", remaining)
                    break
        order: Literal["relevance", "newest", "oldest"] = "relevance"
        if re.search(r"마지막|가장\s*최근", query) or _ordered_on_line(query, "최근", "언제"):
            order, limit = "newest", 1
        elif re.search(r"가장\s*처음", query) or _ordered_on_line(query, "처음", "언제"):
            order, limit = "oldest", 1
        elif "최근" in query:
            order = "newest"
        remaining = _QUERY_FILLER.sub(" ", remaining)
        terms = [term.strip(".,?!()[]{}\"'") for term in remaining.split()]
        keywords = [term for term in terms if len(term) >= 2]
        return SearchPlan(keywords=keywords, limit=limit, start_date=start, end_date=end,
                          experience_axes=list(dict.fromkeys(axes)), order=order)

    def plan(
        self, query: str, *, limit: int = 20, reference_date: date | None = None,
    ) -> SearchPlan:
        reference = reference_date or date.today()
        fallback = self.explicit_plan(query, limit, reference)
        if self.provider is None:
            return fallback
        try:
            plan = self.provider.generate_structured(
                system=self.SYSTEM,
                user=f"Local reference date: {reference.isoformat()}\nRequest: {query}",
                schema=SearchPlan,
            )
            plan.limit = min(plan.limit, limit)
            if not fallback.keywords:
                plan.keywords = []
            # Optional rewriting must never weaken an explicitly parsed user restriction.
            if fallback.start_date or fallback.end_date:
                plan.start_date, plan.end_date = fallback.start_date, fallback.end_date
            if fallback.experience_axes:
                plan.experience_axes = fallback.experience_axes
            if fallback.order != "relevance":
                plan.order, plan.limit = fallback.order, fallback.limit
            if plan.start_date and plan.end_date and plan.start_date > plan.end_date:
                return fallback
            return plan
        except Exception:
            return fallback

    def search(self, *, child_id: str, query: str, limit: int = 20,
               reference_date: date | None = None,
               entity_types: Sequence[str] = _RECORD_TYPES) -> SearchResponse:
        plan = self.plan(query, limit=limit, reference_date=reference_date)
        query_text = " ".join(plan.keywords)
        allowed = set(entity_types)
        entity_types = (tuple(entity_types) if tuple(entity_types) != _RECORD_TYPES else
                        tuple(item for item in plan.entity_types if item in allowed))
        if not entity_types:
            entity_types = tuple(allowed)
        results = self.index.search_entities(
            child_id=child_id,
            query_text=query_text,
            entity_types=entity_types,
            # Explicit filters must run before truncation. These are private family records, not
            # an unbounded public corpus; the ordinary lexical path retains its bounded SQL query.
            limit=None if plan.constrained else plan.limit,
        )
        results = [payload for payload in results if plan.matches(payload)]
        if plan.order != "relevance":
            results.sort(
                key=lambda payload: record_time(payload) or datetime.min.replace(tzinfo=UTC),
                reverse=plan.order == "newest",
            )
        results = results[:plan.limit]
        return SearchResponse(query=query, plan=plan, results=results)
