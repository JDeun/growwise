from __future__ import annotations

from typing import Any

from .license_filter import is_commercial_safe
from .search_base import CachedSearchAdapter


class GoogleBooksAdapter(CachedSearchAdapter):
    SOURCE = "google_books"
    ATTRIBUTION = "Google Books"
    LICENSE_NOTE = (
        "Google Books metadata/API terms apply; GrowWise stores bibliographic metadata and source "
        "links only, not restricted book content"
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://www.googleapis.com/books/v1/volumes")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {"q": query, "maxResults": min(limit, 40), "printType": "books"}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("items"))[:limit]:
            info = self.dict_value(item.get("volumeInfo"))
            title = self.text(info.get("title"))
            if not title:
                continue
            authors = info.get("authors")
            author_text = ", ".join(str(v).strip() for v in authors if str(v).strip()) if isinstance(authors, list) else ""
            identifiers = self.list_of_dicts(info.get("industryIdentifiers"))
            isbn = ""
            for identifier in identifiers:
                if self.text(identifier.get("type")) in {"ISBN_13", "ISBN_10"}:
                    isbn = self.text(identifier.get("identifier"))
                    if self.text(identifier.get("type")) == "ISBN_13":
                        break
            records.append(
                {
                    "source_key": self.text(item.get("id")) or isbn or title,
                    "title": title,
                    "summary": self.text(info.get("description"))[:4_000] or None,
                    "url": self.text(info.get("infoLink")) or None,
                    "author": author_text or None,
                    "resource_kind": "book",
                    "tags": ["도서", "서지"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "isbn": isbn,
                            "publisher": self.text(info.get("publisher")),
                            "published_date": self.text(info.get("publishedDate")),
                            "language": self.text(info.get("language")),
                        }.items()
                        if value
                    },
                }
            )
        return records


class GutendexAdapter(CachedSearchAdapter):
    SOURCE = "gutendex"
    ATTRIBUTION = "Project Gutenberg metadata via Gutendex"
    LICENSE_NOTE = (
        "Project Gutenberg texts are public domain in the United States; verify jurisdiction and "
        "the linked ebook's rights notice before redistribution"
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("endpoint", "https://gutendex.com/books")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        del limit
        return {"search": query}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("results"))[:limit]:
            title = self.text(item.get("title"))
            if not title:
                continue
            authors = self.list_of_dicts(item.get("authors"))
            author_text = ", ".join(
                self.text(author.get("name")) for author in authors if self.text(author.get("name"))
            )
            formats = self.dict_value(item.get("formats"))
            url = (
                self.text(formats.get("text/html; charset=utf-8"))
                or self.text(formats.get("text/html"))
                or self.text(formats.get("application/epub+zip"))
            )
            subjects = item.get("subjects")
            subject_values = [self.text(v) for v in subjects if self.text(v)] if isinstance(subjects, list) else []
            languages = item.get("languages")
            language_values = [self.text(v) for v in languages if self.text(v)] if isinstance(languages, list) else []
            records.append(
                {
                    "source_key": self.text(item.get("id")) or title,
                    "title": title,
                    "summary": " · ".join(subject_values[:4]) or None,
                    "url": url or None,
                    "author": author_text or None,
                    "resource_kind": "book",
                    "tags": ["도서", "퍼블릭도메인", *subject_values[:3]],
                    "metadata": {
                        "languages": ",".join(language_values[:5]),
                        "download_count": self.text(item.get("download_count")),
                    },
                }
            )
        return records


class GlobalDigitalLibraryAdapter(CachedSearchAdapter):
    SOURCE = "global_digital_library"
    ATTRIBUTION = "Global Digital Library"
    LICENSE_NOTE = "Only item-level commercial-safe Creative Commons records are surfaced"

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault(
            "endpoint",
            "https://content.digitallibrary.io/wp-json/content-api/v1/contentsearch",
        )
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        del limit
        return {"query": query}

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in self.list_of_dicts(payload.get("books")):
            title = self.text(item.get("title"))
            if not title:
                continue
            raw_licenses = item.get("license")
            licenses = []
            if isinstance(raw_licenses, list):
                for entry in raw_licenses:
                    if isinstance(entry, dict):
                        value = self.text(entry.get("name") or entry.get("slug"))
                    else:
                        value = self.text(entry)
                    if value:
                        licenses.append(value)
            # GDL is item-licensed; fail closed if the search result does not expose a safe license.
            if not licenses or not any(is_commercial_safe(value) for value in licenses):
                continue
            topics = item.get("topic")
            topic_names = []
            if isinstance(topics, list):
                for topic in topics:
                    if isinstance(topic, dict):
                        value = self.text(topic.get("name"))
                        if value:
                            topic_names.append(value)
            languages = item.get("language")
            language_names = []
            if isinstance(languages, list):
                for language in languages:
                    if isinstance(language, dict):
                        value = self.text(language.get("name"))
                        if value:
                            language_names.append(value)
            records.append(
                {
                    "source_key": self.text(item.get("postId")) or self.text(item.get("post_name")) or title,
                    "title": title,
                    "summary": self.text(item.get("description"))[:4_000] or None,
                    "url": self.text(item.get("postLink")) or None,
                    "author": None,
                    "resource_kind": "book",
                    "tags": ["도서", "오픈교육", *topic_names[:3]],
                    "metadata": {
                        "license": ",".join(licenses[:4]),
                        "languages": ",".join(language_names[:4]),
                        "publisher": self.text(item.get("publisher")),
                        "h5p_url": self.text(item.get("h5pUrl")),
                    },
                }
            )
            if len(records) >= limit:
                break
        return records


class NationalLibraryIsbnAdapter(CachedSearchAdapter):
    SOURCE = "national_library_isbn"
    ATTRIBUTION = "국립중앙도서관 ISBN 서지정보"
    LICENSE_NOTE = "국립중앙도서관 Open API 이용조건; bibliographic metadata only"

    def __init__(self, *, cert_key: str, **kwargs: Any) -> None:
        if not cert_key.strip():
            raise ValueError("cert_key is required")
        self.cert_key = cert_key
        kwargs.setdefault("endpoint", "https://www.nl.go.kr/seoji/SearchApi.do")
        super().__init__(**kwargs)

    def _params(self, *, query: str, limit: int) -> dict[str, str | int | float]:
        return {
            "cert_key": self.cert_key,
            "result_style": "json",
            "page_no": 1,
            "page_size": min(limit, 50),
            "title": query,
        }

    def _normalize(self, payload: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
        candidates: object = payload.get("docs")
        if not isinstance(candidates, list):
            candidates = payload.get("result")
        if isinstance(candidates, dict):
            candidates = candidates.get("docs") or candidates.get("items") or candidates.get("item")
        if not isinstance(candidates, list):
            candidates = payload.get("items")
        if not isinstance(candidates, list):
            return []

        records: list[dict[str, Any]] = []
        for item in candidates[:limit]:
            if not isinstance(item, dict):
                continue
            title = self.text(item.get("TITLE") or item.get("title"))
            if not title:
                continue
            isbn = self.text(item.get("EA_ISBN") or item.get("isbn"))
            records.append(
                {
                    "source_key": isbn or title,
                    "title": title,
                    "summary": self.text(item.get("SERIES_TITLE") or item.get("series_title")) or None,
                    "url": None,
                    "author": self.text(item.get("AUTHOR") or item.get("author")) or None,
                    "resource_kind": "book",
                    "tags": ["도서", "국가서지"],
                    "metadata": {
                        key: value
                        for key, value in {
                            "isbn": isbn,
                            "publisher": self.text(item.get("PUBLISHER") or item.get("publisher")),
                            "publish_date": self.text(item.get("PUBLISH_PREDATE") or item.get("publish_date")),
                            "form": self.text(item.get("FORM") or item.get("form")),
                        }.items()
                        if value
                    },
                }
            )
        return records
