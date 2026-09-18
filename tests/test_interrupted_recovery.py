"""Interrupted export/review recovery.

Parent review is a LangGraph human-in-the-loop interrupt; an interrupted review must resume
from the *persisted* checkpoint after a full process restart (new connection, new graph).
Backup export must be atomic: an interrupted export leaves no partial or corrupt destination.
"""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from growwise.backup import BackupService
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph


def _fresh_review_graph(db_path: Path):
    connection = sqlite3.connect(db_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return connection, build_material_review_graph(checkpointer=checkpointer)


def test_review_recovers_from_persisted_checkpoint_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "review-checkpoints.sqlite3"
    config = {"configurable": {"thread_id": "review-restart-1"}}

    # Process 1: start the review, hit the parent-review interrupt, then "crash".
    conn1, graph1 = _fresh_review_graph(db_path)
    first = graph1.invoke(
        {"material_id": "material-1", "child_id": "child-1", "title": "테스트 자료"},
        config=config,
    )
    assert first["__interrupt__"]
    conn1.close()
    del graph1, conn1  # simulate a full restart: nothing in memory survives

    # Process 2: brand-new connection + graph over the same on-disk checkpoint resumes.
    conn2, graph2 = _fresh_review_graph(db_path)
    resumed = graph2.invoke(
        Command(resume={"status": "approved", "note": "재시작 후 승인"}),
        config=config,
    )
    assert resumed["decision_status"] == "approved"
    assert resumed["decision_note"] == "재시작 후 승인"
    conn2.close()


def test_backup_export_is_atomic_on_interruption(tmp_path: Path, monkeypatch) -> None:
    records_root = tmp_path / "records"
    store = EntityStore(records_root, tmp_path / "index.sqlite3")
    store.save(ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9))
    destination = tmp_path / "out" / "backup.zip"

    # Interrupt the export midway (e.g. power loss while adding a record).
    original_write = zipfile.ZipFile.write

    def _boom(self, filename, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise OSError("interrupted during export")

    monkeypatch.setattr(zipfile.ZipFile, "write", _boom)

    with pytest.raises(OSError):
        BackupService().create(records_root=records_root, destination=destination)

    # No partial/corrupt destination, and no leftover temp files.
    assert not destination.exists()
    monkeypatch.setattr(zipfile.ZipFile, "write", original_write)
    leftovers = list((tmp_path / "out").glob("*.tmp")) if (tmp_path / "out").exists() else []
    assert leftovers == []

    # Recovery = re-run cleanly produces a valid archive.
    manifest = BackupService().create(records_root=records_root, destination=destination)
    assert manifest.record_count == 1
    assert zipfile.is_zipfile(destination)
