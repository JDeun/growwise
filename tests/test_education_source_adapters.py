from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from growwise.adapters import (
    EDUCATION_SOURCE_CATALOG,
    GbifSpeciesAdapter,
    GlobalDigitalLibraryAdapter,
    GoogleBooksAdapter,
    KmaForecastAdapter,
    KoreanHeritageAdapter,
    KrdictAdapter,
    NasaMediaAdapter,
    NationalLibraryIsbnAdapter,
    NominatimAdapter,
    SQLiteExternalCache,
    TatoebaAdapter,
    WikidataAdapter,
    WikimediaCommonsAdapter,
    WikipediaAdapter,
)


class FakeJsonHttp:
    def __init__(
        self,
        *,
        object_payload: dict[str, Any] | None = None,
        list_payload: list[dict[str, Any]] | None = None,
        text_payload: str = "",
    ) -> None:
        self.object_payload = object_payload or {}
        self.list_payload = list_payload or []
        self.text_payload = text_payload
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_json(self, url: str, *, params):
        self.calls.append((url, dict(params)))
        return self.object_payload

    def get_json_list(self, url: str, *, params):
        self.calls.append((url, dict(params)))
        return self.list_payload

    def get_text(self, url: str, *, params):
        self.calls.append((url, dict(params)))
        return self.text_payload


def _cache(tmp_path: Path) -> SQLiteExternalCache:
    return SQLiteExternalCache(tmp_path / "external.sqlite3")


def test_original_education_source_matrix_is_codified() -> None:
    source_ids = {source.source_id for source in EDUCATION_SOURCE_CATALOG}
    expected = {
        "data4library",
        "national_library_isbn",
        "google_books",
        "open_library",
        "gutendex",
        "storyweaver",
        "global_digital_library",
        "standard_ebooks",
        "krdict",
        "opendict",
        "wordnet",
        "cmudict",
        "wordfreq",
        "kiwi",
        "spacy",
        "soynlp",
        "languagetool",
        "hunspell_ko",
        "tatoeba",
        "openstreetmap_nominatim",
        "openstreetmap_overpass",
        "opentopodata",
        "leaflet",
        "threejs",
        "wikidata",
        "wikipedia_ko",
        "wikimedia_commons",
        "korean_heritage",
        "emuseum",
        "nasa_images",
        "phet",
        "bioclip",
        "gbif_species",
        "kma_forecast",
        "kbr",
        "sympy",
        "manim",
        "jsxgraph",
        "mathjs",
        "illustrative_math_v1",
        "khan_academy_kids",
        "openstax",
    }
    assert expected <= source_ids
    assert len(source_ids) == len(EDUCATION_SOURCE_CATALOG)


def test_google_books_normalizes_bibliography(tmp_path: Path) -> None:
    http = FakeJsonHttp(
        object_payload={
            "items": [
                {
                    "id": "vol-1",
                    "volumeInfo": {
                        "title": "우주를 읽는 책",
                        "authors": ["테스트 저자"],
                        "publisher": "테스트 출판사",
                        "publishedDate": "2026",
                        "language": "ko",
                        "infoLink": "https://books.google.example/vol-1",
                        "industryIdentifiers": [
                            {"type": "ISBN_13", "identifier": "9780000000001"}
                        ],
                    },
                }
            ]
        }
    )
    result = GoogleBooksAdapter(
        cache=_cache(tmp_path),
        http=http,  # type: ignore[arg-type]
    ).search(query="우주")

    assert result.source == "google_books"
    assert result.records[0]["title"] == "우주를 읽는 책"
    assert result.records[0]["author"] == "테스트 저자"
    assert result.records[0]["metadata"]["isbn"] == "9780000000001"


def test_nasa_wikidata_wikipedia_and_gbif_normalize_public_results(tmp_path: Path) -> None:
    nasa = NasaMediaAdapter(
        cache=_cache(tmp_path / "nasa"),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "collection": {
                    "items": [
                        {
                            "href": "https://images-api.nasa.gov/asset/NASA1",
                            "data": [
                                {
                                    "nasa_id": "NASA1",
                                    "title": "Mars Surface",
                                    "description": "A Mars image",
                                    "keywords": ["Mars", "planet"],
                                }
                            ],
                            "links": [{"href": "https://images-assets.nasa.gov/image.jpg"}],
                        }
                    ]
                }
            }
        ),
    ).search(query="화성")
    assert nasa.records[0]["metadata"]["nasa_id"] == "NASA1"

    wikidata = WikidataAdapter(
        cache=_cache(tmp_path / "wikidata"),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "search": [
                    {
                        "id": "Q111",
                        "label": "화성",
                        "description": "태양계의 행성",
                        "concepturi": "https://www.wikidata.org/entity/Q111",
                    }
                ]
            }
        ),
    ).search(query="화성")
    assert wikidata.records[0]["title"] == "화성"
    assert wikidata.records[0]["metadata"]["entity_id"] == "Q111"

    wikipedia = WikipediaAdapter(
        cache=_cache(tmp_path / "wikipedia"),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "query": {
                    "search": [
                        {
                            "pageid": 42,
                            "title": "화성",
                            "snippet": "<span>태양계</span>의 네 번째 행성",
                        }
                    ]
                }
            }
        ),
    ).search(query="화성")
    assert wikipedia.records[0]["summary"] == "태양계의 네 번째 행성"

    gbif = GbifSpeciesAdapter(
        cache=_cache(tmp_path / "gbif"),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "results": [
                    {
                        "key": 1,
                        "scientificName": "Panthera tigris",
                        "vernacularName": "호랑이",
                        "kingdom": "Animalia",
                        "family": "Felidae",
                        "rank": "SPECIES",
                    }
                ]
            }
        ),
    ).search(query="호랑이")
    assert gbif.records[0]["title"] == "호랑이"
    assert gbif.records[0]["metadata"]["taxon_key"] == "1"


def test_wikimedia_commons_fails_closed_on_unsafe_or_missing_license(tmp_path: Path) -> None:
    http = FakeJsonHttp(
        object_payload={
            "query": {
                "pages": {
                    "1": {
                        "pageid": 1,
                        "title": "File:Safe.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/safe.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Safe.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY 4.0"},
                                    "Artist": {"value": "Author"},
                                },
                            }
                        ],
                    },
                    "2": {
                        "pageid": 2,
                        "title": "File:NC.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/nc.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-NC 4.0"}
                                },
                            }
                        ],
                    },
                    "3": {
                        "pageid": 3,
                        "title": "File:Unknown.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/unknown.jpg",
                                "extmetadata": {},
                            }
                        ],
                    },
                }
            }
        }
    )
    result = WikimediaCommonsAdapter(
        cache=_cache(tmp_path),
        http=http,  # type: ignore[arg-type]
    ).search(query="호랑이", limit=10)

    assert [item["title"] for item in result.records] == ["Safe.jpg"]
    assert result.records[0]["metadata"]["license"] == "CC BY 4.0"


def test_global_digital_library_filters_noncommercial_items(tmp_path: Path) -> None:
    payload = {
        "books": [
            {
                "postId": 1,
                "title": "Open Reader",
                "description": "reading",
                "postLink": "https://digitallibrary.io/open",
                "license": [{"name": "CC BY 4.0"}],
            },
            {
                "postId": 2,
                "title": "NC Reader",
                "license": [{"name": "CC BY-NC 4.0"}],
            },
        ]
    }
    result = GlobalDigitalLibraryAdapter(
        cache=_cache(tmp_path),
        http=FakeJsonHttp(object_payload=payload),  # type: ignore[arg-type]
    ).search(query="읽기", limit=10)

    assert [item["title"] for item in result.records] == ["Open Reader"]


def test_nominatim_accepts_array_root_via_bounded_http_contract(tmp_path: Path) -> None:
    http = FakeJsonHttp(
        list_payload=[
            {
                "osm_type": "node",
                "osm_id": 123,
                "display_name": "국립과학관, 대한민국",
                "type": "museum",
                "lat": "37.0",
                "lon": "127.0",
            }
        ]
    )
    result = NominatimAdapter(
        cache=_cache(tmp_path),
        http=http,  # type: ignore[arg-type]
    ).search(query="과학관")

    assert result.records[0]["title"] == "국립과학관, 대한민국"
    assert result.records[0]["metadata"]["latitude"] == "37.0"


def test_korean_heritage_and_krdict_parse_bounded_xml(tmp_path: Path) -> None:
    heritage_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <result><item>
      <ccbaMnm1>수원 화성</ccbaMnm1>
      <ccbaKdcd>11</ccbaKdcd><ccbaAsno>0003</ccbaAsno><ccbaCtcd>31</ccbaCtcd>
      <ccmaName>사적</ccmaName><ccbaCtcdNm>경기도</ccbaCtcdNm><ccsiName>수원시</ccsiName>
    </item></result>"""
    heritage = KoreanHeritageAdapter(
        cache=_cache(tmp_path / "heritage"),
        http=FakeJsonHttp(text_payload=heritage_xml),  # type: ignore[arg-type]
    ).search(query="수원")
    assert heritage.records[0]["title"] == "수원 화성"
    assert heritage.records[0]["metadata"]["district"] == "수원시"

    krdict_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <channel><item>
      <target_code>100</target_code><word>우주</word><pos>명사</pos>
      <sense><definition>모든 천체가 존재하는 공간.</definition></sense>
    </item></channel>"""
    krdict = KrdictAdapter(
        api_key="SECRET-KEY",
        cache=_cache(tmp_path / "krdict"),
        http=FakeJsonHttp(text_payload=krdict_xml),  # type: ignore[arg-type]
    ).search(query="우주")
    assert krdict.records[0]["summary"] == "모든 천체가 존재하는 공간."


def test_national_library_key_is_not_persisted_in_cache(tmp_path: Path) -> None:
    cache_path = tmp_path / "external.sqlite3"
    secret = "VERY-SECRET-NL-KEY"
    adapter = NationalLibraryIsbnAdapter(
        cert_key=secret,
        cache=SQLiteExternalCache(cache_path),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "docs": [
                    {
                        "TITLE": "테스트 도서",
                        "EA_ISBN": "9780000000002",
                        "AUTHOR": "저자",
                    }
                ]
            }
        ),
    )
    result = adapter.search(query="테스트")
    assert result.records[0]["title"] == "테스트 도서"

    with sqlite3.connect(cache_path) as connection:
        rows = connection.execute("SELECT cache_key, payload_json FROM external_cache").fetchall()
    assert secret not in "\n".join(f"{key}\n{payload}" for key, payload in rows)


def test_tatoeba_normalizes_sentence_and_translation(tmp_path: Path) -> None:
    result = TatoebaAdapter(
        cache=_cache(tmp_path),
        http=FakeJsonHttp(  # type: ignore[arg-type]
            object_payload={
                "data": [
                    {
                        "id": 9,
                        "lang": "kor",
                        "text": "별을 관찰해요.",
                        "translations": [[{"text": "We observe the stars."}]],
                    }
                ]
            }
        ),
    ).search(query="별")

    assert result.records[0]["title"] == "별을 관찰해요."
    assert result.records[0]["summary"] == "We observe the stars."


def test_kma_location_request_normalizes_first_forecast_without_leaking_key(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "external.sqlite3"
    secret = "KMA-SECRET"
    http = FakeJsonHttp(
        object_payload={
            "response": {
                "body": {
                    "items": {
                        "item": [
                            {
                                "fcstDate": "20260919",
                                "fcstTime": "1200",
                                "category": "TMP",
                                "fcstValue": "24",
                            },
                            {
                                "fcstDate": "20260919",
                                "fcstTime": "1200",
                                "category": "SKY",
                                "fcstValue": "1",
                            },
                            {
                                "fcstDate": "20260919",
                                "fcstTime": "1200",
                                "category": "POP",
                                "fcstValue": "10",
                            },
                        ]
                    }
                }
            }
        }
    )
    result = KmaForecastAdapter(
        service_key=secret,
        cache=SQLiteExternalCache(cache_path),
        http=http,  # type: ignore[arg-type]
    ).search_location(latitude=37.2636, longitude=127.0286)

    assert "기온 24℃" in (result.records[0]["summary"] or "")
    assert "맑음" in (result.records[0]["summary"] or "")
    assert http.calls[0][1]["serviceKey"] == secret

    with sqlite3.connect(cache_path) as connection:
        rows = connection.execute("SELECT cache_key, payload_json FROM external_cache").fetchall()
    assert secret not in "\n".join(f"{key}\n{payload}" for key, payload in rows)
