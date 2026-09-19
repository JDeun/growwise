from __future__ import annotations

from pathlib import Path

import pytest

from growwise.adapters import AdapterResult, ExternalAdapterError
from growwise.config import Settings
from growwise.domain import ActivityPlan, ChildProfile, LearningLog, ResourceKind, Stage
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.discovery import DiscoverySuggestion, EducationDiscoveryService
from growwise.services.public_query import generalize_public_terms, translate_public_terms
from growwise.storage import EntityStore


def _service(tmp_path: Path, **settings_overrides: object) -> tuple[
    EducationDiscoveryService,
    EntityStore,
]:
    settings_overrides.setdefault("public_enrichment_enabled", False)
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
        vision_features_enabled=False,
        **settings_overrides,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    service = EducationDiscoveryService(
        settings=settings,
        store=store,
        ingestor=ResourceIngestor(HybridRagIndex(settings.rag_index_path)),
    )
    return service, store


def test_discovery_has_offline_curriculum_baseline_and_deduplicated_save(
    tmp_path: Path,
) -> None:
    service, store = _service(tmp_path)
    child = ChildProfile(
        name="테스트 아이",
        nickname="별이",
        stage=Stage.INFANT_0_2,
        interests=["동물", "그림책"],
    )
    store.save(child)
    store.save(
        LearningLog(
            child_id=child.id,
            parent_observation="고양이 그림을 오래 바라봤다.",
            tags=["고양이", "책"],
            interest="고양이",
        )
    )

    result = service.discover(child=child, offline=True)

    assert "별이" not in result.query
    assert str(child.id) not in result.query
    assert "고양이 그림을 오래 바라봤다" not in result.query
    assert {item.category.value for item in result.suggestions} >= {"curriculum"}
    states = {state.source: state.status for state in result.sources}
    assert states["data4library"] == "not_configured"
    assert states["national_library_isbn"] == "not_configured"
    assert states["krdict"] == "not_configured"
    assert states["curated_education_catalog"] == "live"
    assert states["korea_museum_standard"] == "not_configured"
    assert states["kma_weather"] == "not_configured"
    assert states["korean_heritage_palaces"] == "disabled"

    suggestion = result.suggestions[0]
    first = service.save(child=child, suggestion=suggestion)
    second = service.save(child=child, suggestion=suggestion)
    assert first.id == second.id
    assert first.provenance["discovery_candidate_id"] == suggestion.candidate_id



def test_discovery_retry_reconciles_missing_rag_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service, store = _service(tmp_path)
    child = ChildProfile(name="테스트", nickname="테스트", stage=Stage.ELEMENTARY)
    store.save(child)
    suggestion = DiscoverySuggestion(
        candidate_id="candidate-reconcile",
        category="book",
        resource_kind=ResourceKind.BOOK,
        title="공룡 관찰 기록",
        summary="공룡 화석을 관찰하는 참고 자료",
        source_name="synthetic",
        attribution="synthetic test",
        license_note="test-only",
        cache_status="fresh",
        rationale="테스트",
    )

    original_ingest = service.ingestor.ingest
    failed = False

    def fail_once(resource):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("simulated RAG ingest crash")
        return original_ingest(resource)

    monkeypatch.setattr(service.ingestor, "ingest", fail_once)
    with pytest.raises(OSError, match="simulated RAG ingest crash"):
        service.save(child=child, suggestion=suggestion)

    authoritative = [
        item
        for item in store.index.list_entities(
            entity_type="resource",
            child_id=str(child.id),
        )
        if (item.get("provenance") or {}).get("discovery_candidate_id")
        == suggestion.candidate_id
    ]
    assert len(authoritative) == 1

    monkeypatch.setattr(service.ingestor, "ingest", original_ingest)
    recovered = service.save(child=child, suggestion=suggestion)
    assert str(recovered.id) == authoritative[0]["id"]

    hits = HybridRagIndex(tmp_path / "rag.sqlite3").search(
        query="공룡 화석",
        child_id=str(child.id),
        limit=10,
    )
    assert hits


def test_external_book_search_receives_allowlisted_topics_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen_keywords: list[str] = []

    class FakeData4LibraryAdapter:
        SOURCE = "data4library"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_books(
            self,
            *,
            keyword: str,
            page: int = 1,
            page_size: int = 10,
            offline: bool = False,
        ) -> AdapterResult:
            del page, page_size, offline
            seen_keywords.append(keyword)
            return AdapterResult(
                source="data4library",
                records=[
                    {
                        "title": "공룡을 찾아서",
                        "authors": "테스트 저자",
                        "publisher": "테스트 출판사",
                        "isbn13": "9780000000000",
                    }
                ],
                attribution="도서관 정보나루",
                license_note="테스트 이용조건",
            )

    monkeypatch.setattr(
        "growwise.services.discovery.Data4LibraryAdapter",
        FakeData4LibraryAdapter,
    )
    service, store = _service(tmp_path, data4library_api_key="test-key")
    child = ChildProfile(
        name="PRIVATE_NAME_MARKER",
        nickname="PRIVATE_NICKNAME_MARKER",
        stage=Stage.ELEMENTARY,
        interests=["공룡", "PRIVATE_INTEREST_MARKER", "우주"],
        learning_goals=["PRIVATE_GOAL_MARKER"],
    )
    store.save(child)
    store.save(
        LearningLog(
            child_id=child.id,
            parent_observation="PRIVATE_OBSERVATION_MARKER",
            interest="PRIVATE_LOG_INTEREST_MARKER",
            tags=["화석", "PRIVATE_TAG_MARKER"],
        )
    )
    store.save(
        ActivityPlan(
            child_id=child.id,
            title="PRIVATE_ACTIVITY_MARKER 박물관에서 공룡을 관찰",
        )
    )

    result = service.discover(child=child)

    assert seen_keywords == ["공룡 우주 화석"]
    outbound = seen_keywords[0]
    assert result.query == outbound
    assert result.query_terms[:3] == ["공룡", "우주", "화석"]
    assert all("PRIVATE_" not in value for value in [outbound, *result.query_terms])
    assert any(item.title == "공룡을 찾아서" for item in result.suggestions)


def test_explicit_discovery_query_is_generalized_before_external_use(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen_keywords: list[str] = []

    class FakeData4LibraryAdapter:
        SOURCE = "data4library"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_books(
            self,
            *,
            keyword: str,
            page: int = 1,
            page_size: int = 10,
            offline: bool = False,
        ) -> AdapterResult:
            del page, page_size, offline
            seen_keywords.append(keyword)
            return AdapterResult(
                source="data4library",
                records=[],
                attribution="도서관 정보나루",
                license_note="테스트 이용조건",
            )

    monkeypatch.setattr(
        "growwise.services.discovery.Data4LibraryAdapter",
        FakeData4LibraryAdapter,
    )
    service, store = _service(tmp_path, data4library_api_key="test-key")
    child = ChildProfile(
        name="PRIVATE_NAME_MARKER",
        stage=Stage.ELEMENTARY,
    )
    store.save(child)

    result = service.discover(
        child=child,
        query="PRIVATE_QUERY_MARKER 박물관에서 공룡을 찾아보기",
    )

    assert seen_keywords == ["박물관 공룡"]
    assert result.query == "박물관 공룡"
    assert "PRIVATE_QUERY_MARKER" not in result.query


def test_public_topic_projection_does_not_treat_nickname_fragment_as_topic() -> None:
    assert generalize_public_terms(["별이와 공룡을 함께 보기"]) == ["공룡"]
    assert generalize_public_terms(["PRIVATE_ONLY_MARKER"]) == []



def test_public_topic_translation_only_maps_allowlisted_terms() -> None:
    canonical = generalize_public_terms(["PRIVATE_MARKER 우주와 공룡"])
    assert canonical == ["우주", "공룡"]
    assert translate_public_terms(canonical, language="en") == ["space", "dinosaurs"]
    assert "PRIVATE_MARKER" not in " ".join(
        translate_public_terms(canonical, language="en")
    )


def test_discovery_save_persists_evidence_content_for_material_grounding(
    tmp_path: Path,
) -> None:
    service, store = _service(tmp_path)
    child = ChildProfile(name="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    suggestion = DiscoverySuggestion(
        candidate_id="nasa_images:moon-test",
        category="science",
        resource_kind=ResourceKind.WEB,
        title="Moon observation",
        summary="달 표면을 관찰하는 NASA 자료",
        content="달 표면에는 충돌구와 밝고 어두운 지형이 보인다.",
        source_name="nasa_images",
        source_url="https://images.nasa.gov/details/test",
        attribution="NASA",
        license_note="test public-domain note",
        cache_status="live",
        rationale="과학 관찰 근거",
        tags=["NASA", "달"],
    )

    saved = service.save(child=child, suggestion=suggestion)
    assert saved.content == suggestion.content
    assert saved.summary == suggestion.summary
    assert saved.provenance["discovery_source"] == "nasa_images"
    assert saved.provenance["discovery_category"] == "science"


def test_public_source_fanout_receives_only_allowlisted_queries(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seen: list[tuple[str, str]] = []

    class FakeOpenLibrary:
        SOURCE = "open_library"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_books(self, *, query: str, limit: int, offline: bool) -> AdapterResult:
            del limit, offline
            seen.append((self.SOURCE, query))
            return AdapterResult(
                source=self.SOURCE,
                records=[],
                attribution="test",
                license_note="test",
            )

    class FakeGoogleBooks:
        SOURCE = "google_books"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_books(
            self,
            *,
            query: str,
            limit: int,
            offline: bool,
        ) -> AdapterResult:
            del limit, offline
            seen.append((self.SOURCE, query))
            return AdapterResult(
                source=self.SOURCE,
                records=[],
                attribution="test",
                license_note="test",
            )

    class FakeSearch:
        def __init__(self, source: str, **_kwargs: object) -> None:
            self.SOURCE = source

        def search(self, *, query: str, limit: int, offline: bool) -> AdapterResult:
            del limit, offline
            seen.append((self.SOURCE, query))
            return AdapterResult(
                source=self.SOURCE,
                records=[],
                attribution="test",
                license_note="test",
            )

    class FakeWikipedia(FakeSearch):
        SOURCE = "wikipedia_ko"

        def __init__(self, **kwargs: object) -> None:
            super().__init__(self.SOURCE, **kwargs)

    class FakeWikidata(FakeSearch):
        SOURCE = "wikidata"

        def __init__(self, **kwargs: object) -> None:
            super().__init__(self.SOURCE, **kwargs)

    class FakeNasa(FakeSearch):
        SOURCE = "nasa_images"

        def __init__(self, **kwargs: object) -> None:
            super().__init__(self.SOURCE, **kwargs)

    class FakeGbif(FakeSearch):
        SOURCE = "gbif_species"

        def __init__(self, **kwargs: object) -> None:
            super().__init__(self.SOURCE, **kwargs)

    class FakeCommons:
        SOURCE = "wikimedia_commons"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_images(
            self,
            *,
            query: str,
            limit: int,
            offline: bool,
        ) -> AdapterResult:
            del limit, offline
            seen.append((self.SOURCE, query))
            return AdapterResult(
                source=self.SOURCE,
                records=[],
                attribution="test",
                license_note="test",
            )

    monkeypatch.setattr("growwise.services.discovery.OpenLibraryAdapter", FakeOpenLibrary)
    monkeypatch.setattr("growwise.services.discovery.GoogleBooksAdapter", FakeGoogleBooks)
    monkeypatch.setattr("growwise.services.discovery.WikipediaAdapter", FakeWikipedia)
    monkeypatch.setattr("growwise.services.discovery.WikidataAdapter", FakeWikidata)
    monkeypatch.setattr("growwise.services.discovery.NasaImagesAdapter", FakeNasa)
    monkeypatch.setattr("growwise.services.discovery.GbifSpeciesAdapter", FakeGbif)
    monkeypatch.setattr("growwise.services.discovery.WikimediaCommonsAdapter", FakeCommons)

    service, store = _service(
        tmp_path,
        public_enrichment_enabled=True,
    )
    child = ChildProfile(
        name="PRIVATE_CHILD",
        nickname="PRIVATE_NICK",
        stage=Stage.ELEMENTARY,
        interests=["우주", "공룡", "PRIVATE_INTEREST"],
    )
    store.save(child)
    result = service.discover(
        child=child,
        query="PRIVATE_QUERY 아이와 우주 공룡을 관찰",
    )

    assert result.query == "우주 공룡 관찰"
    assert seen
    outbound = " ".join(query for _source, query in seen)
    assert "PRIVATE_" not in outbound
    assert child.name not in outbound
    assert str(child.id) not in outbound
    assert ("nasa_images", "space dinosaurs observation") in seen

def test_discovery_calls_configured_korean_book_and_dictionary_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeNationalLibrary:
        SOURCE = "national_library_isbn"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search_books(self, *, query: str, limit: int, offline: bool) -> AdapterResult:
            assert query == "독서 언어"
            assert limit > 0
            assert offline is False
            return AdapterResult(
                source=self.SOURCE,
                records=[
                    {
                        "id": "isbn-1",
                        "title": "읽기와 언어",
                        "author": "저자",
                        "isbn13": "9780000000003",
                        "source_url": "https://www.nl.go.kr/",
                    }
                ],
                attribution="국립중앙도서관",
                license_note="test",
                cache_status="live",
            )

    class FakeKrDict:
        SOURCE = "krdict"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search(self, *, query: str, limit: int, offline: bool) -> AdapterResult:
            assert query == "독서 언어"
            assert limit > 0
            assert offline is False
            return AdapterResult(
                source=self.SOURCE,
                records=[
                    {
                        "id": "word-1",
                        "title": "언어",
                        "definitions": ["생각을 나타내고 전달하는 수단."],
                        "source_url": "https://krdict.korean.go.kr/",
                    }
                ],
                attribution="한국어기초사전",
                license_note="test",
                cache_status="live",
            )

    monkeypatch.setattr(
        "growwise.services.discovery.NationalLibraryIsbnAdapter",
        FakeNationalLibrary,
    )
    monkeypatch.setattr("growwise.services.discovery.KrDictAdapter", FakeKrDict)

    service, store = _service(
        tmp_path,
        national_library_api_key="test-national-key",
        krdict_api_key="test-krdict-key",
    )
    child = ChildProfile(
        name="테스트",
        stage=Stage.ELEMENTARY,
        interests=["독서", "언어"],
    )
    store.save(child)

    result = service.discover(child=child, query="독서 언어")
    sources = {item.source_name for item in result.suggestions}
    states = {state.source: state.status for state in result.sources}

    assert "national_library_isbn" in sources
    assert "krdict" in sources
    assert states["national_library_isbn"] == "live"
    assert states["krdict"] == "live"


def test_discovery_calls_configured_location_sources_without_persisting_coordinates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, tuple[float, float]] = {}

    class FakeMuseum:
        SOURCE = "korea_museum_standard"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def nearby(
            self,
            *,
            latitude: float,
            longitude: float,
            limit: int,
            offline: bool,
        ) -> AdapterResult:
            seen["museum"] = (latitude, longitude)
            assert limit > 0
            assert offline is False
            return AdapterResult(
                source=self.SOURCE,
                records=[
                    {
                        "id": "museum-1",
                        "title": "어린이 박물관",
                        "address": "테스트 주소",
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                ],
                attribution="공공데이터포털",
                license_note="test",
                cache_status="live",
            )

    class FakeWeather:
        SOURCE = "kma_weather"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def current_conditions(
            self,
            *,
            latitude: float,
            longitude: float,
            offline: bool,
        ) -> AdapterResult:
            seen["weather"] = (latitude, longitude)
            assert offline is False
            return AdapterResult(
                source=self.SOURCE,
                records=[
                    {
                        "id": "weather-1",
                        "temperature_c": "23",
                        "humidity_pct": "50",
                        "rainfall_mm": "0",
                    }
                ],
                attribution="기상청",
                license_note="test",
                cache_status="live",
            )

    monkeypatch.setattr("growwise.services.discovery.MuseumArtGalleryAdapter", FakeMuseum)
    monkeypatch.setattr("growwise.services.discovery.KmaWeatherAdapter", FakeWeather)

    service, store = _service(
        tmp_path,
        data_go_kr_service_key="test-service-key",
    )
    child = ChildProfile(
        name="테스트",
        stage=Stage.ELEMENTARY,
        interests=["날씨", "박물관"],
    )
    store.save(child)

    result = service.discover(
        child=child,
        query="날씨 박물관",
        latitude=37.25,
        longitude=127.02,
    )

    assert seen == {
        "museum": (37.25, 127.02),
        "weather": (37.25, 127.02),
    }
    assert all(
        "37.25" not in suggestion.metadata.values()
        and "127.02" not in suggestion.metadata.values()
        for suggestion in result.suggestions
    )

def test_connected_source_collectors_cover_state_boundaries(
    tmp_path: Path,
) -> None:
    service, _store = _service(
        tmp_path,
        national_library_api_key="configured",
        krdict_api_key="configured",
        data_go_kr_service_key="configured",
    )

    suggestions: list[DiscoverySuggestion] = []
    states = []
    service._collect_national_library(
        query="",
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )
    service._collect_krdict(
        query="",
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )
    service._collect_curated_catalog(
        public_terms=[],
        suggestions=suggestions,
        source_states=states,
    )
    service._collect_museums(
        latitude=None,
        longitude=None,
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )
    service._collect_weather(
        public_terms=["독서"],
        latitude=37.5,
        longitude=127.0,
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )
    service._collect_weather(
        public_terms=["날씨"],
        latitude=None,
        longitude=None,
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )

    status_by_source = {state.source: state.status for state in states}
    assert status_by_source["national_library_isbn"] == "needs_query"
    assert status_by_source["krdict"] == "needs_query"
    assert status_by_source["curated_education_catalog"] == "needs_query"
    assert status_by_source["korea_museum_standard"] == "needs_location"
    assert status_by_source["kma_weather"] == "needs_location"


def test_heritage_collector_surfaces_results_and_isolates_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeHeritage:
        SOURCE = "korean_heritage_palaces"

        def __init__(self, **_kwargs: object) -> None:
            pass

        def search(self, *, query: str, offline: bool) -> AdapterResult:
            assert query == "역사"
            assert offline is False
            return AdapterResult(
                source=self.SOURCE,
                records=[
                    {
                        "id": "1:1:A",
                        "title": "근정전",
                        "description": "조선 궁궐의 중심 건물",
                        "palace_number": "1",
                        "image_url": "https://example.org/image.jpg",
                        "source_url": "https://www.heritage.go.kr/",
                    }
                ],
                attribution="국가유산청",
                license_note="test",
                cache_status="live",
            )

    monkeypatch.setattr(
        "growwise.services.discovery.HeritagePalaceAdapter",
        FakeHeritage,
    )
    service, _store = _service(tmp_path, public_enrichment_enabled=True)
    suggestions: list[DiscoverySuggestion] = []
    states = []
    service._collect_heritage(
        query="역사",
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )

    assert suggestions[0].title == "근정전"
    assert suggestions[0].metadata["palace_number"] == "1"
    assert states[0].status == "live"

    class FailingHeritage(FakeHeritage):
        def search(self, *, query: str, offline: bool) -> AdapterResult:
            del query, offline
            raise ExternalAdapterError("heritage unavailable")

    monkeypatch.setattr(
        "growwise.services.discovery.HeritagePalaceAdapter",
        FailingHeritage,
    )
    suggestions = []
    states = []
    service._collect_heritage(
        query="역사",
        suggestions=suggestions,
        source_states=states,
        offline=False,
    )
    assert suggestions == []
    assert states[0].status == "unavailable"
    assert states[0].detail == "heritage unavailable"

