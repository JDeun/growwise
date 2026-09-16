from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from growwise.api.desktop_security import install_desktop_security


def test_desktop_security_requires_exact_bearer_token() -> None:
    app = FastAPI()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    token = "a" * 64
    install_desktop_security(app, session_token=token)
    client = TestClient(app)

    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": "Bearer wrong"}).status_code == 401
    response = client.get("/health", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_desktop_handshake_is_authenticated_and_versioned() -> None:
    app = FastAPI()
    token = "b" * 64
    install_desktop_security(app, session_token=token)
    client = TestClient(app)

    assert client.get("/_desktop/handshake").status_code == 401
    response = client.get(
        "/_desktop/handshake",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == {"product": "growwise-core", "protocol_version": 1}


def test_desktop_security_rejects_weak_tokens() -> None:
    app = FastAPI()
    try:
        install_desktop_security(app, session_token="too-short")
    except ValueError as exc:
        assert "at least 32" in str(exc)
    else:
        raise AssertionError("weak desktop token unexpectedly accepted")
