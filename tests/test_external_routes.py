from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from growwise.adapters import AdapterResult, ExternalUnavailable
from growwise.api.external_routes import get_external_cache, get_external_settings
from growwise.api.main import app
from growwise.config import Settings
from growwise.storage import EntityStore


def _client(tmp_path, *, auth_key: str | None = "test-secret", enabled: bool = True):
    settings = Settings(
        data_dir=tmp_path,
        external_enrichment_enabled=enabled,
        data4library_auth_key=auth_key,
    )
    app.dependency_overrides[get_external_settings] = lambda: settings
    app.dependency_overrides[get_external_cache] = lambda: __import__(
        "growwise.adapters", fromlist=["SQLiteExternalCache"]
    ).SQLiteExternalCache(settings.external_cache_path)
    return TestClient(app), settings


def test_public_book_route_never_exposes_credential(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    client, settings = _client(tmp_path)
    captured: dict[str, Any] = {}

    def fake_search(self, *, keyword: str, page: int, page_size: int, offline: bool):
        captured.update(
            auth_key=self.auth_key,
            keyword=keyword,
            page=page,
            page_size=page_size,
            offline=offline,
        )
        return AdapterResult(
            source="data4library",
            records=[{"title": "우주 그림책", "isbn13": "9780000000000"}],
            attribution="도서관 정보나루 (data4library.kr)",
            license_note="public-data terms",
        )

    monkeypatch.setattr(
        "growwise.api.external_routes.Data4LibraryAdapter.search_books",
        fake_search,
    )
    try:
        response = client.get("/v1/external/books", params={"q": "우주", "page_size": 3})
        assert response.status_code == 200
        payload = response.json()
        assert payload["records"][0]["title"] == "우주 그림책"
        assert captured["auth_key"] == settings.data4library_auth_key
        assert captured["keyword"] == "우주"
        assert captured["page_size"] == 3
        assert "test-secret" not in response.text
        assert "child" not in response.request.url.query.casefold()
    finally:
        app.dependency_overrides.clear()


def test_book_route_requires_configuration_but_not_core_llm(tmp_path) -> None:
    client, _ = _client(tmp_path, auth_key=None)
    try:
        response = client.get("/v1/external/books", params={"q": "수학"})
        assert response.status_code == 503
        assert response.json()["detail"] == "data4library_not_configured"
    finally:
        app.dependency_overrides.clear()


def test_external_enrichment_can_be_disabled_without_affecting_core(tmp_path) -> None:
    client, _ = _client(tmp_path, enabled=False)
    try:
        response = client.get("/v1/external/places", params={"latitude": 37.5, "longitude": 127.0})
        assert response.status_code == 503
        assert response.json()["detail"] == "external_enrichment_disabled"
        assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_places_route_preserves_allowlist_and_generic_offline_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _ = _client(tmp_path)
    try:
        invalid = client.get(
            "/v1/external/places",
            params={
                "latitude": 37.5,
                "longitude": 127.0,
                "amenities": "library,pharmacy",
            },
        )
        assert invalid.status_code == 422
        assert "unsupported amenity" in invalid.json()["detail"]

        def unavailable(self, **kwargs):
            raise ExternalUnavailable("sensitive upstream detail")

        monkeypatch.setattr(
            "growwise.api.external_routes.OverpassAdapter.nearby_places",
            unavailable,
        )
        offline = client.get(
            "/v1/external/places",
            params={
                "latitude": 37.5,
                "longitude": 127.0,
                "offline": True,
            },
        )
        assert offline.status_code == 503
        assert offline.json()["detail"] == "external_enrichment_unavailable"
        assert "sensitive upstream detail" not in offline.text
    finally:
        app.dependency_overrides.clear()


def test_external_openapi_has_no_child_context_parameters(tmp_path) -> None:
    client, _ = _client(tmp_path)
    try:
        schema = client.get("/openapi.json").json()
        for path in ("/v1/external/books", "/v1/external/places"):
            parameters = schema["paths"][path]["get"].get("parameters", [])
            names = {str(item["name"]) for item in parameters}
            assert "child_id" not in names
            assert "observation" not in names
    finally:
        app.dependency_overrides.clear()
