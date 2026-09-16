from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import growwise.api.main as api
from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.services.infant import (
    CURRICULUM_SOURCE,
    BoardBookRecommendationService,
    InfantCurriculumDomain,
    InfantObservationHintService,
)
from growwise.storage import EntityStore


class HostileObservationHintProvider:
    def generate_text(self, *, system: str, user: str) -> str:
        return "unused"

    def generate_structured(self, *, system: str, user: str, schema: type[Any]) -> Any:
        return schema.model_validate(
            {
                "source": "invented",
                "diagnostic": True,
                "hints": [
                    {
                        "domain": domain.value,
                        "cue": (
                            "또래보다 뒤처졌고 자폐 진단이 필요합니다."
                            if domain is InfantCurriculumDomain.COMMUNICATION
                            else f"{domain.value}에서 아이가 관심을 보이는 순간을 살펴봅니다."
                        ),
                        "rationale": "관찰 기록",
                    }
                    for domain in InfantCurriculumDomain
                ],
            }
        )


def _store(tmp_path):
    return EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")


def test_observation_hints_cover_five_curriculum_domains_without_diagnosis() -> None:
    result = InfantObservationHintService(provider=HostileObservationHintProvider()).suggest(
        age_months=9,
        recent_observations=["동물 그림을 오래 바라봄"],
        interests=["고양이"],
    )

    assert result.source == CURRICULUM_SOURCE
    assert result.diagnostic is False
    assert {hint.domain for hint in result.hints} == set(InfantCurriculumDomain)
    rendered = " ".join(f"{hint.cue} {hint.rationale}" for hint in result.hints).casefold()
    assert "자폐" not in rendered
    assert "진단" not in rendered
    assert "또래보다" not in rendered


def test_infant_guidance_api_is_child_scoped_and_has_offline_book_fallback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    child = ChildProfile(
        nickname="영아",
        stage=Stage.INFANT_0_2,
        age_months=9,
        interests=["고양이"],
    )
    other = ChildProfile(
        nickname="다른 아이",
        stage=Stage.INFANT_0_2,
        age_months=12,
        interests=["고양이"],
    )
    store.save(child)
    store.save(other)
    global_book = ResourceRecord(
        kind=ResourceKind.BOOK,
        title="고양이 그림 보드북",
        summary="고양이의 표정과 움직임을 크게 보여주는 책",
        tags=["고양이", "그림책"],
        stage_tags=[Stage.INFANT_0_2],
    )
    other_private_book = ResourceRecord(
        child_id=other.id,
        kind=ResourceKind.BOOK,
        title="다른 아이의 고양이 책",
        tags=["고양이"],
        stage_tags=[Stage.INFANT_0_2],
    )
    store.save(global_book)
    store.save(other_private_book)
    monkeypatch.setattr(api, "get_model_provider", lambda: None)
    monkeypatch.delenv("GROWWISE_DATA4LIBRARY_API_KEY", raising=False)

    hints = api.suggest_infant_observation_hints(child.id, store)
    assert hints["diagnostic"] is False
    assert len(hints["hints"]) == 5

    books = api.recommend_board_books(child.id, store, limit=5)
    returned_ids = {
        item["resource_id"]
        for item in books["recommendations"]
        if item["resource_id"] is not None
    }
    assert str(global_book.id) in returned_ids
    assert str(other_private_book.id) not in returned_ids

    empty_store = _store(tmp_path / "empty")
    empty_child = ChildProfile(
        nickname="오프라인 영아",
        stage=Stage.INFANT_0_2,
        age_months=8,
        interests=["동물"],
    )
    empty_store.save(empty_child)
    fallback = api.recommend_board_books(empty_child.id, empty_store, limit=3)
    assert len(fallback["recommendations"]) == 3
    assert all(
        item["source"] == "local_library_or_offline_fallback"
        for item in fallback["recommendations"]
    )


def test_board_book_discovery_sends_only_generalized_interest_query(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: dict[str, object] = {}

    class FakeData4LibraryAdapter:
        def __init__(self, **kwargs: object) -> None:
            observed["init"] = kwargs

        def search_books(self, *, keyword: str, page_size: int, offline: bool):
            observed["keyword"] = keyword
            observed["page_size"] = page_size
            observed["offline"] = offline
            return SimpleNamespace(
                source="data4library",
                records=[
                    {
                        "title": "고양이와 인사해요",
                        "isbn13": "9780000000001",
                        "book_detail_url": "https://example.invalid/book/1",
                    }
                ],
            )

    monkeypatch.setenv("GROWWISE_DATA4LIBRARY_API_KEY", "test-key")
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path / "app-data"))
    monkeypatch.setattr("growwise.adapters.Data4LibraryAdapter", FakeData4LibraryAdapter)

    result = BoardBookRecommendationService().recommend(
        resources=[],
        interests=["고양이", "동물", "세 번째 관심사"],
        limit=2,
    )

    assert observed["keyword"] == "고양이 동물 그림책"
    assert observed["offline"] is False
    assert result.recommendations[0].source == "public_discovery"
    assert result.recommendations[0].resource_id is None
    assert result.recommendations[0].discovery_candidate_id is not None
    assert result.recommendations[0].source_url == "https://example.invalid/book/1"
    assert "적합성" in result.recommendations[0].reason
    assert result.recommendations[1].source == "local_library_or_offline_fallback"


def test_infant_guidance_rejects_non_infant_stage(tmp_path) -> None:
    store = _store(tmp_path)
    child = ChildProfile(nickname="초등", stage=Stage.ELEMENTARY, age_months=96)
    store.save(child)

    with pytest.raises(HTTPException) as exc_info:
        api.recommend_board_books(child.id, store, limit=3)
    assert exc_info.value.status_code == 409
