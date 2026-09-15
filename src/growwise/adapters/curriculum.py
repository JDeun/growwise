from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, Field

from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .http import JsonHttpClient


class CurriculumRecord(BaseModel):
    """Canonical, provider-independent curriculum mapping record."""

    curriculum_id: str
    title: str
    stage: str
    subject: str | None = None
    domain: str | None = None
    competency: str | None = None
    achievement_standard: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublicCurriculumAdapter:
    """Optional public-curriculum enrichment with deterministic cache fallback.

    The adapter intentionally accepts only public curriculum query dimensions. Child IDs,
    observations, learning logs, and other private GrowWise records must never be passed
    to this boundary.
    """

    SOURCE = "public_curriculum"
    ATTRIBUTION = "공공 교육과정 자료"
    LICENSE_NOTE = "원 제공기관의 공공데이터 이용조건 및 개별 자료의 저작권 표시를 확인할 것"

    def __init__(
        self,
        *,
        endpoint: str,
        cache: SQLiteExternalCache,
        http: JsonHttpClient | None = None,
        ttl_seconds: int = 604_800,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("endpoint is required")
        self.endpoint = endpoint
        self.cache = cache
        self.http = http or JsonHttpClient()
        self.ttl_seconds = ttl_seconds

    def search(
        self,
        *,
        stage: str,
        subject: str | None = None,
        query: str | None = None,
        offline: bool = False,
    ) -> AdapterResult:
        normalized_stage = " ".join(stage.split())
        normalized_subject = " ".join((subject or "").split())
        normalized_query = " ".join((query or "").split())
        if not normalized_stage or len(normalized_stage) > 100:
            raise ValueError("stage must be 1-100 characters")
        if len(normalized_subject) > 100:
            raise ValueError("subject must be at most 100 characters")
        if len(normalized_query) > 200:
            raise ValueError("query must be at most 200 characters")

        descriptor = {
            "stage": normalized_stage,
            "subject": normalized_subject,
            "query": normalized_query,
        }
        cache_key = self._cache_key(descriptor)
        fresh = self.cache.get(cache_key)
        if fresh is not None:
            return self._from_cached(fresh, status="fresh")
        stale = self.cache.get(cache_key, allow_stale=True)
        if offline:
            if stale is None:
                raise ExternalUnavailable(
                    "Curriculum source is unavailable offline and no cache exists"
                )
            return self._from_cached(stale, status="stale" if stale.stale else "fresh")

        try:
            payload = self.http.get_json(self.endpoint, params=descriptor)
            records = [
                record.model_dump(mode="json") for record in self._normalize_response(payload)
            ]
            cached = self.cache.put(
                cache_key=cache_key,
                payload={"records": records},
                source=self.SOURCE,
                attribution=self.ATTRIBUTION,
                license_note=self.LICENSE_NOTE,
                ttl_seconds=self.ttl_seconds,
            )
            return AdapterResult(
                source=self.SOURCE,
                records=records,
                attribution=self.ATTRIBUTION,
                license_note=self.LICENSE_NOTE,
                fetched_at=cached.fetched_at,
                cache_status="live",
            )
        except ExternalAdapterError:
            if stale is None:
                raise
            return self._from_cached(stale, status="stale")

    @staticmethod
    def _cache_key(descriptor: dict[str, str]) -> str:
        encoded = json.dumps(descriptor, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return f"public_curriculum:search:{hashlib.sha256(encoded).hexdigest()}"

    @classmethod
    def _normalize_response(cls, payload: dict[str, Any]) -> list[CurriculumRecord]:
        raw_records = payload.get("records", payload.get("data", []))
        if isinstance(raw_records, dict):
            raw_records = raw_records.get("items", [])
        if not isinstance(raw_records, list):
            return []

        records: list[CurriculumRecord] = []
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            title = cls._text(
                item.get("title") or item.get("name") or item.get("achievement_standard")
            )
            stage = cls._text(
                item.get("stage") or item.get("school_level") or item.get("grade_band")
            )
            if not title or not stage:
                continue
            source_id = cls._text(item.get("id") or item.get("code"))
            curriculum_id = source_id or hashlib.sha256(
                f"{stage}\x1f{cls._text(item.get('subject'))}\x1f{title}".encode()
            ).hexdigest()[:24]
            known = {
                "id",
                "code",
                "title",
                "name",
                "stage",
                "school_level",
                "grade_band",
                "subject",
                "domain",
                "competency",
                "achievement_standard",
                "source_url",
                "url",
            }
            records.append(
                CurriculumRecord(
                    curriculum_id=curriculum_id,
                    title=title,
                    stage=stage,
                    subject=cls._optional_text(item.get("subject")),
                    domain=cls._optional_text(item.get("domain")),
                    competency=cls._optional_text(item.get("competency")),
                    achievement_standard=cls._optional_text(item.get("achievement_standard")),
                    source_url=cls._optional_text(item.get("source_url") or item.get("url")),
                    metadata={str(k): v for k, v in item.items() if k not in known},
                )
            )
        return records

    @staticmethod
    def _text(value: object) -> str:
        return str(value).strip() if value is not None else ""

    @classmethod
    def _optional_text(cls, value: object) -> str | None:
        text = cls._text(value)
        return text or None

    @staticmethod
    def _from_cached(cached: CachedPayload, *, status: str) -> AdapterResult:
        records = cached.payload.get("records", [])
        if not isinstance(records, list):
            records = []
        return AdapterResult(
            source=cached.source,
            records=[item for item in records if isinstance(item, dict)],
            attribution=cached.attribution,
            license_note=cached.license_note,
            fetched_at=cached.fetched_at,
            cache_status="stale" if status == "stale" else "fresh",
        )
