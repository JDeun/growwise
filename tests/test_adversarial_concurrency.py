from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

import growwise.storage.markdown as markdown_module
from growwise.domain import ChildProfile, Stage
from growwise.idempotency import SQLiteIdempotencyStore, request_fingerprint
from growwise.storage.markdown import MarkdownRepository


def test_idempotency_claim_has_exactly_one_owner_under_real_thread_race(tmp_path: Path) -> None:
    path = tmp_path / "idempotency.sqlite3"
    SQLiteIdempotencyStore(path)  # create the schema before the start barrier
    workers = 16
    barrier = Barrier(workers + 1)
    fingerprint = request_fingerprint({"observation": "동시성 합성 요청"})

    def claim(index: int):
        store = SQLiteIdempotencyStore(path)
        barrier.wait(timeout=10)
        return store.claim(
            key="thread-race",
            request_hash=fingerprint,
            resource_type="learning_log",
            resource_id=f"log-{index}",
            lease_seconds=60,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(claim, index) for index in range(workers)]
        barrier.wait(timeout=10)
        claims = [future.result(timeout=30) for future in futures]

    owners = [claim for claim in claims if claim.acquired]
    assert len(owners) == 1
    assert len({claim.record.resource_id for claim in claims}) == 1
    assert all(claim.record.status.value == "pending" for claim in claims)


def test_markdown_same_entity_writes_never_tear_under_real_thread_race(tmp_path: Path) -> None:
    root = tmp_path / "records"
    repository = MarkdownRepository(root)
    profile = ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY, notes="initial")
    path = repository.save(profile)

    workers = 16
    barrier = Barrier(workers + 1)
    expected_notes = {f"writer-{index}" for index in range(workers)}

    def write(index: int) -> None:
        local = MarkdownRepository(root)
        candidate = profile.model_copy(update={"notes": f"writer-{index}"})
        barrier.wait(timeout=10)
        local.save(candidate)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(write, index) for index in range(workers)]
        barrier.wait(timeout=10)
        for future in futures:
            future.result(timeout=30)

    current = repository.load(path, ChildProfile)
    previous = repository.load(repository.backup_path(path), ChildProfile)
    assert current.notes in expected_notes
    assert previous.notes in expected_notes
    assert current.notes != previous.notes


def test_atomic_markdown_save_preserves_previous_generation_when_final_rename_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    original = ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY, notes="before")
    target = repository.save(original)
    replacement = original.model_copy(update={"notes": "after"})

    real_replace = os.replace

    def fail_live_replace(source, destination):
        if Path(destination) == target:
            raise OSError("synthetic final rename failure")
        return real_replace(source, destination)

    monkeypatch.setattr(markdown_module.os, "replace", fail_live_replace)
    with pytest.raises(OSError, match="synthetic final rename failure"):
        repository.save(replacement)

    assert repository.load(target, ChildProfile).notes == "before"
    assert repository.load(repository.backup_path(target), ChildProfile).notes == "before"


def test_atomic_markdown_save_preserves_previous_generation_when_fsync_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    original = ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY, notes="before")
    target = repository.save(original)
    replacement = original.model_copy(update={"notes": "after"})

    def fail_fsync(_fd: int) -> None:
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(markdown_module.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="synthetic fsync failure"):
        repository.save(replacement)

    assert repository.load(target, ChildProfile).notes == "before"
