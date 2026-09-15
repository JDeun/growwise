from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from growwise.api.main import app
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_backup_api_create_list_and_restore_requires_confirmation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "growwise"
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(data_dir))
    store = EntityStore(data_dir / "records", data_dir / "index.sqlite3")
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    client = TestClient(app)
    created = client.post("/v1/admin/backups", json={})
    assert created.status_code == 200
    archive = created.json()["archive"]

    listed = client.get("/v1/admin/backups")
    assert listed.status_code == 200
    assert any(item["archive"] == archive for item in listed.json())

    denied = client.post(
        f"/v1/admin/backups/{archive}/restore",
        json={"confirmed": False},
    )
    assert denied.status_code == 409
    assert denied.json()["detail"] == "restore_confirmation_required"


def test_backup_api_rejects_unsafe_archive_name(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path / "growwise"))
    client = TestClient(app)

    response = client.post(
        "/v1/admin/backups",
        json={"name": "../escape.zip"},
    )

    assert response.status_code == 422
