from __future__ import annotations

from pathlib import Path

import pytest

from growwise.api import entry


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
