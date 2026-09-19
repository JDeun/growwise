from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from growwise.api.dependencies import get_settings
from growwise.api.main import app

_UUID = "018f7f00-9999-7999-8999-999999999999"
_ROOT_TYPE_CORPUS = [
    [],
    "",
    0,
    True,
    ["unexpected", {"nested": "value"}],
]


def _materialize_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", _UUID, path)


def test_every_request_body_route_rejects_adversarial_root_types_without_5xx(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("GROWWISE_LLM_FEATURES_ENABLED", "false")
    monkeypatch.setenv("GROWWISE_EMBEDDING_FEATURES_ENABLED", "false")
    monkeypatch.setenv("GROWWISE_VISION_FEATURES_ENABLED", "false")
    get_settings.cache_clear()

    schema = app.openapi()
    exercised: list[str] = []
    try:
        with TestClient(app) as client:
            for route, operations in schema["paths"].items():
                for method, operation in operations.items():
                    if method.upper() not in {"POST", "PUT", "PATCH"}:
                        continue
                    if "requestBody" not in operation:
                        continue
                    url = _materialize_path(route)
                    for payload in _ROOT_TYPE_CORPUS:
                        response = client.request(method.upper(), url, json=payload)
                        assert response.status_code < 500, (
                            f"{method.upper()} {route} crashed for {payload!r}: "
                            f"{response.status_code} {response.text}"
                        )
                    response = client.request(
                        method.upper(),
                        url,
                        content=b"{]",
                        headers={"content-type": "application/json"},
                    )
                    assert response.status_code < 500, (
                        f"{method.upper()} {route} crashed for malformed JSON: "
                        f"{response.status_code} {response.text}"
                    )
                    exercised.append(f"{method.upper()} {route}")
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert len(exercised) >= 10, "OpenAPI adversarial corpus unexpectedly exercised too few routes"
