from __future__ import annotations

import errno
from pathlib import Path

from growwise.backup import BackupService
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_restore_keeps_atomic_swaps_with_assets_on_another_volume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    service = BackupService()

    source_root = tmp_path / "source" / "records"
    source_assets = tmp_path / "source" / "assets"
    source_assets.mkdir(parents=True)
    (source_assets / "photo.jpg").write_bytes(b"new-photo")
    source_store = EntityStore(source_root, tmp_path / "source.sqlite3")
    source_store.save(ChildProfile(nickname="복원본", stage=Stage.INFANT_0_2, age_months=8))
    archive = tmp_path / "backup.zip"
    service.create(
        records_root=source_root,
        assets_root=source_assets,
        destination=archive,
    )

    records_volume = tmp_path / "records-volume"
    assets_volume = tmp_path / "assets-volume"
    target_root = records_volume / "records"
    target_assets = assets_volume / "assets"
    target_assets.mkdir(parents=True)
    (target_assets / "photo.jpg").write_bytes(b"old-photo")
    target_store = EntityStore(target_root, records_volume / "index.sqlite3")
    target_store.save(ChildProfile(nickname="이전본", stage=Stage.INFANT_0_2, age_months=7))

    real_replace = Path.replace

    def _volume(path: Path) -> str | None:
        absolute = path.absolute()
        records_absolute = records_volume.absolute()
        assets_absolute = assets_volume.absolute()
        if absolute == records_absolute or records_absolute in absolute.parents:
            return "records"
        if absolute == assets_absolute or assets_absolute in absolute.parents:
            return "assets"
        return None

    def reject_cross_volume_replace(self: Path, target: Path | str) -> Path:
        source_volume = _volume(self)
        target_volume = _volume(Path(target))
        if source_volume is not None and target_volume is not None and source_volume != target_volume:
            raise OSError(errno.EXDEV, "simulated cross-device rename")
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", reject_cross_volume_replace)

    service.restore(
        archive_path=archive,
        records_root=target_root,
        index_path=records_volume / "index.sqlite3",
        assets_root=target_assets,
    )

    assert (target_assets / "photo.jpg").read_bytes() == b"new-photo"
    restored_children = EntityStore(target_root, records_volume / "index.sqlite3").list_by_type(
        "child_profile"
    )
    assert len(restored_children) == 1
    assert restored_children[0].get("nickname") == "복원본"
