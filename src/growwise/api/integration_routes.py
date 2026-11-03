from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from growwise.adapters.cache import SQLiteExternalCache
from growwise.adapters.data4library import Data4LibraryAdapter
from growwise.adapters.google_books import GoogleBooksAdapter
from growwise.adapters.krdict import KrDictAdapter
from growwise.adapters.museum import MuseumArtGalleryAdapter
from growwise.adapters.national_library import NationalLibraryIsbnAdapter
from growwise.api.dependencies import get_settings

router = APIRouter(prefix="/v1/admin/integrations", tags=["integration-settings"])
ServiceId = Literal[
    "data4library", "google_books", "national_library", "krdict", "data_go_kr", "model"
]


class ConnectionResult(BaseModel):
    service: ServiceId
    status: Literal["available", "reachable_no_results", "missing_key", "unavailable"]
    message: str


@router.post("/{service}/test", response_model=ConnectionResult)
def test_integration_connection(service: ServiceId) -> ConnectionResult:
    """Probe with a fixed public query; never return credentials, URLs or upstream errors."""
    settings = get_settings()
    key = getattr(
        settings,
        {
            "data4library": "data4library_api_key",
            "google_books": "google_books_api_key",
            "national_library": "national_library_api_key",
            "krdict": "krdict_api_key",
            "data_go_kr": "data_go_kr_service_key",
            "model": "model_api_key",
        }[service],
    )
    if not key:
        return ConnectionResult(
            service=service, status="missing_key", message="API 키를 먼저 등록해 주세요."
        )
    try:
        if service == "model":
            from growwise.model import create_model_provider

            if settings.model_provider.casefold().replace("-", "_") != "openai_compatible":
                return ConnectionResult(
                    service=service,
                    status="unavailable",
                    message="API 키 검증은 설정된 OpenAI 호환 공급자에서 사용할 수 있습니다.",
                )
            answer = create_model_provider(settings).generate_text(
                system="This is a connection test. Reply OK only.",
                user="Connection test.",
            )
            count = int(bool(answer.strip()))
        else:
            # A fresh disposable cache prevents a historical success from validating a new key.
            with TemporaryDirectory(prefix="growwise-connection-") as temporary:
                cache = SQLiteExternalCache(Path(temporary) / "cache.sqlite3")
                if service == "data4library":
                    result = Data4LibraryAdapter(
                        auth_key=key, cache=cache, endpoint=settings.data4library_endpoint
                    ).search_books(keyword="과학", page_size=1)
                elif service == "google_books":
                    result = GoogleBooksAdapter(
                        api_key=key, cache=cache, endpoint=settings.google_books_endpoint
                    ).search_books(query="science", limit=1)
                elif service == "national_library":
                    result = NationalLibraryIsbnAdapter(
                        api_key=key, cache=cache, endpoint=settings.national_library_isbn_endpoint
                    ).search_books(query="과학", limit=1)
                elif service == "krdict":
                    result = KrDictAdapter(
                        api_key=key, cache=cache, endpoint=settings.krdict_endpoint
                    ).search(query="나무", limit=10)
                else:
                    result = MuseumArtGalleryAdapter(
                        service_key=key, cache=cache, endpoint=settings.museum_standard_endpoint
                    ).nearby(latitude=37.5665, longitude=126.9780, limit=1)
                count = len(result.records)
        return ConnectionResult(
            service=service,
            status="available" if count else "reachable_no_results",
            message="실제 연결과 응답을 확인했습니다."
            if count
            else "응답은 받았지만 자료가 없어 키의 권한을 확정할 수 없습니다.",
        )
    except Exception:
        return ConnectionResult(
            service=service,
            status="unavailable",
            message="연결을 확인하지 못했습니다. 키·권한·네트워크를 확인해 주세요.",
        )
