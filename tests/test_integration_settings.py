from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import growwise.api.integration_routes as integrations
from growwise.api.main import app
from growwise.config import Settings


def test_connection_test_does_not_probe_missing_key(monkeypatch, tmp_path):
    monkeypatch.setattr(integrations, "get_settings", lambda: Settings(data_dir=tmp_path))
    response = TestClient(app).post("/v1/admin/integrations/data4library/test")
    assert response.status_code == 200
    assert response.json()["status"] == "missing_key"
    assert TestClient(app).post("/v1/admin/integrations/arbitrary/test").status_code == 422


@pytest.mark.parametrize(
    "records,expected", [([{"title": "science"}], "available"), ([], "reachable_no_results")]
)
def test_probe_uses_new_cache_public_query_and_never_returns_key(
    monkeypatch, tmp_path, records, expected
):
    secret = "synthetic-connection-test-token"
    settings = Settings(data_dir=tmp_path, google_books_api_key=secret)
    monkeypatch.setattr(integrations, "get_settings", lambda: settings)
    observed = []

    class Adapter:
        def __init__(self, *, api_key, cache, endpoint):
            assert api_key == secret
            assert cache is not None
            observed.append(cache)

        def search_books(self, *, query, limit):
            assert query == "science" and limit == 1
            return SimpleNamespace(records=records)

    monkeypatch.setattr(integrations, "GoogleBooksAdapter", Adapter)
    for _ in range(2):
        response = TestClient(app).post("/v1/admin/integrations/google_books/test")
        assert response.json()["status"] == expected
        assert secret not in response.text
    assert observed[0] is not observed[1]


def test_upstream_error_cannot_leak_key_or_private_request(monkeypatch, tmp_path):
    secret = "synthetic-never-reflect-this-token"
    monkeypatch.setattr(
        integrations, "get_settings", lambda: Settings(data_dir=tmp_path, krdict_api_key=secret)
    )

    def fail(**_kwargs):
        raise RuntimeError(f"upstream URL?key={secret}")

    monkeypatch.setattr(integrations, "KrDictAdapter", fail)
    response = TestClient(app).post("/v1/admin/integrations/krdict/test")
    assert response.json()["status"] == "unavailable"
    assert secret not in response.text
    assert "upstream" not in response.text
