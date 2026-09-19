from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import StrEnum
from typing import Any
from uuid import uuid5

from pydantic import BaseModel, Field

from growwise.adapters import (
    EDUCATION_SOURCE_CATALOG,
    ConfiguredPublicDataAdapter,
    Data4LibraryAdapter,
    ExternalAdapterError,
    GbifSpeciesAdapter,
    GlobalDigitalLibraryAdapter,
    GoogleBooksAdapter,
    GutendexAdapter,
    JsonHttpClient,
    KmaForecastAdapter,
    KoreanHeritageAdapter,
    KrdictAdapter,
    NasaMediaAdapter,
    NationalLibraryIsbnAdapter,
    NominatimAdapter,
    OfficialKoreanCurriculumCatalogAdapter,
    OpenDictAdapter,
    OpenTopoDataAdapter,
    OverpassAdapter,
    PublicCurriculumAdapter,
    SQLiteExternalCache,
    SourceIntegrationMode,
    TatoebaAdapter,
    WikidataAdapter,
    WikimediaCommonsAdapter,
    WikipediaAdapter,
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
    REFERENCE = "reference"
    SCIENCE = "science"
    LANGUAGE = "language"
    MEDIA = "media"


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
    label: str | None = None
    domain: str | None = None
    mode: str | None = None
    homepage: str | None = None


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
        self._collect_extended_sources(
            query=public_query,
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
            sources=self._finalize_source_states(source_states),
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
            id=uuid5(child.id, f"growwise:discovery:{suggestion.candidate_id}"),
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

    def _http(self) -> JsonHttpClient:
        return JsonHttpClient(timeout_seconds=self.settings.external_source_timeout_seconds)

    def _search_kwargs(self, endpoint: str) -> dict[str, Any]:
        return {
            "cache": self.cache,
            "http": self._http(),
            "endpoint": endpoint,
            "ttl_seconds": self.settings.external_source_cache_ttl_seconds,
        }

    def _collect_extended_sources(
        self,
        *,
        query: str,
        latitude: float | None,
        longitude: float | None,
        suggestions: list[DiscoverySuggestion],
        source_states: list[DiscoverySourceState],
        offline: bool,
    ) -> None:
        """Collect independent public sources concurrently.

        Text sent outside the device is already reduced to allow-listed public terms.
        Coordinates are used only when the parent explicitly supplied them to Discovery.
        """

        extended_ids = (
            "google_books",
            "gutendex",
            "global_digital_library",
            "national_library_isbn",
            "nasa_images",
            "wikidata",
            "wikipedia_ko",
            "wikimedia_commons",
            "gbif_species",
            "tatoeba",
            "openstreetmap_nominatim",
            "opentopodata",
            "korean_heritage",
            "krdict",
            "opendict",
            "kma_forecast",
            "emuseum",
            "kbr",
        )
        if not self.settings.external_live_sources_enabled:
            source_states.extend(
                DiscoverySourceState(source=source_id, enabled=False, status="disabled")
                for source_id in extended_ids
            )
            return

        tasks: list[tuple[str, DiscoveryCategory, Callable[[], Any]]] = []

        if query:
            tasks.extend(
                [
                    (
                        "google_books",
                        DiscoveryCategory.BOOK,
                        lambda: GoogleBooksAdapter(
                            **self._search_kwargs(self.settings.google_books_endpoint)
                        ).search(query=query, limit=6, offline=offline),
                    ),
                    (
                        "gutendex",
                        DiscoveryCategory.BOOK,
                        lambda: GutendexAdapter(
                            **self._search_kwargs(self.settings.gutendex_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "global_digital_library",
                        DiscoveryCategory.BOOK,
                        lambda: GlobalDigitalLibraryAdapter(
                            **self._search_kwargs(
                                self.settings.global_digital_library_endpoint
                            )
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "nasa_images",
                        DiscoveryCategory.SCIENCE,
                        lambda: NasaMediaAdapter(
                            **self._search_kwargs(self.settings.nasa_images_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "wikidata",
                        DiscoveryCategory.REFERENCE,
                        lambda: WikidataAdapter(
                            **self._search_kwargs(self.settings.wikidata_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "wikipedia_ko",
                        DiscoveryCategory.REFERENCE,
                        lambda: WikipediaAdapter(
                            **self._search_kwargs(self.settings.wikipedia_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "wikimedia_commons",
                        DiscoveryCategory.MEDIA,
                        lambda: WikimediaCommonsAdapter(
                            **self._search_kwargs(
                                self.settings.wikimedia_commons_endpoint
                            )
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "gbif_species",
                        DiscoveryCategory.SCIENCE,
                        lambda: GbifSpeciesAdapter(
                            **self._search_kwargs(self.settings.gbif_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "tatoeba",
                        DiscoveryCategory.LANGUAGE,
                        lambda: TatoebaAdapter(
                            **self._search_kwargs(self.settings.tatoeba_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "openstreetmap_nominatim",
                        DiscoveryCategory.PLACE,
                        lambda: NominatimAdapter(
                            **self._search_kwargs(self.settings.nominatim_endpoint)
                        ).search(query=query, limit=5, offline=offline),
                    ),
                    (
                        "korean_heritage",
                        DiscoveryCategory.PLACE,
                        lambda: KoreanHeritageAdapter(
                            **self._search_kwargs(
                                self.settings.korean_heritage_endpoint
                            )
                        ).search(query=query, limit=5, offline=offline),
                    ),
                ]
            )
            self._append_keyed_text_tasks(
                tasks=tasks,
                source_states=source_states,
                query=query,
                offline=offline,
            )
        else:
            source_states.extend(
                DiscoverySourceState(
                    source=source_id,
                    enabled=True,
                    status="needs_query",
                )
                for source_id in (
                    "google_books",
                    "gutendex",
                    "global_digital_library",
                    "nasa_images",
                    "wikidata",
                    "wikipedia_ko",
                    "wikimedia_commons",
                    "gbif_species",
                    "tatoeba",
                    "openstreetmap_nominatim",
                    "korean_heritage",
                )
            )
            self._append_keyed_missing_query_states(source_states)

        self._append_location_tasks(
            tasks=tasks,
            source_states=source_states,
            latitude=latitude,
            longitude=longitude,
            offline=offline,
        )

        if not tasks:
            return

        max_workers = min(self.settings.discovery_max_parallel_sources, len(tasks))
        with ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="growwise-discovery",
        ) as executor:
            future_map = {
                executor.submit(fetch): (source_id, category)
                for source_id, category, fetch in tasks
            }
            for future in as_completed(future_map):
                source_id, category = future_map[future]
                try:
                    result = future.result()
                except ExternalAdapterError:
                    source_states.append(
                        DiscoverySourceState(
                            source=source_id,
                            enabled=True,
                            status="unavailable",
                            detail="공개 데이터 소스 요청에 실패했습니다.",
                        )
                    )
                    continue
                except Exception:
                    source_states.append(
                        DiscoverySourceState(
                            source=source_id,
                            enabled=True,
                            status="unavailable",
                            detail="공개 데이터 소스를 처리하지 못했습니다.",
                        )
                    )
                    continue
                suggestions.extend(
                    self._normalized_suggestions(
                        result=result,
                        category=category,
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

    def _append_keyed_text_tasks(
        self,
        *,
        tasks: list[tuple[str, DiscoveryCategory, Callable[[], Any]]],
        source_states: list[DiscoverySourceState],
        query: str,
        offline: bool,
    ) -> None:
        national_key = (self.settings.national_library_api_key or "").strip()
        if national_key:
            tasks.append(
                (
                    "national_library_isbn",
                    DiscoveryCategory.BOOK,
                    lambda: NationalLibraryIsbnAdapter(
                        cert_key=national_key,
                        **self._search_kwargs(self.settings.national_library_endpoint),
                    ).search(query=query, limit=6, offline=offline),
                )
            )
        else:
            source_states.append(
                DiscoverySourceState(
                    source="national_library_isbn",
                    enabled=False,
                    status="not_configured",
                )
            )

        krdict_key = (self.settings.krdict_api_key or "").strip()
        if krdict_key:
            tasks.append(
                (
                    "krdict",
                    DiscoveryCategory.LANGUAGE,
                    lambda: KrdictAdapter(
                        api_key=krdict_key,
                        **self._search_kwargs(self.settings.krdict_endpoint),
                    ).search(query=query, limit=5, offline=offline),
                )
            )
        else:
            source_states.append(
                DiscoverySourceState(
                    source="krdict",
                    enabled=False,
                    status="not_configured",
                )
            )

        opendict_key = (self.settings.opendict_api_key or "").strip()
        if opendict_key:
            tasks.append(
                (
                    "opendict",
                    DiscoveryCategory.LANGUAGE,
                    lambda: OpenDictAdapter(
                        api_key=opendict_key,
                        cert_key_no=self.settings.opendict_cert_key_no,
                        **self._search_kwargs(self.settings.opendict_endpoint),
                    ).search(query=query, limit=5, offline=offline),
                )
            )
        else:
            source_states.append(
                DiscoverySourceState(
                    source="opendict",
                    enabled=False,
                    status="not_configured",
                )
            )

        public_key = (self.settings.public_data_api_key or "").strip()
        self._append_configured_public_data_task(
            tasks=tasks,
            source_states=source_states,
            source_id="emuseum",
            endpoint=self.settings.emuseum_endpoint,
            query_param=self.settings.emuseum_query_param,
            query=query,
            api_key=public_key,
            category=DiscoveryCategory.REFERENCE,
            attribution="국립중앙박물관 e뮤지엄",
            license_note="공공데이터 및 개별 유물/이미지 권리표시를 확인할 것",
            offline=offline,
        )
        self._append_configured_public_data_task(
            tasks=tasks,
            source_states=source_states,
            source_id="kbr",
            endpoint=self.settings.kbr_endpoint,
            query_param=self.settings.kbr_query_param,
            query=query,
            api_key=public_key,
            category=DiscoveryCategory.SCIENCE,
            attribution="국립생물자원관",
            license_note="텍스트 메타데이터 중심; 이미지 재사용 권리는 별도 확인할 것",
            offline=offline,
        )

    def _append_keyed_missing_query_states(
        self,
        source_states: list[DiscoverySourceState],
    ) -> None:
        checks = (
            (
                "national_library_isbn",
                bool((self.settings.national_library_api_key or "").strip()),
            ),
            ("krdict", bool((self.settings.krdict_api_key or "").strip())),
            ("opendict", bool((self.settings.opendict_api_key or "").strip())),
            (
                "emuseum",
                bool((self.settings.public_data_api_key or "").strip())
                and bool(self.settings.emuseum_endpoint),
            ),
            (
                "kbr",
                bool((self.settings.public_data_api_key or "").strip())
                and bool(self.settings.kbr_endpoint),
            ),
        )
        source_states.extend(
            DiscoverySourceState(
                source=source_id,
                enabled=configured,
                status="needs_query" if configured else "not_configured",
            )
            for source_id, configured in checks
        )

    def _append_configured_public_data_task(
        self,
        *,
        tasks: list[tuple[str, DiscoveryCategory, Callable[[], Any]]],
        source_states: list[DiscoverySourceState],
        source_id: str,
        endpoint: str | None,
        query_param: str,
        query: str,
        api_key: str,
        category: DiscoveryCategory,
        attribution: str,
        license_note: str,
        offline: bool,
    ) -> None:
        if not endpoint or not api_key:
            source_states.append(
                DiscoverySourceState(
                    source=source_id,
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        tasks.append(
            (
                source_id,
                category,
                lambda: ConfiguredPublicDataAdapter(
                    source=source_id,
                    attribution=attribution,
                    license_note=license_note,
                    service_key=api_key,
                    query_param=query_param,
                    **self._search_kwargs(endpoint),
                ).search(query=query, limit=5, offline=offline),
            )
        )

    def _append_location_tasks(
        self,
        *,
        tasks: list[tuple[str, DiscoveryCategory, Callable[[], Any]]],
        source_states: list[DiscoverySourceState],
        latitude: float | None,
        longitude: float | None,
        offline: bool,
    ) -> None:
        if latitude is None or longitude is None:
            source_states.append(
                DiscoverySourceState(
                    source="opentopodata",
                    enabled=True,
                    status="needs_location",
                )
            )
            kma_configured = bool((self.settings.public_data_api_key or "").strip())
            source_states.append(
                DiscoverySourceState(
                    source="kma_forecast",
                    enabled=kma_configured,
                    status="needs_location" if kma_configured else "not_configured",
                )
            )
            return

        tasks.append(
            (
                "opentopodata",
                DiscoveryCategory.PLACE,
                lambda: OpenTopoDataAdapter(
                    **self._search_kwargs(self.settings.opentopodata_endpoint)
                ).search_location(
                    latitude=latitude,
                    longitude=longitude,
                    offline=offline,
                ),
            )
        )

        public_key = (self.settings.public_data_api_key or "").strip()
        if not public_key:
            source_states.append(
                DiscoverySourceState(
                    source="kma_forecast",
                    enabled=False,
                    status="not_configured",
                )
            )
            return
        tasks.append(
            (
                "kma_forecast",
                DiscoveryCategory.SCIENCE,
                lambda: KmaForecastAdapter(
                    service_key=public_key,
                    cache=self.cache,
                    http=self._http(),
                    endpoint=self.settings.kma_endpoint,
                    ttl_seconds=min(
                        self.settings.external_source_cache_ttl_seconds,
                        10_800,
                    ),
                ).search_location(
                    latitude=latitude,
                    longitude=longitude,
                    offline=offline,
                ),
            )
        )

    @classmethod
    def _normalized_suggestions(
        cls,
        *,
        result: Any,
        category: DiscoveryCategory,
        query: str,
    ) -> list[DiscoverySuggestion]:
        suggestions: list[DiscoverySuggestion] = []
        for record in result.records:
            if not isinstance(record, dict):
                continue
            title = cls._text(record.get("title"))
            if not title:
                continue
            source_key = cls._text(record.get("source_key")) or title
            raw_kind = cls._text(record.get("resource_kind"))
            resource_kind = (
                ResourceKind.BOOK if raw_kind == ResourceKind.BOOK.value else ResourceKind.WEB
            )
            raw_tags = record.get("tags")
            tags = (
                [cls._text(value) for value in raw_tags if cls._text(value)]
                if isinstance(raw_tags, list)
                else []
            )
            metadata = record.get("metadata")
            safe_metadata = (
                {
                    str(key)[:200]: str(value)[:1_000]
                    for key, value in metadata.items()
                    if isinstance(key, str) and value is not None
                }
                if isinstance(metadata, dict)
                else {}
            )
            suggestions.append(
                DiscoverySuggestion(
                    candidate_id=cls._candidate_id(result.source, source_key),
                    category=category,
                    resource_kind=resource_kind,
                    title=title,
                    summary=cls._optional_text(record.get("summary")),
                    source_name=result.source,
                    source_url=cls._optional_text(record.get("url")),
                    author=cls._optional_text(record.get("author")),
                    attribution=result.attribution,
                    license_note=result.license_note,
                    cache_status=result.cache_status,
                    rationale=cls._rationale(category=category, query=query),
                    query_term=query or None,
                    tags=list(dict.fromkeys([*tags, *query.split()[:3]]))[:30],
                    metadata=safe_metadata,
                )
            )
        return suggestions

    @staticmethod
    def _rationale(*, category: DiscoveryCategory, query: str) -> str:
        label = {
            DiscoveryCategory.BOOK: "도서",
            DiscoveryCategory.CURRICULUM: "교육과정",
            DiscoveryCategory.PLACE: "탐방",
            DiscoveryCategory.REFERENCE: "백과·역사",
            DiscoveryCategory.SCIENCE: "과학·자연",
            DiscoveryCategory.LANGUAGE: "언어·어휘",
            DiscoveryCategory.MEDIA: "공개 미디어",
        }[category]
        if query:
            return f"'{query}'와 연결된 {label} 공개 자료 후보입니다."
        return f"현재 맥락과 연결할 수 있는 {label} 공개 자료 후보입니다."

    def _finalize_source_states(
        self,
        states: list[DiscoverySourceState],
    ) -> list[DiscoverySourceState]:
        by_source = {state.source: state for state in states}
        ordered: list[DiscoverySourceState] = []

        for spec in EDUCATION_SOURCE_CATALOG:
            current = by_source.pop(spec.source_id, None)
            configured = (
                bool(getattr(self.settings, spec.requires_setting, None))
                if spec.requires_setting
                else True
            )
            if spec.source_id in {"emuseum", "kbr"}:
                endpoint = (
                    self.settings.emuseum_endpoint
                    if spec.source_id == "emuseum"
                    else self.settings.kbr_endpoint
                )
                configured = configured and bool(endpoint)

            if current is None:
                status_by_mode = {
                    SourceIntegrationMode.CURATED_LINK: "catalog_link",
                    SourceIntegrationMode.OFFLINE_DATASET: "offline_dataset",
                    SourceIntegrationMode.LOCAL_ENGINE: "local_optional",
                    SourceIntegrationMode.RENDERER: "renderer",
                    SourceIntegrationMode.KEYED_API: (
                        "configured" if configured else "not_configured"
                    ),
                    SourceIntegrationMode.LIVE_API: (
                        "available"
                        if self.settings.external_live_sources_enabled
                        else "disabled"
                    ),
                }
                current = DiscoverySourceState(
                    source=spec.source_id,
                    enabled=configured
                    and (
                        spec.mode != SourceIntegrationMode.LIVE_API
                        or self.settings.external_live_sources_enabled
                    ),
                    status=status_by_mode[spec.mode],
                )

            current.label = spec.label
            current.domain = spec.domain
            current.mode = spec.mode.value
            current.homepage = spec.homepage
            ordered.append(current)

        ordered.extend(sorted(by_source.values(), key=lambda state: state.source))
        return ordered

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
            DiscoveryCategory.BOOK: 7,
            DiscoveryCategory.CURRICULUM: 6,
            DiscoveryCategory.SCIENCE: 5,
            DiscoveryCategory.LANGUAGE: 4,
            DiscoveryCategory.REFERENCE: 3,
            DiscoveryCategory.PLACE: 2,
            DiscoveryCategory.MEDIA: 1,
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
