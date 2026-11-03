from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uuid6 import uuid7

from growwise.api import photo_routes
from growwise.api.main import app
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoRecordStatus
from growwise.jobs import JobStatus, SQLiteJobQueue
from growwise.services.photo_activity import PhotoActivityService, PhotoAssetStore, PhotoUpload
from growwise.services.photo_jobs import PHOTO_ANALYSIS_JOB, PhotoJobRunner
from growwise.storage import EntityStore


@pytest.fixture
def setup(tmp_path: Path, monkeypatch):
    settings = Settings(data_dir=tmp_path, llm_features_enabled=False,
                        vision_features_enabled=False, embedding_features_enabled=False)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY)
    store.save(child)
    service = PhotoActivityService(
        store=store, asset_store=PhotoAssetStore(settings.assets_dir,
                                               max_file_bytes=settings.photo_max_file_bytes),
        text_provider=None, vision_provider=None, max_images=8,
    )
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    record, assets = service.prepare_draft(
        child_id=str(child.id), uploads=[PhotoUpload(filename="fixture.png",
                                                    mime_type="image/png", data=data)],
        user_context="부모가 남긴 원본 메모",
    )
    queue = SQLiteJobQueue(settings.jobs_path)
    runner = PhotoJobRunner(queue=queue, service_factory=lambda: service, lease_seconds=60,
                            max_attempts=3, poll_interval_seconds=.01)
    # Exercise the real startup recovery deterministically before allowing any new inference.
    monkeypatch.setattr(runner, "_run", lambda: None)
    monkeypatch.setattr(photo_routes, "get_photo_job_runner", lambda: runner)
    monkeypatch.setattr(photo_routes, "get_photo_text_provider", lambda: None)
    monkeypatch.setattr(photo_routes, "get_photo_vision_provider", lambda: None)
    yield settings, store, service, record, assets, queue, runner
    runner.stop()


def test_exhausted_interruption_becomes_retryable_and_preserves_photos_and_parent_text(setup):
    settings, store, service, record, assets, queue, runner = setup
    job = runner.submit(child_id=str(record.child_id), record_id=str(record.id))
    record = service.attach_job(record_id=str(record.id), job_id=job.id)
    for attempt in range(3):
        claimed = queue.claim_next(job_types=(PHOTO_ANALYSIS_JOB,), max_attempts=3)
        assert claimed is not None and claimed.attempts == attempt + 1
        if attempt < 2:
            queue.recover_running(job_type=PHOTO_ANALYSIS_JOB, max_attempts=3)
    record.status = PhotoRecordStatus.PROCESSING
    store.save(record)
    runner.start()
    assert queue.get(job.id).status is JobStatus.FAILED
    interrupted = service.get_record(str(record.id))
    assert interrupted.status is PhotoRecordStatus.FAILED
    assert interrupted.user_context == "부모가 남긴 원본 메모"
    assert interrupted.photo_asset_ids == record.photo_asset_ids
    assert interrupted.error_message and "다시 시도" in interrupted.error_message

    result = photo_routes.retry_photo_record(record.id, settings, store)
    assert result["record"]["status"] == "queued"
    retry = queue.claim_next(job_types=(PHOTO_ANALYSIS_JOB,), max_attempts=3)
    assert retry is not None and retry.id != job.id and retry.attempts == 1
    runner._process(retry)
    assert queue.get(retry.id).status is JobStatus.COMPLETED
    assert service.get_record(str(record.id)).status is PhotoRecordStatus.DRAFT
    log = service.commit(record_id=str(record.id), observation="부모가 확인한 기록")
    assert log.parent_observation == "부모가 확인한 기록"
    assert service.asset_store.read_verified(assets[0])


@pytest.mark.parametrize(
    "job_state", ["missing", "cancelled", "completed", "failed", "wrong_scope"],
)
def test_terminal_missing_or_foreign_job_never_leaves_a_photo_running(setup, job_state):
    _settings, store, service, record, _assets, queue, runner = setup
    if job_state != "missing":
        job = queue.enqueue(PHOTO_ANALYSIS_JOB, {
            "child_id": str(uuid7()) if job_state == "wrong_scope" else str(record.child_id),
            "record_id": str(record.id),
        })
        record = service.attach_job(record_id=str(record.id), job_id=job.id)
        claimed = queue.claim_next(job_types=(PHOTO_ANALYSIS_JOB,))
        assert claimed is not None and claimed.claim_token
        if job_state == "cancelled":
            queue.cancel(job.id)
        elif job_state == "completed":
            queue.complete(job.id, claimed.claim_token)
        elif job_state == "failed":
            queue.fail(job.id, claimed.claim_token, "private provider detail must not leak")
    record.status = PhotoRecordStatus.PROCESSING
    store.save(record)
    runner.start()
    recovered = service.get_record(str(record.id))
    assert recovered.status is PhotoRecordStatus.FAILED
    assert "private provider" not in (recovered.error_message or "")
    assert recovered.generated_observation == record.generated_observation


def test_recoverable_interruption_is_requeued_but_parent_review_states_are_untouched(setup):
    _settings, store, service, record, _assets, queue, runner = setup
    job = runner.submit(child_id=str(record.child_id), record_id=str(record.id))
    record = service.attach_job(record_id=str(record.id), job_id=job.id)
    assert queue.claim_next(job_types=(PHOTO_ANALYSIS_JOB,))
    record.status = PhotoRecordStatus.PROCESSING
    store.save(record)
    reviewed = []
    for status in (
        PhotoRecordStatus.DRAFT, PhotoRecordStatus.COMMITTED, PhotoRecordStatus.DISCARDED,
    ):
        kept = record.model_copy(update={"id": uuid7(), "status": status,
                                         "generated_observation": "부모가 확인한 본문"})
        store.save(kept)
        reviewed.append(kept)
    runner.start()
    assert queue.get(job.id).status is JobStatus.PENDING
    assert service.get_record(str(record.id)).status is PhotoRecordStatus.QUEUED
    for kept in reviewed:
        assert service.get_record(str(kept.id)).model_dump() == kept.model_dump()


def test_recovery_pages_pending_sources_without_history_scan(setup, monkeypatch):
    _settings, store, service, record, _assets, _queue, runner = setup
    for _ in range(102):
        store.save(record.model_copy(update={"id": uuid7()}))
    monkeypatch.setattr(store.index, "list_entities",
                        lambda **_kw: pytest.fail("full history scan"))
    runner.start()
    assert store.index.pending_photo_entities() == []
    assert service.get_record(str(record.id)).status is PhotoRecordStatus.FAILED


def test_recovery_rereads_parent_decision_under_child_lock(setup, monkeypatch):
    _settings, store, service, record, _assets, _queue, runner = setup
    original = store.index.pending_photo_entities
    def page(**kwargs):
        rows = original(**kwargs)
        if rows:
            latest = service.get_record(str(record.id))
            latest.status = PhotoRecordStatus.COMMITTED
            latest.generated_observation = "부모가 이미 확정한 내용"
            store.save(latest)
        return rows
    monkeypatch.setattr(store.index, "pending_photo_entities", page)
    runner.start()
    kept = service.get_record(str(record.id))
    assert kept.status is PhotoRecordStatus.COMMITTED
    assert kept.generated_observation == "부모가 이미 확정한 내용"


def test_first_submission_restores_queued_status_after_missing_job_recovery(setup):
    settings, store, service, record, assets, queue, runner = setup
    result = photo_routes._finalize_photo_create(
        child_id=record.child_id, record=record, assets=assets, shared_child_ids=[],
        manual_text="", can_assist=True, settings=settings, store=store, ai_service=service,
    )
    assert result["record"]["status"] == "queued"
    assert result["record"]["job_id"] == result["job"]["id"]
    assert queue.get(result["job"]["id"]).status is JobStatus.PENDING


def test_opening_restored_photo_library_exposes_recovery_and_http_retry(setup):
    settings, store, _service, record, _assets, _queue, _runner = setup
    # Operational jobs are disposable after restore; an original queued photo can have no job.
    overrides = {
        photo_routes.get_photo_settings: lambda: settings,
        photo_routes.get_photo_store: lambda: store,
    }
    app.dependency_overrides.update(overrides)
    try:
        client = TestClient(app)
        library = client.get(f"/v1/children/{record.child_id}/photo-records")
        assert library.status_code == 200
        assert library.json()[0]["status"] == "failed"
        retry = client.post(f"/v1/photo-records/{record.id}/retry")
        assert retry.status_code == 202, retry.text
        assert retry.json()["record"]["status"] == "queued"
        assert retry.json()["record"]["photo_asset_ids"] == [str(record.photo_asset_ids[0])]
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)
