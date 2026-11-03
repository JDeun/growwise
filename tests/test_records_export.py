from __future__ import annotations

import asyncio
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from growwise.api import records_export_routes as routes
from growwise.api.dependencies import get_settings, get_store
from growwise.api.main import app
from growwise.backup import records_export
from growwise.backup.records_export import MANIFEST_NAME
from growwise.backup.service import BackupService, InvalidBackup
from growwise.config import Settings
from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.domain.photo import PhotoActivityRecord, PhotoAsset, PhotoRecordStatus
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore

NOW = datetime(2026, 11, 3, 12, tzinfo=UTC)


@pytest.fixture
def exported(tmp_path):
    settings = Settings(data_dir=tmp_path, llm_features_enabled=False,
                        embedding_features_enabled=False, vision_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    owner = ChildProfile(nickname="합성 내보내기", stage=Stage.ELEMENTARY, age_months=96,
                         created_at=NOW - timedelta(days=90))
    other = ChildProfile(nickname="다른 아이 비공개 이름", stage=Stage.ELEMENTARY, age_months=96)
    store.save(owner)
    store.save(other)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        yield TestClient(app), store, settings, owner, other
    finally:
        app.dependency_overrides.pop(get_store, None)
        app.dependency_overrides.pop(get_settings, None)


def _request(client, child, **params):
    return client.get(f"/v1/children/{child.id}/records/export", params=params)


def _archive(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "growwise-records-" in response.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    return archive, json.loads(archive.read(MANIFEST_NAME))


def _member(entity):
    return f"records/{entity.entity_type}/{entity.id}.md"


def _photo(store, settings, child, *, log=None):
    content = b"synthetic managed asset bytes"
    asset = PhotoAsset(
        child_id=child.id, original_filename="synthetic.png", mime_type="image/png",
        relative_path="photos/synthetic.png", sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
    )
    path = settings.assets_dir / asset.relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    store.save(asset)
    photo = PhotoActivityRecord(child_id=child.id, photo_asset_ids=[asset.id],
                                generated_observation="부모가 확인한 합성 사진 관찰",
                                generation_mode="manual", status=PhotoRecordStatus.COMMITTED,
                                learning_log_id=log.id if log else None,
                                created_at=NOW - timedelta(days=90))
    store.save(photo)
    return photo, asset, content


def test_selected_period_has_profile_exact_markdown_and_supporting_book_not_other_child(exported):
    client, store, settings, child, other = exported
    book = ResourceRecord(kind=ResourceKind.BOOK, title="범위 밖의 연결된 책",
                          created_at=NOW - timedelta(days=90))
    store.save(book)
    wanted = LearningLog(child_id=child.id, parent_observation="선택한 합성 관찰",
                         occurred_at=NOW, created_at=NOW - timedelta(days=90), book_id=book.id)
    path = store.save(wanted)
    old = LearningLog(child_id=child.id, parent_observation="기간 밖의 관찰",
                      occurred_at=NOW - timedelta(days=90), created_at=NOW)
    private = LearningLog(child_id=other.id, parent_observation="다른 아이 비공개 관찰",
                          occurred_at=NOW)
    store.save(old)
    store.save(private)
    response = _request(client, child, start_date="2026-11-01", end_date="2026-11-03")
    archive, manifest = _archive(response)
    assert archive.read(_member(wanted)) == path.read_bytes()
    assert _member(child) in archive.namelist()
    assert _member(book) in archive.namelist()
    assert _member(old) not in archive.namelist()
    assert _member(private) not in archive.namelist()
    assert _member(other) not in archive.namelist()
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    assert manifest["full_backup"] is False
    assert manifest["restorable_by_app"] is False
    selected = settings.data_dir / "selected.zip"
    selected.write_bytes(response.content)
    with pytest.raises(InvalidBackup):
        BackupService().validate_archive(selected)
    full = settings.data_dir / "full.zip"
    expected = BackupService().create(records_root=settings.records_dir, destination=full)
    assert BackupService().validate_archive(full).record_count == expected.record_count
    assert expected.record_count > manifest["record_count"]


def test_raw_sources_override_stale_index_and_unindexed_records_are_not_lost(exported):
    client, store, _, child, other = exported
    resource = ResourceRecord(
        kind=ResourceKind.NOTE, title="formerly global", content="now private",
    )
    store.save(resource)
    resource.child_id = other.id
    store.markdown.save(resource)  # Deliberately do not update SQLite ownership.
    unindexed = LearningLog(child_id=child.id, parent_observation="새 원본만 존재하는 기록")
    path = store.markdown.save(unindexed)
    archive, _ = _archive(_request(client, child))
    assert _member(resource) not in archive.namelist()
    assert archive.read(_member(unindexed)) == path.read_bytes()


def test_shared_source_rechecked_from_raw_grants_and_revoke_excludes_private_content(exported):
    client, store, _, child, other = exported
    book = ResourceRecord(child_id=other.id, kind=ResourceKind.BOOK, title="공유된 합성 책")
    store.save(book)
    links = EntityLinkService(store)
    grant = links.share_with_children(source_id=book.id, child_ids=[child.id])[0]
    archive, _ = _archive(_request(client, child))
    assert _member(book) in archive.namelist()
    assert links.delete(grant.id)
    archive, _ = _archive(_request(client, child))
    assert _member(book) not in archive.namelist()
    assert _member(other) not in archive.namelist()


def test_referenced_photo_and_avatar_bytes_are_portable_outside_date_window(exported):
    client, store, settings, child, other = exported
    log = LearningLog(child_id=child.id, parent_observation="최근 사진 관찰", occurred_at=NOW)
    store.save(log)
    photo, asset, content = _photo(store, settings, child, log=log)
    child.avatar_asset_id = asset.id
    store.save(child)
    private_asset = PhotoAsset(child_id=other.id, original_filename="private.png",
                               mime_type="image/png", relative_path="photos/private.png",
                               sha256="b" * 64, byte_size=10)
    store.save(private_asset)
    archive, manifest = _archive(_request(client, child, start_date="2026-11-01",
                                          end_date="2026-11-03"))
    assert _member(photo) in archive.namelist()
    assert _member(asset) in archive.namelist()
    assert archive.read(f"assets/{asset.relative_path}") == content
    assert _member(private_asset) not in archive.namelist()
    assert manifest["asset_count"] == 1


@pytest.mark.parametrize("fault", ["traversal", "foreign_owner", "wrong_hash"])
def test_unsafe_or_inconsistent_asset_cannot_be_exported(exported, fault):
    client, store, settings, child, other = exported
    photo, asset, _ = _photo(store, settings, child)
    if fault == "traversal":
        asset.relative_path = "../outside.bin"
    elif fault == "foreign_owner":
        asset.child_id = other.id
    else:
        asset.sha256 = "f" * 64
    store.save(asset)
    response = _request(client, child)
    assert response.status_code == 409
    assert response.json()["detail"] == "records_export_unavailable"
    assert "outside.bin" not in response.text


@pytest.mark.parametrize("kind", ["record", "asset"])
def test_symlink_sources_are_rejected_without_reading_the_target(exported, tmp_path, kind):
    client, store, settings, child, _ = exported
    photo, asset, _ = _photo(store, settings, child)
    target = tmp_path / "outside.txt"
    target.write_text("must not be exported", encoding="utf-8")
    path = (store.markdown.path_for(photo) if kind == "record"
            else settings.assets_dir / asset.relative_path)
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("creating symbolic links requires OS permission on this runner")
    response = _request(client, child)
    assert response.status_code == 409
    assert "must not be exported" not in response.text


@pytest.mark.parametrize("params,status", [
    ({"start_date": "not-a-date"}, 422),
    ({"start_date": "2026-11-03", "end_date": "2026-10-01"}, 400),
    ({"start_date": "1900-01-01", "end_date": "2026-11-03"}, 400),
])
def test_invalid_periods_are_rejected(exported, params, status):
    client, _, _, child, _ = exported
    assert _request(client, child, **params).status_code == status


def test_member_byte_and_time_budgets_are_enforced(exported, monkeypatch):
    client, _, _, child, _ = exported
    with monkeypatch.context() as patch:
        patch.setattr(records_export, "MAX_TOTAL_BYTES", 1)
        assert _request(client, child).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(records_export, "MAX_FILE_BYTES", 1)
        assert _request(client, child).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(records_export, "MAX_ARCHIVE_BYTES", 1)
        assert _request(client, child).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(records_export, "MAX_MEMBERS", 1)
        assert _request(client, child).status_code == 413
    with monkeypatch.context() as patch:
        patch.setattr(records_export, "MAX_SECONDS", -1)
        assert _request(client, child).status_code == 413


def test_unknown_child_is_not_exported_and_open_ended_dates_are_supported(exported):
    client, store, _, child, _ = exported
    assert client.get(f"/v1/children/{uuid4()}/records/export").status_code == 404
    log = LearningLog(child_id=child.id, parent_observation="경계 날짜 관찰", occurred_at=NOW)
    store.save(log)
    archive, _ = _archive(_request(client, child, end_date="2026-11-03"))
    assert _member(log) in archive.namelist()
    archive, _ = _archive(_request(client, child, start_date="2026-11-04"))
    assert _member(log) not in archive.namelist()
    assert _member(child) in archive.namelist()


def test_temporary_archive_is_removed_after_response(exported, monkeypatch):
    client, _, _, child, _ = exported
    original = tempfile.TemporaryDirectory
    paths = []

    def temporary(*args, **kwargs):
        directory = original(*args, **kwargs)
        paths.append(Path(directory.name))
        return directory

    monkeypatch.setattr(routes.tempfile, "TemporaryDirectory", temporary)
    _archive(_request(client, child))
    assert paths and all(not path.exists() for path in paths)


def test_temporary_archive_is_removed_if_client_disconnects():
    temporary = tempfile.TemporaryDirectory(prefix="growwise-export-test-")
    path = Path(temporary.name) / "synthetic.zip"
    path.write_bytes(b"PK" + b"synthetic")
    response = routes._ExportResponse(path, temporary, "synthetic.zip")

    async def disconnected(_message):
        raise OSError("synthetic client disconnected")

    async def receive():
        return {"type": "http.request"}

    with pytest.raises(OSError, match="synthetic client"):
        asyncio.run(response({"type": "http", "method": "GET", "headers": []},
                             receive, disconnected))
    assert not path.parent.exists()
