from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from growwise.adapters import (
    Data4LibraryAdapter,
    ExternalAdapterError,
    ExternalUnavailable,
    OverpassAdapter,
    SQLiteExternalCache,
)

FIXTURES = Path(__file__).parent / "fixtures" / "external"


class FixtureHttp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, *, params):
        self.calls.append((url, dict(params)))
        return self.payload

    def post_form_json(self, url: str, *, form):
        self.calls.append((url, dict(form)))
        return self.payload


class FailingHttp:
    def get_json(self, url: str, *, params):
        raise ExternalAdapterError("offline")

    def post_form_json(self, url: str, *, form):
        raise ExternalAdapterError("offline")


def _fixture(name: str) -> dict[str, Any]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_external_cache_distinguishes_fresh_and_stale(tmp_path) -> None:
    cache = SQLiteExternalCache(tmp_path / "external.sqlite3")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    cache.put(
        cache_key="example",
        payload={"records": [{"id": 1}]},
        source="test",
        attribution="test attribution",
        license_note="test license",
        ttl_seconds=10,
        now=now,
    )

    fresh = cache.get("example", now=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC))
    assert fresh is not None and fresh.stale is False
    assert cache.get("example", now=datetime(2026, 1, 1, 0, 0, 11, tzinfo=UTC)) is None
    stale = cache.get(
        "example",
        allow_stale=True,
        now=datetime(2026, 1, 1, 0, 0, 11, tzinfo=UTC),
    )
    assert stale is not None and stale.stale is True


def test_overpass_uses_fixture_then_fresh_cache_without_second_request(tmp_path) -> None:
    cache = SQLiteExternalCache(tmp_path / "external.sqlite3")
    http = FixtureHttp(_fixture("overpass-nearby.json"))
    adapter = OverpassAdapter(cache=cache, http=http)  # type: ignore[arg-type]

    live = adapter.nearby_places(latitude=37.5665, longitude=126.978)
    cached = adapter.nearby_places(latitude=37.5665, longitude=126.978)

    assert live.cache_status == "live"
    assert cached.cache_status == "fresh"
    assert len(http.calls) == 1
    assert {item["amenity"] for item in live.records} == {"library", "museum"}
    assert live.attribution == "© OpenStreetMap contributors"


def test_overpass_offline_mode_uses_stale_cache_and_never_calls_network(tmp_path) -> None:
    cache = SQLiteExternalCache(tmp_path / "external.sqlite3")
    descriptor = {
        "lat": 37.5665,
        "lon": 126.978,
        "radius_m": 2000,
        "amenities": ("community_centre", "library", "museum"),
    }
    cache.put(
        cache_key=OverpassAdapter._cache_key(descriptor),
        payload={"records": [{"name": "cached", "amenity": "library"}]},
        source=OverpassAdapter.SOURCE,
        attribution=OverpassAdapter.ATTRIBUTION,
        license_note=OverpassAdapter.LICENSE_NOTE,
        ttl_seconds=1,
        now=datetime(2020, 1, 1, tzinfo=UTC),
    )
    adapter = OverpassAdapter(cache=cache, http=FailingHttp())  # type: ignore[arg-type]

    result = adapter.nearby_places(latitude=37.5665, longitude=126.978, offline=True)
    assert result.cache_status == "stale"
    assert result.records[0]["name"] == "cached"


def test_overpass_rejects_arbitrary_tag_regex_input(tmp_path) -> None:
    adapter = OverpassAdapter(cache=SQLiteExternalCache(tmp_path / "external.sqlite3"))
    with pytest.raises(ValueError, match="unsupported amenity"):
        adapter.nearby_places(
            latitude=37.5,
            longitude=127.0,
            amenities=("library|.*",),
        )


def test_data4library_search_uses_json_fixture_and_does_not_cache_auth_key(tmp_path) -> None:
    cache_path = tmp_path / "external.sqlite3"
    cache = SQLiteExternalCache(cache_path)
    http = FixtureHttp(_fixture("data4library-search.json"))
    secret = "test-secret-auth-key"
    adapter = Data4LibraryAdapter(
        auth_key=secret,
        cache=cache,
        http=http,  # type: ignore[arg-type]
    )

    live = adapter.search_books(keyword="역사")
    cached = adapter.search_books(keyword="역사")

    assert live.cache_status == "live"
    assert cached.cache_status == "fresh"
    assert live.records[0]["isbn13"] == "9780000000001"
    assert len(http.calls) == 1
    assert http.calls[0][1]["authKey"] == secret

    with sqlite3.connect(cache_path) as connection:
        rows = connection.execute("SELECT cache_key, payload_json FROM external_cache").fetchall()
    persisted = "\n".join(f"{key}\n{payload}" for key, payload in rows)
    assert secret not in persisted


def test_data4library_stale_fallback_on_network_failure(tmp_path) -> None:
    cache = SQLiteExternalCache(tmp_path / "external.sqlite3")
    descriptor = {"keyword": "역사", "page": 1, "page_size": 10}
    cache.put(
        cache_key=Data4LibraryAdapter._cache_key(descriptor),
        payload={"records": [{"title": "cached history"}]},
        source=Data4LibraryAdapter.SOURCE,
        attribution=Data4LibraryAdapter.ATTRIBUTION,
        license_note=Data4LibraryAdapter.LICENSE_NOTE,
        ttl_seconds=1,
        now=datetime(2020, 1, 1, tzinfo=UTC),
    )
    adapter = Data4LibraryAdapter(
        auth_key="not-persisted",
        cache=cache,
        http=FailingHttp(),  # type: ignore[arg-type]
    )

    result = adapter.search_books(keyword="역사")
    assert result.cache_status == "stale"
    assert result.records == [{"title": "cached history"}]


def test_offline_cache_miss_is_explicit(tmp_path) -> None:
    adapter = OverpassAdapter(
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=FailingHttp(),  # type: ignore[arg-type]
    )
    with pytest.raises(ExternalUnavailable):
        adapter.nearby_places(latitude=37.5, longitude=127.0, offline=True)



@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("payload_json", "{not-json"),
        ("payload_json", "[]"),
        ("fetched_at", "not-a-timestamp"),
        ("expires_at", "not-a-timestamp"),
    ],
)
def test_external_cache_corruption_degrades_to_miss_and_self_heals(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    cache_path = tmp_path / "external.sqlite3"
    cache = SQLiteExternalCache(cache_path)
    cache.put(
        cache_key="corrupt",
        payload={"records": [{"id": 1}]},
        source="test",
        attribution="test attribution",
        license_note="test license",
        ttl_seconds=60,
    )
    with sqlite3.connect(cache_path) as connection:
        connection.execute(
            f"UPDATE external_cache SET {column} = ? WHERE cache_key = ?",
            (value, "corrupt"),
        )

    assert cache.get("corrupt", allow_stale=True) is None
    with sqlite3.connect(cache_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM external_cache WHERE cache_key = ?",
            ("corrupt",),
        ).fetchone()
    assert count is not None and count[0] == 0
