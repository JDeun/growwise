from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

import growwise.api.photo_routes as photo_api
import growwise.api.resource_routes as resource_api
import growwise.api.study_routes as study_api
from growwise.api.dependencies import (
    get_conversation_store,
    get_idempotency_store,
    get_material_review_graph,
    get_model_provider,
    get_observation_graph,
    get_rag_index,
    get_settings,
)
from growwise.api.main import app

_UUID = "018f7f00-9999-7999-8999-999999999999"
_ROOT_TYPE_CORPUS = [
    [],
    "",
    0,
    True,
    ["unexpected", {"nested": "value"}],
]


def _reset_route_caches() -> None:
    for provider in (
        get_settings,
        get_model_provider,
        get_rag_index,
        get_conversation_store,
        get_idempotency_store,
        get_observation_graph,
        get_material_review_graph,
        resource_api.get_resource_settings,
        resource_api.get_resource_rag_index,
        resource_api.get_resource_idempotency_store,
        study_api.get_study_settings,
        photo_api.get_photo_settings,
        photo_api.get_photo_text_provider,
        photo_api.get_photo_vision_provider,
        photo_api.get_photo_job_runner,
    ):
        provider.cache_clear()


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
    _reset_route_caches()

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
        _reset_route_caches()

    assert len(exercised) >= 10, "OpenAPI adversarial corpus unexpectedly exercised too few routes"
