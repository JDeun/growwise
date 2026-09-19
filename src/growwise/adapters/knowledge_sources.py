from __future__ import annotations

import html
import re
from typing import Any

from .license_filter import is_commercial_safe
from .search_base import CachedSearchAdapter

_TAG_RE = re.compile(r"<[^>]+>")


def _plain(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    return html.unescape(_TAG_RE.sub("", text)).strip()


class NasaMediaAdapter(CachedSearchAdapter):
    SOURCE = "nasa_images"
    ATTRIBUTION = "NASA Image and Video Library"
    LICENSE_NOTE = (
        "NASA media are generally U.S. Government works; NASA insignia/logos and third-party "
        "materials may have separate restrictions. Keep NASA attribution and source metadata."
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://images-api.nasa.gov/search")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {"q": query, "media_type": "image", "page_size": min(limit, 100)}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        collection = self.dict_value(payload.get("collection"))
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(collection.get("items"))[:limit]:
            data = self.list_of_dicts(item.get("data"))
            if not data:
                continue
            meta = data[0]
            title = self.text(meta.get("title"))
            if not title:
                continue
            links = self.list_of_dicts(item.get("links"))
            preview = self.text(links[0].get("href")) if links else ""
            keywords = meta.get("keywords")
            keyword_values = (
                [self.text(value) for value in keywords if self.text(value)]
                if isinstance(keywords, list)
                else []
            )
            records.append(
                {
                    "source_key": self.text(meta.get("nasa_id")) or title,
                    "title": title,
                    "summary": self.text(meta.get("description"))[:4_000] or None,
                    "url": self.text(item.get("href")) or preview or None,
                    "author": self.text(
                        meta.get("photographer") or meta.get("secondary_creator")
                    )
                    or None,
                    "resource_kind": "web",
                    "tags": ["과학", "우주", "NASA", *keyword_values[:4]],
                    "metadata": {
                        key: value
                        for key, value in {
                            "nasa_id": self.text(meta.get("nasa_id")),
                            "date_created": self.text(meta.get("date_created")),
                            "center": self.text(meta.get("center")),
                            "preview_url": preview,
                        }.items()
                        if value
                    },
                }
            )
        return records


class WikidataAdapter(CachedSearchAdapter):
    SOURCE = "wikidata"
    ATTRIBUTION = "Wikidata contributors"
    LICENSE_NOTE = "Wikidata structured data is CC0 1.0"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://www.wikidata.org/w/api.php")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "action": "wbsearchentities",
            "search": query,
            "language": "ko",
            "uselang": "ko",
            "format": "json",
            "limit": min(limit, 50),
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("search"))[:limit]:
            label = self.text(item.get("label"))
            entity_id = self.text(item.get("id"))
            if not label or not entity_id:
                continue
            records.append(
                {
                    "source_key": entity_id,
                    "title": label,
                    "summary": self.text(item.get("description")) or None,
                    "url": self.text(item.get("concepturi")) or f"https://www.wikidata.org/wiki/{entity_id}",
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["백과", "사실", "Wikidata"],
                    "metadata": {"entity_id": entity_id},
                }
            )
        return records


class WikipediaAdapter(CachedSearchAdapter):
    SOURCE = "wikipedia_ko"
    ATTRIBUTION = "Wikipedia contributors"
    LICENSE_NOTE = "Wikipedia text is CC BY-SA; follow article attribution/share-alike requirements"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://ko.wikipedia.org/w/api.php")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": min(limit, 50),
            "format": "json",
            "utf8": 1,
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        query = self.dict_value(payload.get("query"))
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(query.get("search"))[:limit]:
            title = self.text(item.get("title"))
            page_id = self.text(item.get("pageid"))
            if not title:
                continue
            records.append(
                {
                    "source_key": page_id or title,
                    "title": title,
                    "summary": _plain(item.get("snippet"))[:4_000] or None,
                    "url": f"https://ko.wikipedia.org/?curid={page_id}" if page_id else None,
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["백과", "Wikipedia"],
                    "metadata": {"page_id": page_id} if page_id else {},
                }
            )
        return records


class WikimediaCommonsAdapter(CachedSearchAdapter):
    SOURCE = "wikimedia_commons"
    ATTRIBUTION = "Wikimedia Commons contributors / individual file authors"
    LICENSE_NOTE = "Only files with commercial-safe item-level licenses are surfaced"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://commons.wikimedia.org/w/api.php")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(limit, 50),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "format": "json",
        }

    @staticmethod
    def _meta_value(metadata: dict[str, Any], key: str) -> str:
        raw = metadata.get(key)
        if isinstance(raw, dict):
            raw = raw.get("value")
        return _plain(raw)

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        query = self.dict_value(payload.get("query"))
        pages = query.get("pages")
        if not isinstance(pages, dict):
            return []
        records: list[dict[str, Any]] = []
        for page in pages.values():
            if not isinstance(page, dict):
                continue
            infos = self.list_of_dicts(page.get("imageinfo"))
            if not infos:
                continue
            info = infos[0]
            metadata = self.dict_value(info.get("extmetadata"))
            license_name = (
                self._meta_value(metadata, "LicenseShortName")
                or self._meta_value(metadata, "UsageTerms")
            )
            if not license_name or not is_commercial_safe(license_name):
                continue
            title = self.text(page.get("title")).removeprefix("File:").strip()
            if not title:
                continue
            records.append(
                {
                    "source_key": self.text(page.get("pageid")) or title,
                    "title": title,
                    "summary": self._meta_value(metadata, "ImageDescription")[:4_000] or None,
                    "url": self.text(info.get("descriptionurl") or info.get("url")) or None,
                    "author": self._meta_value(metadata, "Artist") or None,
                    "resource_kind": "web",
                    "tags": ["이미지", "Wikimedia Commons"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "license": license_name,
                            "credit": self._meta_value(metadata, "Credit"),
                            "media_url": self.text(info.get("url")),
                        }.items()
                        if value
                    },
                }
            )
            if len(records) >= limit:
                break
        return records


class GbifSpeciesAdapter(CachedSearchAdapter):
    SOURCE = "gbif_species"
    ATTRIBUTION = "GBIF.org"
    LICENSE_NOTE = (
        "GBIF taxonomic metadata is surfaced without reusing occurrence-media files; individual "
        "dataset/media licenses must be checked separately before redistribution"
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://api.gbif.org/v1/species/search")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {"q": query, "limit": min(limit, 50)}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("results"))[:limit]:
            scientific = self.text(item.get("scientificName") or item.get("canonicalName"))
            vernacular = self.text(item.get("vernacularName"))
            title = vernacular or scientific
            key = self.text(item.get("key") or item.get("nubKey"))
            if not title or not key:
                continue
            classification = " > ".join(
                value for value in (
                    self.text(item.get("kingdom")),
                    self.text(item.get("phylum")),
                    self.text(item.get("class")),
                    self.text(item.get("order")),
                    self.text(item.get("family")),
                    self.text(item.get("genus")),
                ) if value
            )
            records.append(
                {
                    "source_key": key,
                    "title": title,
                    "summary": " · ".join(v for v in (scientific, classification) if v) or None,
                    "url": f"https://www.gbif.org/species/{key}",
                    "author": self.text(item.get("authorship")) or None,
                    "resource_kind": "web",
                    "tags": ["과학", "생물", "분류"],
                    "metadata": {
                        key_name: value
                        for key_name, value in {
                            "taxon_key": key,
                            "scientific_name": scientific,
                            "rank": self.text(item.get("rank")),
                            "status": self.text(item.get("taxonomicStatus")),
                        }.items()
                        if value
                    },
                }
            )
        return records


class TatoebaAdapter(CachedSearchAdapter):
    SOURCE = "tatoeba"
    ATTRIBUTION = "Tatoeba contributors"
    LICENSE_NOTE = "Tatoeba sentence text is CC BY; attribution is required"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://api.tatoeba.org/v1/sentences")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "lang": "kor,eng",
            "q": query,
            "limit": min(limit, 20),
            "is_unapproved": "no",
            "is_orphan": "no",
            "showtrans": "all",
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("data"))[:limit]:
            sentence = self.text(item.get("text"))
            sentence_id = self.text(item.get("id"))
            language = self.text(item.get("lang"))
            if not sentence or not sentence_id:
                continue
            translations = item.get("translations")
            translation_texts: list[str] = []
            if isinstance(translations, list):
                for group in translations:
                    if isinstance(group, list):
                        for translated in group:
                            if isinstance(translated, dict):
                                value = self.text(translated.get("text"))
                                if value and value != sentence:
                                    translation_texts.append(value)
                    elif isinstance(group, dict):
                        value = self.text(group.get("text"))
                        if value and value != sentence:
                            translation_texts.append(value)
            records.append(
                {
                    "source_key": sentence_id,
                    "title": sentence,
                    "summary": " / ".join(translation_texts[:3]) or None,
                    "url": f"https://tatoeba.org/en/sentences/show/{sentence_id}",
                    "author": self.text(item.get("owner")) or None,
                    "resource_kind": "web",
                    "tags": ["언어", "예문", language] if language else ["언어", "예문"],
                    "metadata": {"sentence_id": sentence_id, "language": language},
                }
            )
        return records


class NominatimAdapter(CachedSearchAdapter):
    SOURCE = "openstreetmap_nominatim"
    ATTRIBUTION = "© OpenStreetMap contributors"
    LICENSE_NOTE = "OpenStreetMap data: ODbL 1.0; attribution required"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://nominatim.openstreetmap.org/search")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "q": query,
            "format": "jsonv2",
            "limit": min(limit, 20),
            "addressdetails": 1,
            "accept-language": "ko",
        }

    def _fetch(self, query: str, limit: int) -> dict[str, Any]:
        items = self.http.get_json_list(
            self.endpoint,
            params=self._params(query=query, limit=limit),
        )
        return {"results": items}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records = payload.get("results")
        if not isinstance(records, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in records[:limit]:
            if not isinstance(item, dict):
                continue
            title = self.text(item.get("display_name"))
            osm_id = self.text(item.get("osm_id"))
            if not title:
                continue
            normalized.append(
                {
                    "source_key": f"{self.text(item.get('osm_type'))}:{osm_id}",
                    "title": title,
                    "summary": self.text(item.get("type")) or None,
                    "url": None,
                    "author": None,
                    "resource_kind": "web",
                    "tags": ["탐방", "장소"],
                    "metadata": {
                        "latitude": self.text(item.get("lat")),
                        "longitude": self.text(item.get("lon")),
                        "osm_id": osm_id,
                    },
                }
            )
        return normalized


class OpenTopoDataAdapter(CachedSearchAdapter):
    SOURCE = "opentopodata"
    ATTRIBUTION = "OpenTopoData / underlying elevation datasets"
    LICENSE_NOTE = "Observe the license of the configured elevation dataset (default SRTM90m)"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://api.opentopodata.org/v1/srtm90m")
        super().__init__(**kwargs)

    def search_location(
        self,
        *,
        latitude: float,
        longitude: float,
        offline: bool = False,
    ):
        query = f"{latitude:.6f},{longitude:.6f}"
        return self.search(query=query, limit=1, offline=offline)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        del limit
        return {"locations": query}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        del limit
        results = self.list_of_dicts(payload.get("results"))
        if not results:
            return []
        item = results[0]
        elevation = self.text(item.get("elevation"))
        location = self.dict_value(item.get("location"))
        lat = self.text(location.get("lat"))
        lon = self.text(location.get("lng"))
        if not elevation:
            return []
        return [
            {
                "source_key": f"{lat},{lon}",
                "title": f"탐방 위치 고도 {elevation} m",
                "summary": "부모가 입력한 탐방 좌표의 공개 지형 고도 정보",
                "url": None,
                "author": None,
                "resource_kind": "web",
                "tags": ["탐방", "지형", "고도"],
                "metadata": {"elevation_m": elevation, "latitude": lat, "longitude": lon},
            }
        ]
