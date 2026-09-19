from __future__ import annotations

from pathlib import Path

import pytest

from growwise.adapters import AdapterResult
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
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        embedding_features_enabled=False,
        vision_features_enabled=False,
        public_enrichment_enabled=False,
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
    assert any(
        state.source == "data4library" and state.status == "not_configured"
        for state in result.sources
    )

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
