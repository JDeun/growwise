from pathlib import Path

import pytest
from fastapi import HTTPException
from uuid6 import uuid7

from growwise.api import photo_routes
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoActivityRecord, PhotoRecordStatus
from growwise.jobs import SQLiteJobQueue
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB
from growwise.storage import EntityStore


def test_photo_retry_reuses_saved_record_and_rejects_duplicate_in_progress_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, llm_features_enabled=False,
                        vision_features_enabled=False, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="테스트아이", stage=Stage.ELEMENTARY)
    store.save(child)
    record = PhotoActivityRecord(
        child_id=child.id, photo_asset_ids=[uuid7()], status=PhotoRecordStatus.FAILED,
        generated_observation="부모의 원본 메모", generation_mode="failed",
    )
    store.save(record)
    queue = SQLiteJobQueue(settings.jobs_path)

    class Runner:
        def start(self):
            pass

        def submit(self, *, child_id: str, record_id: str):
            return queue.enqueue(PHOTO_ANALYSIS_JOB, {"child_id": child_id, "record_id": record_id})

    monkeypatch.setattr(photo_routes, "get_photo_job_runner", Runner)
    result = photo_routes.retry_photo_record(record.id, settings, store)
    assert result["record"]["id"] == str(record.id)
    assert result["record"]["photo_asset_ids"] == [str(record.photo_asset_ids[0])]
    assert result["record"]["generated_observation"] == "부모의 원본 메모"
    assert result["record"]["status"] == "queued"
    queued = queue.get(result["record"]["job_id"])
    assert queued is not None
    assert queued.payload == {"child_id": str(child.id), "record_id": str(record.id)}
    with pytest.raises(HTTPException) as duplicate:
        photo_routes.retry_photo_record(record.id, settings, store)
    assert duplicate.value.status_code == 409
