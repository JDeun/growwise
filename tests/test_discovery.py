from __future__ import annotations

from pathlib import Path

from growwise.adapters import AdapterResult
from growwise.config import Settings
from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.rag import HybridRagIndex, ResourceIngestor
from growwise.services.discovery import EducationDiscoveryService
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


def test_external_book_search_receives_generic_terms_only(
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
        name="외부로 나가면 안 되는 이름",
        nickname="비밀별명",
        stage=Stage.ELEMENTARY,
        interests=["공룡", "우주"],
    )
    store.save(child)
    store.save(
        LearningLog(
            child_id=child.id,
            parent_observation="이 관찰 원문은 외부 API로 전달되면 안 된다.",
            tags=["화석"],
        )
    )

    result = service.discover(child=child)

    assert seen_keywords == ["공룡 우주 화석"]
    outbound = seen_keywords[0]
    assert child.name not in outbound
    assert (child.nickname or "") not in outbound
    assert "관찰 원문" not in outbound
    assert any(item.title == "공룡을 찾아서" for item in result.suggestions)
