from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from growwise.backup import BackupService, InvalidBackup
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_backup_restores_markdown_and_rebuilds_projection(tmp_path: Path) -> None:
    source_root = tmp_path / "source-records"
    source_index = tmp_path / "source.sqlite3"
    source_store = EntityStore(source_root, source_index)
    child = ChildProfile(nickname="수아", stage=Stage.INFANT_0_2, age_months=9)
    source_store.save(child)

    archive = tmp_path / "growwise-backup.zip"
    service = BackupService()
    manifest = service.create(records_root=source_root, destination=archive)
    assert manifest.record_count == 1

    restored_root = tmp_path / "restored-records"
    restored_index = tmp_path / "restored.sqlite3"
    service.restore(
        archive_path=archive,
        records_root=restored_root,
        index_path=restored_index,
    )

    restored_store = EntityStore(restored_root, restored_index)
    payload = restored_store.index.get_entity(str(child.id), entity_type="child_profile")
    assert payload is not None
    assert payload["nickname"] == "수아"


def test_backup_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.zip"
    manifest = {
        "format_version": 1,
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "record_count": 0,
    }
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("manifest.json", json.dumps(manifest))
        output.writestr("../escape.txt", "nope")

    with pytest.raises(InvalidBackup, match="unsafe archive member"):
        BackupService().restore(
            archive_path=archive,
            records_root=tmp_path / "records",
            index_path=tmp_path / "index.sqlite3",
        )
