from __future__ import annotations

import base64
import shutil
from pathlib import Path

from growwise.api.child_profile_routes import (
    ChildAvatarUploadRequest,
    delete_child_avatar,
    upload_child_avatar,
)
from growwise.backup.cli import create_backup, restore_backup
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.domain.photo import PhotoAsset
from growwise.services.photo_activity import PhotoAssetStore
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )


def test_child_avatar_upload_preview_delete_and_backup_roundtrip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="프로필아이", nickname="프로필아이", stage=Stage.ELEMENTARY)
    store.save(child)

    updated = upload_child_avatar(
        child.id,
        ChildAvatarUploadRequest(
            filename="avatar.png",
            mime_type="image/png",
            data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        ),
        settings,
        store,
    )

    assert updated.avatar_asset_id is not None
    avatar_payload = store.index.get_entity(
        str(updated.avatar_asset_id),
        entity_type="photo_asset",
    )
    assert avatar_payload is not None
    avatar = PhotoAsset.model_validate(avatar_payload)
    assert avatar.relative_path.startswith(f"avatars/{child.id}/")
    asset_store = PhotoAssetStore(
        settings.assets_dir,
        max_file_bytes=settings.photo_max_file_bytes,
    )
    assert asset_store.read_verified(avatar) == _ONE_PIXEL_PNG

    created = create_backup(settings, "avatar-roundtrip.zip")
    assert created["manifest"]["asset_count"] == 1

    deleted = delete_child_avatar(child.id, settings, store)
    assert deleted.avatar_asset_id is None
    assert store.index.get_entity(str(avatar.id), entity_type="photo_asset") is None
    assert not (settings.assets_dir / avatar.relative_path).exists()

    restored = restore_backup(settings, "avatar-roundtrip.zip", confirmed=True)
    assert restored["restored"] is True
    restored_store = EntityStore(settings.records_dir, settings.index_path)
    restored_child = ChildProfile.model_validate(
        restored_store.index.get_entity(str(child.id), entity_type="child_profile")
    )
    assert restored_child.avatar_asset_id == avatar.id
    restored_asset = PhotoAsset.model_validate(
        restored_store.index.get_entity(str(avatar.id), entity_type="photo_asset")
    )
    assert (settings.assets_dir / restored_asset.relative_path).read_bytes() == _ONE_PIXEL_PNG


def test_child_purge_deletes_avatar_namespace(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="삭제아이", nickname="삭제아이", stage=Stage.ELEMENTARY)
    store.save(child)
    updated = upload_child_avatar(
        child.id,
        ChildAvatarUploadRequest(
            filename="avatar.png",
            mime_type="image/png",
            data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        ),
        settings,
        store,
    )
    assert updated.avatar_asset_id is not None
    avatar_dir = settings.assets_dir / "avatars" / str(child.id)
    assert avatar_dir.exists()

    result = ChildPurgeService(settings).purge(str(child.id))

    assert result.photo_files_deleted == 1
    assert not avatar_dir.exists()
    assert store.index.get_entity(str(updated.avatar_asset_id), entity_type="photo_asset") is None
