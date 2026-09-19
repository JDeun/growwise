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
    GbifSpeciesAdapter,
    GoogleBooksAdapter,
    NasaImagesAdapter,
    OpenLibraryAdapter,
    OverpassAdapter,
    SQLiteExternalCache,
    WikidataAdapter,
    WikimediaCommonsAdapter,
    WikipediaAdapter,
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
        ("expires_at", "not-a-timestamp"),
    ],
)
def test_external_cache_corrupt_row_is_deleted(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    path = tmp_path / "external.sqlite3"
    cache = SQLiteExternalCache(path)
    cache.put(
        cache_key="corrupt",
        payload={"records": [{"id": 1}]},
        source="test",
        attribution="test attribution",
        license_note="test license",
        ttl_seconds=60,
    )

    with sqlite3.connect(path) as connection:
        connection.execute(
            f"UPDATE external_cache SET {column} = ? WHERE cache_key = ?",
            (value, "corrupt"),
        )

    assert cache.get("corrupt", allow_stale=True) is None
    with sqlite3.connect(path) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM external_cache WHERE cache_key = ?",
            ("corrupt",),
        ).fetchone()
    assert remaining is not None
    assert remaining[0] == 0


def test_external_cache_recreates_malformed_disposable_database(tmp_path: Path) -> None:
    path = tmp_path / "external.sqlite3"
    path.write_bytes(b"not-a-sqlite-database")

    cache = SQLiteExternalCache(path)
    cached = cache.put(
        cache_key="recovered",
        payload={"records": [{"id": 1}]},
        source="test",
        attribution="test attribution",
        license_note="test license",
        ttl_seconds=60,
    )

    assert cached.payload == {"records": [{"id": 1}]}
    assert cache.get("recovered") is not None



def test_openlibrary_normalizes_book_search(tmp_path: Path) -> None:
    http = FixtureHttp(
        {
            "docs": [
                {
                    "key": "/works/OL1W",
                    "title": "Dinosaurs",
                    "author_name": ["A. Author"],
                    "first_publish_year": 2020,
                    "subject": ["Dinosaurs", "Fossils"],
                    "isbn": ["9780000000002"],
                    "edition_count": 3,
                }
            ]
        }
    )
    adapter = OpenLibraryAdapter(
        cache=SQLiteExternalCache(tmp_path / "ol.sqlite3"),
        http=http,  # type: ignore[arg-type]
    )
    result = adapter.search_books(query="dinosaurs")
    assert result.records[0]["title"] == "Dinosaurs"
    assert result.records[0]["source_url"].endswith("/works/OL1W")


def test_google_books_normalizes_description_for_grounding(tmp_path: Path) -> None:
    http = FixtureHttp(
        {
            "items": [
                {
                    "id": "g1",
                    "volumeInfo": {
                        "title": "달 관찰",
                        "authors": ["저자"],
                        "description": "달의 위상과 표면을 설명한다.",
                        "categories": ["Science"],
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9780000000003"}
                        ],
                    },
                }
            ]
        }
    )
    adapter = GoogleBooksAdapter(
        cache=SQLiteExternalCache(tmp_path / "gb.sqlite3"),
        http=http,  # type: ignore[arg-type]
    )
    result = adapter.search_books(query="달")
    assert result.records[0]["description"] == "달의 위상과 표면을 설명한다."
    assert result.records[0]["isbn13"] == "9780000000003"


def test_nasa_images_exposes_description_and_image_url(tmp_path: Path) -> None:
    http = FixtureHttp(
        {
            "collection": {
                "items": [
                    {
                        "data": [
                            {
                                "nasa_id": "NASA-1",
                                "title": "The Moon",
                                "description": "A detailed view of lunar craters.",
                                "keywords": ["Moon", "crater"],
                            }
                        ],
                        "links": [
                            {"render": "image", "href": "https://images-assets.nasa.gov/moon.jpg"}
                        ],
                    }
                ]
            }
        }
    )
    adapter = NasaImagesAdapter(
        cache=SQLiteExternalCache(tmp_path / "nasa.sqlite3"),
        http=http,  # type: ignore[arg-type]
    )
    result = adapter.search(query="moon")
    assert result.records[0]["id"] == "NASA-1"
    assert "lunar craters" in result.records[0]["description"]
    assert result.records[0]["image_url"].startswith("https://")


def test_wikidata_and_wikipedia_normalize_reference_evidence(tmp_path: Path) -> None:
    wikidata = WikidataAdapter(
        cache=SQLiteExternalCache(tmp_path / "wd.sqlite3"),
        http=FixtureHttp(
            {
                "search": [
                    {
                        "id": "Q405",
                        "label": "달",
                        "description": "지구의 유일한 자연위성",
                        "concepturi": "https://www.wikidata.org/entity/Q405",
                    }
                ]
            }
        ),  # type: ignore[arg-type]
    )
    wiki = WikipediaAdapter(
        cache=SQLiteExternalCache(tmp_path / "wiki.sqlite3"),
        http=FixtureHttp(
            {
                "pages": [
                    {
                        "id": 1,
                        "key": "달",
                        "title": "달",
                        "description": "지구의 위성",
                        "excerpt": "<span>지구</span> 주위를 돈다.",
                    }
                ]
            }
        ),  # type: ignore[arg-type]
    )

    wd_result = wikidata.search(query="달")
    wiki_result = wiki.search(query="달")
    assert wd_result.records[0]["id"] == "Q405"
    assert wiki_result.records[0]["excerpt"] == "지구 주위를 돈다."


def test_gbif_normalizes_taxonomy(tmp_path: Path) -> None:
    adapter = GbifSpeciesAdapter(
        cache=SQLiteExternalCache(tmp_path / "gbif.sqlite3"),
        http=FixtureHttp(
            {
                "results": [
                    {
                        "key": 2435099,
                        "vernacularName": "고양이",
                        "scientificName": "Felis catus Linnaeus, 1758",
                        "canonicalName": "Felis catus",
                        "rank": "SPECIES",
                        "kingdom": "Animalia",
                        "family": "Felidae",
                    }
                ]
            }
        ),  # type: ignore[arg-type]
    )
    result = adapter.search(query="cat")
    assert result.records[0]["title"] == "고양이"
    assert result.records[0]["family"] == "Felidae"


def test_commons_drops_noncommercial_and_unknown_media(tmp_path: Path) -> None:
    payload = {
        "query": {
            "pages": [
                {
                    "pageid": 1,
                    "title": "File:Safe.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/safe.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Safe.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY 4.0"},
                                "ImageDescription": {"value": "Safe image"},
                            },
                        }
                    ],
                },
                {
                    "pageid": 2,
                    "title": "File:NC.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/nc.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-NC 4.0"},
                            },
                        }
                    ],
                },
                {
                    "pageid": 3,
                    "title": "File:Unknown.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/unknown.jpg",
                            "extmetadata": {},
                        }
                    ],
                },
            ]
        }
    }
    adapter = WikimediaCommonsAdapter(
        cache=SQLiteExternalCache(tmp_path / "commons.sqlite3"),
        http=FixtureHttp(payload),  # type: ignore[arg-type]
    )
    result = adapter.search_images(query="moon")
    assert [item["title"] for item in result.records] == ["Safe.jpg"]
    assert result.records[0]["license"] == "cc-by"
