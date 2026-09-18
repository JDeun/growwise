from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from growwise.api import entry, main


def test_standalone_entry_rejects_non_loopback_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROWWISE_API_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="local-only"):
        entry.run()


def test_standalone_entry_holds_data_dir_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    observed: dict[str, object] = {}

    def fake_run(app: str, *, host: str, port: int, reload: bool) -> None:
        observed.update(app=app, host=host, port=port, reload=reload)
        assert (tmp_path / ".core.lock").exists()

    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GROWWISE_API_HOST", "127.0.0.1")
    monkeypatch.setenv("GROWWISE_API_PORT", "9876")
    monkeypatch.setattr(entry.uvicorn, "run", fake_run)

    entry.run()

    assert observed == {
        "app": "growwise.api.main:app",
        "host": "127.0.0.1",
        "port": 9876,
        "reload": False,
    }


def test_main_module_runner_delegates_to_guarded_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_guarded_run() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(entry, "run", fake_guarded_run)

    main.run()

    assert called is True


def test_main_module_runner_cannot_bypass_loopback_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROWWISE_API_HOST", "0.0.0.0")

    with pytest.raises(RuntimeError, match="local-only"):
        main.run()



def test_shared_app_handles_domain_validation_as_422() -> None:
    class InvalidDomain(BaseModel):
        value: int

    with pytest.raises(ValidationError) as captured:
        InvalidDomain(value="not-an-int")

    handler = main.app.exception_handlers[ValidationError]
    response = asyncio.run(handler(None, captured.value))  # type: ignore[arg-type]

    assert response.status_code == 422
    payload = json.loads(response.body)
    assert payload["detail"][0]["type"] == "int_parsing"



def test_standalone_entry_recovers_before_server_start(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []

    def fake_recover(_settings) -> dict[str, object]:
        events.append("recover")
        return {}

    def fake_run(_app: str, *, host: str, port: int, reload: bool) -> None:
        del host, port, reload
        events.append("serve")

    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GROWWISE_API_HOST", "127.0.0.1")
    monkeypatch.setattr(entry, "recover_startup_state", fake_recover)
    monkeypatch.setattr(entry.uvicorn, "run", fake_run)

    entry.run()

    assert events == ["recover", "serve"]
