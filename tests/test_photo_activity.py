from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoActivityRecord, PhotoRecordStatus
from growwise.services.photo_activity import (
    _COMMIT_LOCK_STRIPES,
    PhotoActivityService,
    PhotoAssetStore,
    PhotoUpload,
    PhotoValidationError,
    _commit_lock,
)
from growwise.storage import EntityStore

# Valid 1x1 PNG. Keeping a binary fixture in code makes this test independent of Pillow.
_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _service(tmp_path: Path) -> tuple[PhotoActivityService, EntityStore, ChildProfile, Settings]:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="샘플아이", nickname="샘플아이", stage=Stage.INFANT_0_2)
    store.save(child)
    service = PhotoActivityService(
        store=store,
        asset_store=PhotoAssetStore(
            settings.assets_dir,
            max_file_bytes=settings.photo_max_file_bytes,
        ),
        text_provider=None,
        vision_provider=None,
        max_images=settings.photo_max_images_per_record,
    )
    return service, store, child, settings


def test_photo_activity_draft_survives_without_any_model_and_commits_learning_log(
    tmp_path: Path,
) -> None:
    service, store, child, settings = _service(tmp_path)
    record, assets = service.create_draft(
        child_id=str(child.id),
        uploads=[PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
        user_context="블록을 함께 쌓고 무너뜨리며 반복해서 놀았다.",
    )

    assert record.status is PhotoRecordStatus.DRAFT
    assert record.generation_mode == "deterministic_photo_fallback"
    assert "블록을 함께" in record.generated_observation
    assert len(assets) == 1
    assert assets[0].width == 1
    assert assets[0].height == 1
    assert (settings.assets_dir / assets[0].relative_path).is_file()

    log = service.commit(
        record_id=str(record.id),
        observation="블록을 쌓고 무너뜨리는 놀이를 여러 번 반복했다.",
    )
    assert log.child_id == child.id
    assert log.record_kind.value == "photo_activity"
    assert log.parent_observation.startswith("블록을 쌓고")
    assert "사진기록" in log.tags

    stored_record = PhotoActivityRecord.model_validate(
        store.index.get_entity(str(record.id), entity_type="photo_activity_record")
    )
    assert stored_record.status is PhotoRecordStatus.COMMITTED
    assert stored_record.learning_log_id == log.id

    # Commit is idempotent after the draft has become a LearningLog.
    assert service.commit(record_id=str(record.id)).id == log.id


def test_concurrent_photo_commit_creates_exactly_one_learning_log(tmp_path: Path) -> None:
    service, store, child, _settings = _service(tmp_path)
    record, _assets = service.create_draft(
        child_id=str(child.id),
        uploads=[PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
        user_context="동시 저장 테스트",
    )

    def commit_once() -> str:
        return str(service.commit(record_id=str(record.id)).id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result_ids = list(pool.map(lambda _index: commit_once(), range(2)))

    assert len(set(result_ids)) == 1
    stored_logs = store.index.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(stored_logs) == 1



def test_photo_commit_recovers_after_crash_between_log_and_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, store, child, _settings = _service(tmp_path)
    record, _assets = service.create_draft(
        child_id=str(child.id),
        uploads=[PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
        user_context="crash recovery test",
    )

    original_save = store.save
    failed = False

    def fail_final_record_save(entity, body: str = ""):
        nonlocal failed
        if (
            not failed
            and entity.entity_type == "photo_activity_record"
            and entity.status is PhotoRecordStatus.COMMITTED
        ):
            failed = True
            raise OSError("simulated crash after learning log commit")
        return original_save(entity, body=body)

    monkeypatch.setattr(store, "save", fail_final_record_save)
    with pytest.raises(OSError, match="simulated crash"):
        service.commit(record_id=str(record.id), observation="부모가 확정한 관찰")

    persisted = PhotoActivityRecord.model_validate(
        store.index.get_entity(str(record.id), entity_type="photo_activity_record")
    )
    assert persisted.status is PhotoRecordStatus.DRAFT
    assert persisted.learning_log_id is not None
    logs_after_failure = store.index.list_entities(
        entity_type="learning_log",
        child_id=str(child.id),
    )
    assert len(logs_after_failure) == 1
    assert logs_after_failure[0]["id"] == str(persisted.learning_log_id)

    monkeypatch.setattr(store, "save", original_save)
    recovered = service.commit(record_id=str(record.id), observation="부모가 확정한 관찰")
    assert recovered.id == persisted.learning_log_id

    logs_after_retry = store.index.list_entities(
        entity_type="learning_log",
        child_id=str(child.id),
    )
    assert len(logs_after_retry) == 1
    final_record = PhotoActivityRecord.model_validate(
        store.index.get_entity(str(record.id), entity_type="photo_activity_record")
    )
    assert final_record.status is PhotoRecordStatus.COMMITTED
    assert final_record.learning_log_id == recovered.id

def test_photo_asset_rejects_spoofed_mime_oversize_and_truncated_input(tmp_path: Path) -> None:
    asset_store = PhotoAssetStore(tmp_path / "assets", max_file_bytes=len(_ONE_PIXEL_PNG))
    child_id = "018f47f2-9786-7c99-bc1f-1d5df10c0000"

    with pytest.raises(PhotoValidationError, match="image_mime_mismatch"):
        asset_store.store(
            child_id=child_id,
            upload=PhotoUpload(
                filename="fake.jpg",
                mime_type="image/jpeg",
                data=_ONE_PIXEL_PNG,
            ),
        )

    with pytest.raises(PhotoValidationError, match="image_too_large"):
        asset_store.store(
            child_id=child_id,
            upload=PhotoUpload(
                filename="large.png",
                mime_type="image/png",
                data=_ONE_PIXEL_PNG + b"x",
            ),
        )

    with pytest.raises(PhotoValidationError, match="malformed_image"):
        asset_store.store(
            child_id=child_id,
            upload=PhotoUpload(
                filename="truncated.png",
                mime_type="image/png",
                data=_ONE_PIXEL_PNG[:32],
            ),
        )


def test_photo_draft_rolls_back_binary_and_metadata_when_persistence_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, store, child, settings = _service(tmp_path)
    original_save = store.save

    def failing_save(entity, body: str = ""):
        if entity.entity_type == "photo_activity_record":
            raise OSError("simulated persistence failure")
        return original_save(entity, body=body)

    monkeypatch.setattr(store, "save", failing_save)

    with pytest.raises(OSError, match="simulated persistence failure"):
        service.create_draft(
            child_id=str(child.id),
            uploads=[PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
            user_context="rollback test",
        )

    assert store.index.list_entities(entity_type="photo_asset", child_id=str(child.id)) == []
    photo_dir = settings.photo_assets_dir / str(child.id)
    assert not photo_dir.exists() or not any(photo_dir.iterdir())


def test_photo_asset_read_detects_tampering(tmp_path: Path) -> None:
    service, _store, child, settings = _service(tmp_path)
    _record, assets = service.create_draft(
        child_id=str(child.id),
        uploads=[PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
        user_context=None,
    )
    path = settings.assets_dir / assets[0].relative_path
    path.write_bytes(_ONE_PIXEL_PNG + b"tampered")

    with pytest.raises(PhotoValidationError, match="photo_integrity_mismatch"):
        service.get_asset(str(assets[0].id))

def test_photo_commit_lock_storage_is_bounded() -> None:
    assert len(_COMMIT_LOCK_STRIPES) == 256
    assert _commit_lock("same-record") is _commit_lock("same-record")
    for index in range(10_000):
        _commit_lock(f"record-{index}")
    assert len(_COMMIT_LOCK_STRIPES) == 256
