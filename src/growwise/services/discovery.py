from __future__ import annotations

import hashlib
from collections.abc import Iterable
from enum import StrEnum
from typing import Any
from uuid import uuid5

from pydantic import BaseModel, Field

from growwise.adapters import (
    CuratedEducationCatalogAdapter,
    Data4LibraryAdapter,
    ExternalAdapterError,
    GbifSpeciesAdapter,
    GoogleBooksAdapter,
    HeritagePalaceAdapter,
    KmaWeatherAdapter,
    KrDictAdapter,
    MuseumArtGalleryAdapter,
    NasaImagesAdapter,
    NationalLibraryIsbnAdapter,
    OfficialKoreanCurriculumCatalogAdapter,
    OpenLibraryAdapter,
    OverpassAdapter,
    PublicCurriculumAdapter,
    SQLiteExternalCache,
    WikidataAdapter,
    WikimediaCommonsAdapter,
    WikipediaAdapter,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord
from growwise.rag import ResourceIngestor
from growwise.services.public_query import generalize_public_terms, translate_public_terms
from growwise.storage import EntityStore


class DiscoveryCategory(StrEnum):
    BOOK = "book"
    CURRICULUM = "curriculum"
    PLACE = "place"
    REFERENCE = "reference"
    SCIENCE = "science"
    NATURE = "nature"
    MEDIA = "media"


class DiscoverySuggestion(BaseModel):
    candidate_id: str = Field(min_length=1, max_length=120)
    category: DiscoveryCategory
    resource_kind: ResourceKind
    title: str = Field(min_length=1, max_length=500)
    summary: str | None = Field(default=None, max_length=20_000)
    content: str | None = Field(default=None, max_length=20_000)
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


_NATURE_TERMS = {
    "동물",
    "고양이",
    "강아지",
    "곤충",
    "식물",
    "자연",
    "환경",
    "생태",
    "바다",
    "물고기",
    "나무",
    "꽃",
}
_SPACE_TERMS = {"우주", "별", "달", "지구"}
_NASA_TERMS = {
    *_SPACE_TERMS,
    "환경",
    "날씨",
    "계절",
    "과학",
}
_SCIENCE_TERMS = {
    *_SPACE_TERMS,
    *_NATURE_TERMS,
    "날씨",
    "계절",
    "물",
    "빛",
    "소리",
    "자석",
    "힘",
    "에너지",
    "과학",
    "실험",
    "관찰",
}
_HERITAGE_TERMS = {"역사", "한국사", "문화", "박물관"}
_WEATHER_TERMS = {"날씨", "계절", "환경", "과학", "관찰"}



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
        english_query = " ".join(
            translate_public_terms(public_terms[:3], language="en")
        ).strip()
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

        # Books: combine Korean library metadata with two broad international catalogs.
        self._collect_data4library(
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_national_library(
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_krdict(
            query=public_query,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_curated_catalog(
            public_terms=public_terms,
            suggestions=suggestions,
            source_states=source_states,
        )
        if self.settings.public_enrichment_enabled:
            self._collect_open_library(
                query=english_query or public_query,
                suggestions=suggestions,
                source_states=source_states,
                offline=offline,
            )
            self._collect_google_books(
                query=public_query or english_query,
                suggestions=suggestions,
                source_states=source_states,
                offline=offline,
            )
        else:
            source_states.extend(
                [
                    DiscoverySourceState(
                        source=OpenLibraryAdapter.SOURCE,
                        enabled=False,
                        status="disabled",
                    ),
                    DiscoverySourceState(
                        source=GoogleBooksAdapter.SOURCE,
                        enabled=False,
                        status="disabled",
                    ),
                ]
            )

        # General factual/reference enrichment.
        if self.settings.public_enrichment_enabled:
            self._collect_wikipedia(
                query=public_query,
                suggestions=suggestions,
                source_states=source_states,
                offline=offline,
            )
            self._collect_wikidata(
                query=public_query,
                suggestions=suggestions,
                source_states=source_states,
                offline=offline,
            )
            self._collect_commons(
                query=english_query or public_query,
                suggestions=suggestions,
                source_states=source_states,
                offline=offline,
            )

            if set(public_terms) & _HERITAGE_TERMS:
                self._collect_heritage(
                    query=public_query,
                    suggestions=suggestions,
                    source_states=source_states,
                    offline=offline,
                )
            else:
                source_states.append(
                    DiscoverySourceState(
                        source=HeritagePalaceAdapter.SOURCE,
                        enabled=True,
                        status="not_relevant",
                    )
                )

            # Science/nature sources are called only when the allow-listed topic warrants them.
            if set(public_terms) & _NASA_TERMS:
                self._collect_nasa(
                    query=english_query or public_query,
                    suggestions=suggestions,
                    source_states=source_states,
                    offline=offline,
                )
            else:
                source_states.append(
                    DiscoverySourceState(
                        source=NasaImagesAdapter.SOURCE,
                        enabled=True,
                        status="not_relevant",
                    )
                )

            if set(public_terms) & _NATURE_TERMS:
                self._collect_gbif(
                    query=english_query or public_query,
                    suggestions=suggestions,
                    source_states=source_states,
                    offline=offline,
                )
            else:
                source_states.append(
                    DiscoverySourceState(
                        source=GbifSpeciesAdapter.SOURCE,
                        enabled=True,
                        status="not_relevant",
                    )
                )
        else:
            for source in (
                WikipediaAdapter.SOURCE,
                WikidataAdapter.SOURCE,
                WikimediaCommonsAdapter.SOURCE,
                NasaImagesAdapter.SOURCE,
                GbifSpeciesAdapter.SOURCE,
                HeritagePalaceAdapter.SOURCE,
            ):
                source_states.append(
                    DiscoverySourceState(
                        source=source,
                        enabled=False,
                        status="disabled",
                    )
                )

        self._collect_places(
            latitude=latitude,
            longitude=longitude,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_museums(
            latitude=latitude,
            longitude=longitude,
            suggestions=suggestions,
            source_states=source_states,
            offline=offline,
        )
        self._collect_weather(
            public_terms=public_terms,
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
                self.ingestor.ingest(resource)
                return resource

        provenance = {
            "discovery_candidate_id": suggestion.candidate_id,
            "discovery_source": suggestion.source_name,
            "attribution": suggestion.attribution,
            "license_note": suggestion.license_note,
            "cache_status": suggestion.cache_status,
            "discovery_category": suggestion.category.value,
        }
        if suggestion.query_term:
            provenance["discovery_query"] = suggestion.query_term
        for key, value in suggestion.metadata.items():
            provenance[f"source_{key}"] = value[:4_000]

        resource = ResourceRecord(
            id=uuid5(child.id, f"growwise:discovery:{suggestion.candidate_id}"),
            child_id=child.id,
            kind=suggestion.resource_kind,
            title=suggestion.title,
            summary=suggestion.summary,
            content=suggestion.content,
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

    @staticmethod
    def _needs_query(
        *,
        source: str,
        query: str,
        source_states: list[DiscoverySourceState],
    ) -> bool:
        if query:
            return False
        source_states.append(
            DiscoverySourceState(source=source, enabled=True, status="needs_query")
        )
        return True

    @staticmethod
    def _failed_source(
        *,
        source: str,
        exc: Exception,
        source_states: list[DiscoverySourceState],
    ) -> None:
        source_states.append(
            DiscoverySourceState(
                source=source,
                enabled=True,
                status="unavailable",
                detail=str(exc)[:500],
            )
        )

    @staticmethod
    def _source_ready(
        *,
        result_source: str,
        cache_status: str,
        source_states: list[DiscoverySourceState],
    ) -> None:
        source_states.append(
            DiscoverySourceState(
                source=result_source,
                enabled=True,
                status=cache_status,
            )
        )

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
            self._failed_source(
                source="public_curriculum",
                exc=exc,
                source_states=source_states,
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
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_data4library(
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
                    source=Data4LibraryAdapter.SOURCE,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if self._needs_query(
            source=Data4LibraryAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
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
                page_size=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=Data4LibraryAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
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
                self._suggestion(
                    source=result.source,
                    source_key=isbn or title,
                    category=DiscoveryCategory.BOOK,
                    resource_kind=ResourceKind.BOOK,
                    title=title,
                    summary=" · ".join(summary_parts) or None,
                    content=None,
                    source_url=self._optional_text(record.get("book_detail_url")),
                    author=authors or None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale=f"'{query}'와 연결된 국내 도서 후보입니다.",
                    query=query,
                    tags=["도서", *query.split()[:3]],
                    metadata={
                        "isbn13": isbn,
                        "publisher": publisher,
                        "publication_year": self._text(record.get("publication_year")),
                        "class_name": self._text(record.get("class_name")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_national_library(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        api_key = (self.settings.national_library_api_key or "").strip()
        if not api_key:
            source_states.append(
                DiscoverySourceState(
                    source=NationalLibraryIsbnAdapter.SOURCE,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if self._needs_query(
            source=NationalLibraryIsbnAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = NationalLibraryIsbnAdapter(
            api_key=api_key,
            cache=self.cache,
            endpoint=self.settings.national_library_isbn_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search_books(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=NationalLibraryIsbnAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            author = self._text(record.get("author"))
            publisher = self._text(record.get("publisher"))
            publish_date = self._text(record.get("publish_date"))
            summary = " · ".join(
                part for part in (author, publisher, publish_date) if part
            )
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.BOOK,
                    resource_kind=ResourceKind.BOOK,
                    title=title,
                    summary=summary or None,
                    content=None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=author or None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="국립중앙도서관 서지정보에서 확인한 국내 도서 후보입니다.",
                    query=query,
                    tags=["도서", "국립중앙도서관"],
                    metadata={
                        "publisher": publisher,
                        "publish_date": publish_date,
                        "isbn13": self._text(record.get("isbn13")),
                        "keywords": self._text(record.get("keywords")),
                        "language": self._text(record.get("language")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_krdict(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        api_key = (self.settings.krdict_api_key or "").strip()
        if not api_key:
            source_states.append(
                DiscoverySourceState(
                    source=KrDictAdapter.SOURCE,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if self._needs_query(
            source=KrDictAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = KrDictAdapter(
            api_key=api_key,
            cache=self.cache,
            endpoint=self.settings.krdict_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=KrDictAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            raw_definitions = record.get("definitions")
            definitions = (
                [str(value) for value in raw_definitions[:4]]
                if isinstance(raw_definitions, list)
                else []
            )
            definition_text = "\n".join(definitions)
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.REFERENCE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=" · ".join(definitions[:2]) or None,
                    content=definition_text or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="국립국어원 사전에서 확인한 어휘·뜻풀이 후보입니다.",
                    query=query,
                    tags=["언어", "사전", title],
                    metadata={
                        "pronunciation": self._text(record.get("pronunciation")),
                        "word_grade": self._text(record.get("word_grade")),
                        "part_of_speech": self._text(record.get("part_of_speech")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_curated_catalog(
        self,
        *,
        public_terms: list[str],
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
    ) -> None:
        if not public_terms:
            source_states.append(
                DiscoverySourceState(
                    source=CuratedEducationCatalogAdapter.SOURCE,
                    enabled=True,
                    status="needs_query",
                )
            )
            return
        result = CuratedEducationCatalogAdapter().search(terms=public_terms)
        science_ids = {"phet", "openstax", "nasa-kids-club"}
        book_ids = {"storyweaver", "global-digital-library"}
        for record in result.records:
            title = self._text(record.get("title"))
            source_key = self._text(record.get("id"))
            if not title or not source_key:
                continue
            if source_key in science_ids:
                category = DiscoveryCategory.SCIENCE
            elif source_key in book_ids:
                category = DiscoveryCategory.BOOK
            else:
                category = DiscoveryCategory.REFERENCE
            raw_tags = record.get("tags")
            tags = [str(value) for value in raw_tags[:8]] if isinstance(raw_tags, list) else []
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=source_key,
                    category=category,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=self._optional_text(record.get("summary")),
                    content=None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=(
                        self._text(record.get("license_note"))
                        or result.license_note
                    ),
                    cache_status=result.cache_status,
                    rationale="공식 교육 콘텐츠 카탈로그에서 확인할 수 있는 후보입니다.",
                    query=" ".join(public_terms[:3]),
                    tags=tags,
                    metadata={"catalog_id": source_key},
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_open_library(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=OpenLibraryAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = OpenLibraryAdapter(
            cache=self.cache,
            endpoint=self.settings.openlibrary_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search_books(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=OpenLibraryAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            subjects = record.get("subjects")
            subject_list = [str(v) for v in subjects[:8]] if isinstance(subjects, list) else []
            authors = self._text(record.get("authors"))
            year = self._text(record.get("first_publish_year"))
            summary = " · ".join(
                part
                for part in (authors, year, ", ".join(subject_list[:4]))
                if part
            )
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.BOOK,
                    resource_kind=ResourceKind.BOOK,
                    title=title,
                    summary=summary or None,
                    content=", ".join(subject_list) or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=authors or None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="주제와 연결된 국제 도서·서지 후보입니다.",
                    query=query,
                    tags=["도서", *subject_list[:5]],
                    metadata={
                        "isbn": self._text(record.get("isbn")),
                        "first_publish_year": year,
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_google_books(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=GoogleBooksAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = GoogleBooksAdapter(
            cache=self.cache,
            api_key=self.settings.google_books_api_key,
            endpoint=self.settings.google_books_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search_books(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=GoogleBooksAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            authors = self._text(record.get("authors"))
            description = self._text(record.get("description"))
            categories = record.get("categories")
            category_list = [str(v) for v in categories[:8]] if isinstance(categories, list) else []
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.BOOK,
                    resource_kind=ResourceKind.BOOK,
                    title=title,
                    summary=description[:1_500] or authors or None,
                    content=description or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=authors or None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="주제와 연결된 Google Books 서지·설명 후보입니다.",
                    query=query,
                    tags=["도서", *category_list[:5]],
                    metadata={
                        "publisher": self._text(record.get("publisher")),
                        "published_date": self._text(record.get("published_date")),
                        "isbn13": self._text(record.get("isbn13")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_wikipedia(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=WikipediaAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = WikipediaAdapter(
            cache=self.cache,
            endpoint=self.settings.wikipedia_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=WikipediaAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            description = self._text(record.get("description"))
            excerpt = self._text(record.get("excerpt"))
            content = "\n".join(part for part in (description, excerpt) if part)
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.REFERENCE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=description or excerpt[:1_500] or None,
                    content=content or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="주제의 기본 개념과 배경을 확인할 백과 후보입니다.",
                    query=query,
                    tags=["백과", *query.split()[:3]],
                    metadata={},
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_wikidata(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=WikidataAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = WikidataAdapter(
            cache=self.cache,
            endpoint=self.settings.wikidata_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=WikidataAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            description = self._text(record.get("description"))
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.REFERENCE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=description or None,
                    content=description or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="CC0 구조화 지식에서 확인할 개념 후보입니다.",
                    query=query,
                    tags=["Wikidata", *query.split()[:3]],
                    metadata={"entity_id": self._text(record.get("id"))},
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_commons(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=WikimediaCommonsAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = WikimediaCommonsAdapter(
            cache=self.cache,
            endpoint=self.settings.wikimedia_commons_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search_images(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=WikimediaCommonsAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            description = self._text(record.get("description"))
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.MEDIA,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=(
                        description[:1_500]
                        or "상업적 재사용 조건을 통과한 Wikimedia Commons 이미지"
                    ),
                    content=description or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=self._optional_text(record.get("artist")),
                    attribution=result.attribution,
                    license_note=(
                        f"{result.license_note}; "
                        f"file license={self._text(record.get('license'))}"
                    ),
                    cache_status=result.cache_status,
                    rationale="관찰·비교·설명 활동에 활용할 수 있는 공개 이미지 후보입니다.",
                    query=query,
                    tags=["이미지", *query.split()[:3]],
                    metadata={
                        "image_url": self._text(record.get("image_url")),
                        "license": self._text(record.get("license")),
                        "license_url": self._text(record.get("license_url")),
                        "credit": self._text(record.get("credit")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_nasa(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=NasaImagesAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = NasaImagesAdapter(
            cache=self.cache,
            endpoint=self.settings.nasa_images_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=NasaImagesAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            description = self._text(record.get("description"))
            keywords = record.get("keywords")
            keyword_list = [str(v) for v in keywords[:10]] if isinstance(keywords, list) else []
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.SCIENCE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=description[:1_500] or None,
                    content=description or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale=(
                        "실제 NASA 이미지·설명으로 관찰과 과학 질문을 만들 수 있는 후보입니다."
                    ),
                    query=query,
                    tags=["NASA", "과학", *keyword_list[:5]],
                    metadata={
                        "nasa_id": self._text(record.get("id")),
                        "image_url": self._text(record.get("image_url")),
                        "date_created": self._text(record.get("date_created")),
                        "center": self._text(record.get("center")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_gbif(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=GbifSpeciesAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = GbifSpeciesAdapter(
            cache=self.cache,
            endpoint=self.settings.gbif_species_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(
                query=query,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=GbifSpeciesAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            scientific = self._text(record.get("scientific_name"))
            taxonomy = " > ".join(
                value
                for value in (
                    self._text(record.get("kingdom")),
                    self._text(record.get("phylum")),
                    self._text(record.get("class")),
                    self._text(record.get("order")),
                    self._text(record.get("family")),
                )
                if value
            )
            content = "\n".join(
                part for part in (
                    f"scientific name: {scientific}" if scientific else "",
                    f"taxonomy: {taxonomy}" if taxonomy else "",
                    f"rank: {self._text(record.get('rank'))}",
                    f"status: {self._text(record.get('status'))}",
                ) if part
            )
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.NATURE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=scientific or taxonomy or None,
                    content=content or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="생물 이름과 분류를 확인해 관찰 활동의 사실 근거로 쓸 수 있습니다.",
                    query=query,
                    tags=["생물", "GBIF", *query.split()[:3]],
                    metadata={
                        "taxon_key": self._text(record.get("id")),
                        "scientific_name": scientific,
                        "rank": self._text(record.get("rank")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
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
            self._failed_source(
                source="openstreetmap_overpass",
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("name"))
            amenity = self._text(record.get("amenity"))
            osm_id = self._text(record.get("osm_id"))
            if not title:
                continue
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=f"{record.get('osm_type', '')}:{osm_id}",
                    category=DiscoveryCategory.PLACE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=f"탐방 후보 · {amenity or 'public place'}",
                    content=None,
                    source_url=self._optional_text(record.get("website")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="부모가 지정한 위치 주변의 탐방 후보입니다.",
                    query="",
                    tags=["탐방", amenity] if amenity else ["탐방"],
                    metadata={
                        "osm_type": self._text(record.get("osm_type")),
                        "osm_id": osm_id,
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
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
                EducationDiscoveryService._suggestion(
                    source=source,
                    source_key=curriculum_id or title,
                    category=DiscoveryCategory.CURRICULUM,
                    resource_kind=ResourceKind.CURRICULUM,
                    title=title,
                    summary=summary,
                    content=standard or None,
                    source_url=EducationDiscoveryService._optional_text(record.get("source_url")),
                    author=None,
                    attribution=attribution,
                    license_note=license_note,
                    cache_status=cache_status,
                    rationale=(
                        f"'{query}'와 연결해 확인할 수 있는 교육과정 근거입니다."
                        if query
                        else "현재 단계에서 확인할 수 있는 공식 교육과정 근거입니다."
                    ),
                    query=query,
                    tags=[value for value in ("교육과정", subject, domain) if value],
                    metadata={"curriculum_id": curriculum_id, **safe_metadata},
                )
            )
        return suggestions

    @staticmethod
    def _suggestion(
        *,
        source: str,
        source_key: str,
        category: DiscoveryCategory,
        resource_kind: ResourceKind,
        title: str,
        summary: str | None,
        content: str | None,
        source_url: str | None,
        author: str | None,
        attribution: str,
        license_note: str,
        cache_status: str,
        rationale: str,
        query: str,
        tags: list[str],
        metadata: dict[str, str],
    ) -> DiscoverySuggestion:
        return DiscoverySuggestion(
            candidate_id=EducationDiscoveryService._candidate_id(source, source_key),
            category=category,
            resource_kind=resource_kind,
            title=title[:500],
            summary=(summary[:20_000] if summary else None),
            content=(content[:20_000] if content else None),
            source_name=source,
            source_url=source_url,
            author=author,
            attribution=attribution,
            license_note=license_note,
            cache_status=cache_status,
            rationale=rationale,
            query_term=query or None,
            tags=list(dict.fromkeys(tag[:200] for tag in tags if tag))[:30],
            metadata={key: value[:4_000] for key, value in metadata.items() if value},
        )

    @staticmethod
    def _rank(
        suggestions: list[DiscoverySuggestion],
        *,
        terms: list[str],
    ) -> list[DiscoverySuggestion]:
        category_priority = {
            DiscoveryCategory.CURRICULUM: 7,
            DiscoveryCategory.SCIENCE: 6,
            DiscoveryCategory.NATURE: 6,
            DiscoveryCategory.BOOK: 5,
            DiscoveryCategory.REFERENCE: 4,
            DiscoveryCategory.MEDIA: 3,
            DiscoveryCategory.PLACE: 2,
        }

        def score(item: DiscoverySuggestion) -> tuple[int, int, str]:
            haystack = " ".join([item.title, item.summary or "", *item.tags]).casefold()
            matches = sum(1 for term in terms if term.casefold() in haystack)
            return matches, category_priority[item.category], item.title

        by_id: dict[str, DiscoverySuggestion] = {}
        for suggestion in suggestions:
            by_id.setdefault(suggestion.candidate_id, suggestion)
        ordered = sorted(by_id.values(), key=score, reverse=True)

        # Keep the first page diverse enough for parents to compare source types rather than
        # allowing one broad catalog to flood every visible slot.
        diversified: list[DiscoverySuggestion] = []
        deferred: list[DiscoverySuggestion] = []
        source_counts: dict[str, int] = {}
        source_cap = 3
        for item in ordered:
            count = source_counts.get(item.source_name, 0)
            if count < source_cap:
                diversified.append(item)
                source_counts[item.source_name] = count + 1
            else:
                deferred.append(item)
        return [*diversified, *deferred]

    @staticmethod
    def _candidate_id(source: str, source_key: str) -> str:
        digest = hashlib.sha256(f"{source}\x1f{source_key}".encode()).hexdigest()[:24]
        return f"{source}:{digest}"

    def _collect_heritage(
        self,
        *,
        query: str,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        if self._needs_query(
            source=HeritagePalaceAdapter.SOURCE,
            query=query,
            source_states=source_states,
        ):
            return
        adapter = HeritagePalaceAdapter(
            cache=self.cache,
            endpoint=self.settings.heritage_palace_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.search(query=query, offline=offline)
        except ExternalAdapterError as exc:
            self._failed_source(
                source=HeritagePalaceAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records[: self.settings.discovery_source_result_limit]:
            title = self._text(record.get("title"))
            if not title:
                continue
            description = self._text(record.get("description"))
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.REFERENCE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=description[:1_500] or None,
                    content=description or None,
                    source_url=self._optional_text(record.get("source_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="한국사·문화 탐구에 연결할 국가유산청 공개 자료입니다.",
                    query=query,
                    tags=["역사", "문화", "국가유산"],
                    metadata={
                        "palace_number": self._text(record.get("palace_number")),
                        "image_url": self._text(record.get("image_url")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_museums(
        self,
        *,
        latitude: float | None,
        longitude: float | None,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        service_key = (self.settings.data_go_kr_service_key or "").strip()
        if not service_key:
            source_states.append(
                DiscoverySourceState(
                    source=MuseumArtGalleryAdapter.SOURCE,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if latitude is None or longitude is None:
            source_states.append(
                DiscoverySourceState(
                    source=MuseumArtGalleryAdapter.SOURCE,
                    enabled=True,
                    status="needs_location",
                )
            )
            return
        adapter = MuseumArtGalleryAdapter(
            service_key=service_key,
            cache=self.cache,
            endpoint=self.settings.museum_standard_endpoint,
            ttl_seconds=self.settings.public_enrichment_cache_ttl_seconds,
        )
        try:
            result = adapter.nearby(
                latitude=latitude,
                longitude=longitude,
                limit=self.settings.discovery_source_result_limit,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=MuseumArtGalleryAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records:
            title = self._text(record.get("title"))
            if not title:
                continue
            introduction = self._text(record.get("introduction"))
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")) or title,
                    category=DiscoveryCategory.PLACE,
                    resource_kind=ResourceKind.WEB,
                    title=title,
                    summary=introduction[:1_500] or self._optional_text(record.get("address")),
                    content=introduction or None,
                    source_url=self._optional_text(record.get("homepage_url")),
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="부모가 지정한 위치 주변의 박물관·미술관 탐방 후보입니다.",
                    query="",
                    tags=["탐방", "박물관", "미술관"],
                    metadata={
                        "address": self._text(record.get("address")),
                        "facility_type": self._text(record.get("facility_type")),
                        "closed_days": self._text(record.get("closed_days")),
                        "child_fee": self._text(record.get("child_fee")),
                        "institution": self._text(record.get("institution")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    def _collect_weather(
        self,
        *,
        public_terms: list[str],
        latitude: float | None,
        longitude: float | None,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        service_key = (self.settings.data_go_kr_service_key or "").strip()
        if not service_key:
            source_states.append(
                DiscoverySourceState(
                    source=KmaWeatherAdapter.SOURCE,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        if not set(public_terms) & _WEATHER_TERMS:
            source_states.append(
                DiscoverySourceState(
                    source=KmaWeatherAdapter.SOURCE,
                    enabled=True,
                    status="not_relevant",
                )
            )
            return
        if latitude is None or longitude is None:
            source_states.append(
                DiscoverySourceState(
                    source=KmaWeatherAdapter.SOURCE,
                    enabled=True,
                    status="needs_location",
                )
            )
            return
        adapter = KmaWeatherAdapter(
            service_key=service_key,
            cache=self.cache,
            endpoint=self.settings.kma_weather_endpoint,
            ttl_seconds=1_800,
        )
        try:
            result = adapter.current_conditions(
                latitude=latitude,
                longitude=longitude,
                offline=offline,
            )
        except ExternalAdapterError as exc:
            self._failed_source(
                source=KmaWeatherAdapter.SOURCE,
                exc=exc,
                source_states=source_states,
            )
            return
        for record in result.records[:1]:
            temperature = self._text(record.get("temperature_c"))
            humidity = self._text(record.get("humidity_pct"))
            rainfall = self._text(record.get("rainfall_mm"))
            details = [
                f"기온 {temperature}°C" if temperature else "",
                f"습도 {humidity}%" if humidity else "",
                f"1시간 강수량 {rainfall}mm" if rainfall else "",
            ]
            summary = " · ".join(value for value in details if value)
            suggestions.append(
                self._suggestion(
                    source=result.source,
                    source_key=self._text(record.get("id")),
                    category=DiscoveryCategory.SCIENCE,
                    resource_kind=ResourceKind.WEB,
                    title="현재 날씨 관찰 기록",
                    summary=summary or None,
                    content=summary or None,
                    source_url=None,
                    author=None,
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale="현재 날씨를 관찰·측정 활동과 연결할 수 있는 공공데이터입니다.",
                    query=" ".join(public_terms[:3]),
                    tags=["날씨", "과학", "관찰"],
                    metadata={
                        "temperature_c": temperature,
                        "humidity_pct": humidity,
                        "rainfall_mm": rainfall,
                        "precipitation_type": self._text(
                            record.get("precipitation_type")
                        ),
                        "wind_speed_ms": self._text(record.get("wind_speed_ms")),
                    },
                )
            )
        self._source_ready(
            result_source=result.source,
            cache_status=result.cache_status,
            source_states=source_states,
        )

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if value is not None else ""

    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        text = cls._text(value)
        return text or None
