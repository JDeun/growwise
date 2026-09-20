from __future__ import annotations

import threading
import time
from pathlib import Path

from uuid6 import uuid7

from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoActivityRecord, PhotoRecordStatus
from growwise.maintenance import DATA_MAINTENANCE
from growwise.services.child_lock import child_operation_lock
from growwise.services.photo_activity import PhotoActivityService, PhotoAssetStore
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore


def test_photo_write_registers_maintenance_before_waiting_for_child_lock(
    tmp_path: Path,
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)
    record = PhotoActivityRecord(
        child_id=child.id,
        photo_asset_ids=[uuid7()],
        generated_observation="사진 기록",
        generation_mode="manual",
        status=PhotoRecordStatus.DRAFT,
    )
    store.save(record)

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

    child_lock = child_operation_lock(str(child.id))
    child_lock.acquire()
    baseline = DATA_MAINTENANCE._active_mutations
    write_errors: list[Exception] = []

    def write_photo_state() -> None:
        try:
            service.mark_queued(str(record.id))
        except Exception as exc:  # pragma: no cover - asserted below
            write_errors.append(exc)

    worker = threading.Thread(target=write_photo_state)
    worker.start()

    deadline = time.monotonic() + 2.0
    while DATA_MAINTENANCE._active_mutations <= baseline and time.monotonic() < deadline:
        time.sleep(0.01)

    # The write must be registered with the maintenance coordinator before it waits on the child
    # lock. Otherwise purge can enter exclusive maintenance first and deadlock against the writer.
    assert DATA_MAINTENANCE._active_mutations == baseline + 1

    purge_errors: list[Exception] = []

    def purge_child() -> None:
        try:
            ChildPurgeService(settings).purge(str(child.id))
        except Exception as exc:  # pragma: no cover - asserted below
            purge_errors.append(exc)

    purge = threading.Thread(target=purge_child)
    purge.start()
    time.sleep(0.05)
    assert purge.is_alive()

    child_lock.release()
    worker.join(timeout=5)
    purge.join(timeout=5)

    assert not worker.is_alive()
    assert not purge.is_alive()
    assert write_errors == []
    assert purge_errors == []

    fresh = EntityStore(settings.records_dir, settings.index_path)
    assert fresh.index.get_entity(str(child.id), entity_type="child_profile") is None
    assert fresh.index.get_entity(str(record.id), entity_type="photo_activity_record") is None
