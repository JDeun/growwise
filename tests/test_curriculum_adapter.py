from __future__ import annotations

from pathlib import Path

import pytest

from growwise.adapters import ExternalUnavailable, PublicCurriculumAdapter, SQLiteExternalCache


class StubHttp:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def get_json(self, endpoint: str, *, params: dict[str, str]) -> dict[str, object]:
        self.calls.append(params)
        return self.payload


def test_curriculum_adapter_normalizes_and_caches(tmp_path: Path) -> None:
    cache = SQLiteExternalCache(tmp_path / "external.sqlite3")
    http = StubHttp(
        {
            "records": [
                {
                    "code": "SCI-01",
                    "title": "주변의 생물을 관찰하고 특징을 설명한다",
                    "school_level": "elementary",
                    "subject": "science",
                    "domain": "life",
                    "competency": "inquiry",
                    "url": "https://example.invalid/curriculum/SCI-01",
                    "revision": "2022",
                }
            ]
        }
    )
    adapter = PublicCurriculumAdapter(
        endpoint="https://example.invalid/api", cache=cache, http=http
    )

    result = adapter.search(stage="elementary", subject="science", query="생물")

    assert result.cache_status == "live"
    assert result.records[0]["curriculum_id"] == "SCI-01"
    assert result.records[0]["domain"] == "life"
    assert result.records[0]["metadata"] == {"revision": "2022"}
    assert http.calls == [{"stage": "elementary", "subject": "science", "query": "생물"}]

    cached = adapter.search(stage="elementary", subject="science", query="생물", offline=True)
    assert cached.cache_status == "fresh"
    assert cached.records == result.records
    assert len(http.calls) == 1


def test_curriculum_adapter_offline_without_cache_fails_closed(tmp_path: Path) -> None:
    adapter = PublicCurriculumAdapter(
        endpoint="https://example.invalid/api",
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=StubHttp({"records": []}),
    )

    with pytest.raises(ExternalUnavailable):
        adapter.search(stage="middle", subject="math", offline=True)


def test_curriculum_adapter_ignores_malformed_records(tmp_path: Path) -> None:
    payload = {
        "data": {
            "items": [None, {}, {"title": "제목만"}, {"stage": "elementary"}]
        }
    }
    adapter = PublicCurriculumAdapter(
        endpoint="https://example.invalid/api",
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=StubHttp(payload),
    )

    result = adapter.search(stage="elementary")
    assert result.records == []


def test_curriculum_query_is_bounded(tmp_path: Path) -> None:
    adapter = PublicCurriculumAdapter(
        endpoint="https://example.invalid/api",
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=StubHttp({"records": []}),
    )

    with pytest.raises(ValueError):
        adapter.search(stage="")
    with pytest.raises(ValueError):
        adapter.search(stage="elementary", query="x" * 201)
