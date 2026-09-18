from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from growwise.adapters import (
    Data4LibraryAdapter,
    ExternalAdapterError,
    OfficialKoreanCurriculumCatalogAdapter,
    OverpassAdapter,
    PublicCurriculumAdapter,
    SQLiteExternalCache,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord
from growwise.rag import ResourceIngestor
from growwise.services.public_query import generalize_public_terms
from growwise.storage import EntityStore


class DiscoveryCategory(StrEnum):
    BOOK = "book"
    CURRICULUM = "curriculum"
    PLACE = "place"


class DiscoverySuggestion(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=120)
    category: DiscoveryCategory
    resource_kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=20_000)
    source_name: str = Field(min_length=1, max_length=500)
    source_url: str | None = Field(default=None, max_length=2_048)
    author: str | None = Field(default=None, max_length=500)
    attribution: str = Field(min_length=1, max_length=2_000)
    license_note: str = Field(min_length=1, max_length=4_000)
    cache_status: str = Field(min_length=1, max_length=40)
    rationale: str = Field(min_length=1, max_length=2_000)
    query_term: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list, max_length=30)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=40)


class DiscoverySourceState(BaseModel):
    source: str
    enabled: bool
    status: str
    detail: str | None = None


class DiscoveryResponse(BaseModel):
    query: str
    query_terms: list[str]
    suggestions: list[DiscoverySuggestion]
    sources: list[DiscoverySourceState]


class EducationDiscoveryService:
    """Find public education resources without exporting private child records.

    Private records may contribute to local ranking terms, but external adapters receive only
    allow-listed generic education topics, school stage, or parent-supplied map coordinates.
    Child IDs, names, observations, free-form interests, activity titles, and notes never cross
    this boundary.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        store: EntityStore,
        ingestor: ResourceIngestor,
    ) -> None:
        self.settings = settings
        self.store = store
        self.ingestor = ingestor
        self.cache = SQLiteExternalCache(settings.external_cache_path)

    def discover(
        self,
        *,
        child: ChildProfile,
        query: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        limit: int = 12,
        offline: bool = False,
    ) -> DiscoveryResponse:
        local_terms = self._query_terms(child=child, explicit_query=query)
        public_terms = generalize_public_terms(local_terms)
        public_query = " ".join(public_terms[:3]).strip()
        suggestions: list[DiscoverySuggestion] = []
        source_states: list[DiscoverySourceState] = []

        self._collect_official_curriculum(
            child=child,
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
        )
        self._collect_public_curriculum(
            child=child,
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_books(
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_places(
            latitude=latitude,
            longitude=longitude,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )

        ranked = self._rank(suggestions, terms=local_terms)
        return DiscoveryResponse(
            query=public_query,
            query_terms=public_terms,
            suggestions=ranked[:limit],
            sources=source_states,
        )

    def save(
        self,
        *,
        child: ChildProfile,
        suggestion: DiscoverySuggestion,
    ) -> ResourceRecord:
        for payload in self.store.index.list_entities(
            entity_type="resource",
            child_id=str(child.id),
        ):
            provenance = payload.get("provenance") or {}
            if provenance.get("discovery_candidate_id") == suggestion.candidate_id:
                resource = ResourceRecord.model_validate(payload)
                # RAG is a disposable projection. Re-ingest an already-authoritative resource so a
                # crash between Markdown save and the original ingest converges on retry instead of
                # leaving the resource permanently absent from search until a full rebuild.
                self.ingestor.ingest(resource)
                return resource

        provenance = {
            "discovery_candidate_id": suggestion.candidate_id,
            "discovery_source": suggestion.source_name,
            "attribution": suggestion.attribution,
            "license_note": suggestion.license_note,
            "cache_status": suggestion.cache_status,
        }
        if suggestion.query_term:
            provenance["discovery_query"] = suggestion.query_term
        for key, value in suggestion.metadata.items():
            provenance[f"source_{key}"] = value[:4_000]

        resource = ResourceRecord(
            child_id=child.id,
            kind=suggestion.resource_kind,
            title=suggestion.title,
            summary=suggestion.summary,
            source_url=suggestion.source_url,
            source_name=suggestion.source_name,
            author=suggestion.author,
            tags=list(dict.fromkeys([*suggestion.tags, "discovered"])),
            stage_tags=[child.stage],
            provenance=provenance,
        )
        self.store.save(resource)
        self.ingestor.ingest(resource)
        return resource

    def _query_terms(self, *, child: ChildProfile, explicit_query: str | None) -> list[str]:
        """Build rich local terms for ranking; callers must not send these terms externally."""
        if explicit_query and explicit_query.strip():
            return self._normalize_terms([explicit_query])

        values: list[str] = [*child.interests, *child.learning_goals]
        logs = self.store.index.list_entities(
            entity_type="learning_log",
            child_id=str(child.id),
            limit=20,
        )
        for payload in logs:
            interest = payload.get("interest")
            if isinstance(interest, str):
                values.append(interest)
            tags = payload.get("tags")
            if isinstance(tags, list):
                values.extend(str(tag) for tag in tags)
        activities = self.store.index.list_entities(
            entity_type="activity_plan",
            child_id=str(child.id),
            limit=10,
        )
        values.extend(
            str(payload.get("title") or "")
            for payload in activities
            if payload.get("title")
        )
        return self._normalize_terms(values)

    @staticmethod
    def _normalize_terms(values: Iterable[str]) -> list[str]:
        terms: list[str] = []
        seen: set[str] = set()
        for value in values:
            for raw in value.replace(",", " ").replace("/", " ").split():
                term = raw.strip()[:80]
                folded = term.casefold()
                if len(term) < 2 or folded in seen:
                    continue
                seen.add(folded)
                terms.append(term)
                if len(terms) >= 12:
                    return terms
        return terms

    def _collect_official_curriculum(
        self,
        *,
        child: ChildProfile,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
    ) -> None:
        adapter = OfficialKoreanCurriculumCatalogAdapter()
        result = adapter.search(stage=child.stage.value)
        suggestions.extend(
            self._curriculum_suggestions(
                result.records,
                source=result.source,
                attribution=result.attribution,
                license_note=result.license_note,
                cache_status=result.cache_status,
                query=query,
            )
        )
        source_states.append(
            DiscoverySourceState(source=result.source, enabled=True, status="ready")
        )

    def _collect_public_curriculum(
        self,
        *,
        child: ChildProfile,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if not self.settings.curriculum_endpoint:
            source_states.append(
                DiscoverySourceState(
                    source="public_curriculum",
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        adapter = PublicCurriculumAdapter(
            endpoint=self.settings.curriculum_endpoint,
            cache=self.cache,
            ttl_seconds=self.settings.curriculum_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                stage=child.stage.value,
                query=query or None,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            source_states.append(
                DiscoverySourceState(
                    source="public_curriculum",
                    enabled=True,
                    status="unavailable",
                    detail=str(exc)[:500],
                )
            )
            return
        suggestions.extend(
            self._curriculum_suggestions(
                result.records,
                source=result.source,
                attribution=result.attribution,
                license_note=result.license_note,
                cache_status=result.cache_status,
                query=query,
            )
        )
        source_states.append(
            DiscoverySourceState(
                source=result.source,
                enabled=True,
                status=result.cache_status,
            )
        )

    def _collect_books(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        api_key = (self.settings.data4library_api_key or "").strip()
        if not api_key:
            source_states.append(
                DiscoverySourceState(
                    source="data4library",
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if not query:
            source_states.append(
                DiscoverySourceState(
                    source="data4library",
                    enabled=True,
                    status="needs_query",
                )
            )
            return
        adapter = Data4LibraryAdapter(
            auth_key=api_key,
            cache=self.cache,
            endpoint=self.settings.data4library_endpoint,
            ttl_seconds=self.settings.data4library_cache_ttl_seconds,
        )
        try:
            result = adapter.search_books(
                keyword=query,
                page_size=8,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            source_states.append(
                DiscoverySourceState(
                    source="data4library",
                    enabled=True,
                    status="unavailable",
                    detail=str(exc)[:500],
                )
            )
            return

        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            authors = self._text(record.get("authors"))
            publisher = self._text(record.get("publisher"))
            isbn = self._text(record.get("isbn13"))
            summary_parts = [part for part in (authors, publisher) if part]
            suggestions.append(
                DiscoverySuggestion(
                    candidate_id=self._candidate_id(result.source, isbn or title),
                    category=DiscoveryCategory.BOOK,
                    resource_kind=ResourceKind.BOOK,
                    title=title,
                    summary=" · ".join(summary_parts) or None,
                    source_name=result.source,
                    source_url=self._optional_text(record.get("book_detail_url")),
                    author=authors or None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale=f"'{query}'와 연결된 도서 후보입니다.",
                    query_term=query,
                    tags=["도서", *query.split()[:3]],
                    metadata={
                        key: value
                        for key, value in {
                            "isbn13": isbn,
                            "publisher": publisher,
                            "publication_year": self._text(record.get("publication_year")),
                            "class_name": self._text(record.get("class_name")),
                        }.items()
                        if value
                    },
                )
            )
        source_states.append(
            DiscoverySourceState(
                source=result.source,
                enabled=True,
                status=result.cache_status,
            )
        )

    def _collect_places(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if latitude is None or longitude is None:
            source_states.append(
                DiscoverySourceState(
                    source="openstreetmap_overpass",
                    enabled=True,
                    status="needs_location",
                )
            )
            return
        adapter = OverpassAdapter(
            cache=self.cache,
            endpoint=self.settings.overpass_endpoint,
            ttl_seconds=self.settings.overpass_cache_ttl_seconds,
        )
        try:
            result = adapter.nearby_places(
                latitude=latitude,
                longitude=longitude,
                radius_m=self.settings.discovery_place_radius_m,
                amenities=("library", "museum", "arts_centre", "community_centre"),
                offline=offline,
            )
        except ExternalAdapterError as exc:
            source_states.append(
                DiscoverySourceState(
                    source="openstreetmap_overpass",
                    enabled=True,
                    status="unavailable",
                    detail=str(exc)[:500],
                )
            )
            return
        for record in result.records:
            title = self._text(record.get("name"))
            amenity = self._text(record.get("amenity"))
            osm_id = self._text(record.get("osm_id"))
            if not title:
                continue
            suggestions.append(
                DiscoverySuggestion(
                    candidate_id=self._candidate_id(
                        result.source,
                        f"{record.get('osm_type', '')}:{osm_id}",
                    ),
                    category=DiscoveryCategory.PLACE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=f"탐방 후보 · {amenity or 'public place'}",
                    source_name=result.source,
                    source_url=self._optional_text(record.get("website")),
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="부모가 지정한 위치 주변의 탐방 후보입니다.",
                    tags=["탐방", amenity] if amenity else ["탐방"],
                    metadata={
                        "osm_type": self._text(record.get("osm_type")),
                        "osm_id": osm_id,
                    },
                )
            )
        source_states.append(
            DiscoverySourceState(
                source=result.source,
                enabled=True,
                status=result.cache_status,
            )
        )

    @staticmethod
    def _curriculum_suggestions(
        records: list[dict[str, Any]],
        *,
        source: str,
        attribution: str,
        license_note: str,
        cache_status: str,
        query: str,
    ) -> list[DiscoverySuggestion]:
        suggestions: list[DiscoverySuggestion] = []
        for record in records:
            title = EducationDiscoveryService._text(record.get("title"))
            if not title:
                continue
            domain = EducationDiscoveryService._text(record.get("domain"))
            subject = EducationDiscoveryService._text(record.get("subject"))
            standard = EducationDiscoveryService._text(record.get("achievement_standard"))
            summary = " · ".join(part for part in (subject, domain, standard) if part) or None
            curriculum_id = EducationDiscoveryService._text(record.get("curriculum_id"))
            metadata = record.get("metadata")
            if not isinstance(metadata, dict):
                metadata = {}
            safe_metadata = {
                str(key): str(value)[:1_000]
                for key, value in metadata.items()
                if isinstance(key, str) and value is not None
            }
            suggestions.append(
                DiscoverySuggestion(
                    candidate_id=EducationDiscoveryService._candidate_id(
                        source,
                        curriculum_id or title,
                    ),
                    category=DiscoveryCategory.CURRICULUM,
                    resource_kind=ResourceKind.CURRICULUM,
                    title=title,
                    summary=summary,
                    source_name=source,
                    source_url=EducationDiscoveryService._optional_text(record.get("source_url")),
                    attribution=attribution,
                    license_note=license_note,
                    cache_status=cache_status,
                    rationale=(
                        f"'{query}'와 연결해 확인할 수 있는 교육과정 근거입니다."
                        if query
                        else "현재 단계에서 확인할 수 있는 공식 교육과정 근거입니다."
                    ),
                    query_term=query or None,
                    tags=[value for value in ("교육과정", subject, domain) if value],
                    metadata={
                        "curriculum_id": curriculum_id,
                        **safe_metadata,
                    },
                )
            )
        return suggestions

    @staticmethod
    def _rank(
        suggestions: list[DiscoverySuggestion],
        *,
        terms: list[str],
    ) -> list[DiscoverySuggestion]:
        category_priority = {
            DiscoveryCategory.BOOK: 3,
            DiscoveryCategory.PLACE: 2,
            DiscoveryCategory.CURRICULUM: 1,
        }

        def score(item: DiscoverySuggestion) -> tuple[int, int, str]:
            haystack = " ".join([item.title, item.summary or "", *item.tags]).casefold()
            matches = sum(1 for term in terms if term.casefold() in haystack)
            return matches, category_priority[item.category], item.title

        by_id: dict[str, DiscoverySuggestion] = {}
        for suggestion in suggestions:
            by_id.setdefault(suggestion.candidate_id, suggestion)
        return sorted(by_id.values(), key=score, reverse=True)

    @staticmethod
    def _candidate_id(source: str, source_key: str) -> str:
        digest = hashlib.sha256(f"{source}\x1f{source_key}".encode()).hexdigest()[:24]
        return f"{source}:{digest}"

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if value is not None else ""

    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        text = cls._text(value)
        return text or None
