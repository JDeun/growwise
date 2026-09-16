from __future__ import annotations

import base64
import threading
import time
from pathlib import Path

from growwise.api.main import app
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoRecordStatus
from growwise.jobs import JobStatus, SQLiteJobQueue
from growwise.services.photo_activity import PhotoActivityService, PhotoAssetStore, PhotoUpload
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB, PhotoJobRunner
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
        photo_job_poll_interval_seconds=0.1,
    )


def _child(store: EntityStore) -> ChildProfile:
    child = ChildProfile(name="샘플아이", nickname="샘플아이", stage=Stage.INFANT_0_2)
    store.save(child)
    return child


def _service(
    settings: Settings,
    *,
    vision_provider=None,
) -> tuple[PhotoActivityService, EntityStore]:
    store = EntityStore(settings.records_dir, settings.index_path)
    return (
        PhotoActivityService(
            store=store,
            asset_store=PhotoAssetStore(
                settings.assets_dir,
                max_file_bytes=settings.photo_max_file_bytes,
            ),
            text_provider=None,
            vision_provider=vision_provider,
            max_images=settings.photo_max_images_per_record,
        ),
        store,
    )


def _upload() -> PhotoUpload:
    return PhotoUpload(filename="play.png", mime_type="image/png", data=_ONE_PIXEL_PNG)


def test_queue_recovers_interrupted_jobs_with_bounded_attempts(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    original = queue.enqueue(PHOTO_ANALYSIS_JOB, {"child_id": "child", "record_id": "record"})

    first = queue.claim_next(
        job_types=(PHOTO_ANALYSIS_JOB,),
        lease_seconds=3600,
        max_attempts=2,
    )
    assert first is not None
    assert first.id == original.id
    assert first.status is JobStatus.RUNNING
    assert first.attempts == 1

    assert queue.recover_running(job_type=PHOTO_ANALYSIS_JOB, max_attempts=2) == 1
    recovered = queue.get(original.id)
    assert recovered is not None
    assert recovered.status is JobStatus.PENDING

    second = queue.claim_next(
        job_types=(PHOTO_ANALYSIS_JOB,),
        lease_seconds=3600,
        max_attempts=2,
    )
    assert second is not None
    assert second.attempts == 2
    assert queue.recover_running(job_type=PHOTO_ANALYSIS_JOB, max_attempts=2) == 1
    exhausted = queue.get(original.id)
    assert exhausted is not None
    assert exhausted.status is JobStatus.FAILED


def test_photo_worker_returns_request_to_queue_then_builds_draft(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service, store = _service(settings)
    child = _child(store)
    record, _assets = service.prepare_draft(
        child_id=str(child.id),
        uploads=[_upload()],
        user_context="블록을 함께 쌓았다.",
    )
    assert record.status is PhotoRecordStatus.QUEUED

    queue = SQLiteJobQueue(settings.jobs_path)
    runner = PhotoJobRunner(
        queue=queue,
        service_factory=lambda: service,
        lease_seconds=60,
        max_attempts=3,
        poll_interval_seconds=0.05,
    )
    job = runner.submit(child_id=str(child.id), record_id=str(record.id))
    service.attach_job(record_id=str(record.id), job_id=job.id)
    assert job.payload == {"child_id": str(child.id), "record_id": str(record.id)}
    assert "data_base64" not in str(job.payload)

    runner.start()
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            current = service.get_record(str(record.id))
            queued_job = queue.get(job.id)
            if (
                current.status is PhotoRecordStatus.DRAFT
                and queued_job is not None
                and queued_job.status is JobStatus.COMPLETED
            ):
                break
            time.sleep(0.02)
        else:
            raise AssertionError("background photo job did not complete")
    finally:
        runner.stop()

    current = service.get_record(str(record.id))
    assert current.status is PhotoRecordStatus.DRAFT
    assert "블록을 함께" in current.generated_observation


def test_child_purge_during_slow_caption_does_not_resurrect_photo_data(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    class SlowVision:
        model = "slow-test-vision"

        def __init__(self) -> None:
            self.started = threading.Event()
            self.release = threading.Event()

        def caption(self, **_kwargs: str) -> str:
            self.started.set()
            if not self.release.wait(timeout=3):
                raise TimeoutError("test vision release was not signalled")
            return "블록과 손이 보인다."

    vision = SlowVision()
    service, store = _service(settings, vision_provider=vision)
    child = _child(store)
    record, _assets = service.prepare_draft(
        child_id=str(child.id),
        uploads=[_upload()],
        user_context="블록 놀이",
    )

    queue = SQLiteJobQueue(settings.jobs_path)
    runner = PhotoJobRunner(
        queue=queue,
        service_factory=lambda: service,
        lease_seconds=60,
        max_attempts=2,
        poll_interval_seconds=0.05,
    )
    job = runner.submit(child_id=str(child.id), record_id=str(record.id))
    service.attach_job(record_id=str(record.id), job_id=job.id)
    runner.start()
    try:
        assert vision.started.wait(timeout=2)
        result = ChildPurgeService(settings).purge(str(child.id))
        assert result.child_id == str(child.id)
        vision.release.set()
        time.sleep(0.15)
    finally:
        vision.release.set()
        runner.stop()

    verification_store = EntityStore(settings.records_dir, settings.index_path)
    assert verification_store.index.get_entity(str(child.id), entity_type="child_profile") is None
    assert verification_store.index.list_entities(child_id=str(child.id)) == []
    assert not (settings.photo_assets_dir / str(child.id)).exists()


def test_photo_and_privacy_routes_are_registered_on_core_app() -> None:
    paths = {route.path for route in app.routes}
    assert "/v1/children/{child_id}/photo-records" in paths
    assert "/v1/photo-records/{record_id}/commit" in paths
    assert "/v1/children/{child_id}" in paths
