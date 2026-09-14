from pathlib import Path

import pytest

from growwise.backup.cli import (
    create_backup,
    list_backups,
    managed_archive_path,
    restore_backup,
    validate_archive_name,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_backup_name_rejects_path_traversal(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)

    for unsafe in ("../escape.zip", "nested/escape.zip", "\\escape.zip", "not-a-zip.txt"):
        with pytest.raises(ValueError):
            managed_archive_path(settings, unsafe)

    assert validate_archive_name("family-20260914.zip") == "family-20260914.zip"


def test_cli_helpers_create_list_and_restore_managed_backup(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    created = create_backup(settings, "baseline.zip")
    assert created["archive"] == "baseline.zip"
    assert (settings.backups_dir / "baseline.zip").is_file()
    assert [item["archive"] for item in list_backups(settings)] == ["baseline.zip"]

    replacement = ChildProfile(nickname="다른 아이", stage=Stage.INFANT_0_2, age_months=8)
    store.save(replacement)

    with pytest.raises(ValueError):
        restore_backup(settings, "baseline.zip", confirmed=False)

    restored = restore_backup(settings, "baseline.zip", confirmed=True)
    assert restored["restored"] is True

    rebuilt = EntityStore(settings.records_dir, settings.index_path)
    children = rebuilt.index.list_entities(entity_type="child_profile")
    assert [item["nickname"] for item in children] == ["아이"]
