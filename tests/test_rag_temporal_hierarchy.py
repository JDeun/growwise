from __future__ import annotations

from datetime import date

from growwise.rag import HybridRagIndex, chunk_resource


def _chunks(resource_id: str, child_id: str, text: str, recorded_at: str | None):
    return chunk_resource(
        resource_id=resource_id,
        child_id=child_id,
        title=resource_id,
        text=text,
        source_url=None,
        source_name=None,
        tags=["고양이"],
        recorded_at=recorded_at,
    )


def test_search_fills_current_month_then_current_year_then_archive(tmp_path) -> None:
    index = HybridRagIndex(tmp_path / "rag.sqlite3")
    child_id = "child-1"
    index.replace_resource(
        _chunks("archive", child_id, "고양이 고양이 고양이 과거 기록", "2025-12-20T10:00:00+00:00")
    )
    index.replace_resource(
        _chunks("year", child_id, "고양이 고양이 올해 기록", "2026-02-20T10:00:00+00:00")
    )
    index.replace_resource(
        _chunks("month", child_id, "고양이 이번 달 기록", "2026-09-01T10:00:00+00:00")
    )

    hits = index.search(
        query="고양이",
        child_id=child_id,
        limit=3,
        reference_date=date(2026, 9, 16),
    )

    assert [hit["resource_id"] for hit in hits] == ["month", "year", "archive"]
    assert [hit["temporal_tier"] for hit in hits] == [
        "current_month",
        "current_year",
        "archive",
    ]


def test_unknown_timestamp_cannot_outrank_dated_archive(tmp_path) -> None:
    index = HybridRagIndex(tmp_path / "rag.sqlite3")
    index.replace_resource(_chunks("unknown", "child-1", "고양이 고양이", None))
    index.replace_resource(
        _chunks("archive", "child-1", "고양이", "2024-01-01T00:00:00+00:00")
    )

    hits = index.search(
        query="고양이",
        child_id="child-1",
        limit=2,
        reference_date=date(2026, 9, 16),
    )

    assert [hit["resource_id"] for hit in hits] == ["archive", "unknown"]


def test_delete_child_keeps_global_and_other_child_chunks(tmp_path) -> None:
    index = HybridRagIndex(tmp_path / "rag.sqlite3")
    index.replace_resource(_chunks("a", "child-a", "고양이", "2026-09-01T00:00:00+00:00"))
    index.replace_resource(_chunks("b", "child-b", "고양이", "2026-09-01T00:00:00+00:00"))
    index.replace_resource(_chunks("global", None, "고양이", "2026-09-01T00:00:00+00:00"))

    assert index.delete_child("child-a") == 1
    hits = index.search(
        query="고양이",
        child_id="child-b",
        limit=10,
        reference_date=date(2026, 9, 16),
    )
    ids = {hit["resource_id"] for hit in hits}
    assert "a" not in ids
    assert {"b", "global"}.issubset(ids)
