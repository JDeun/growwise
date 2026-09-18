from __future__ import annotations

import base64
import shutil
from pathlib import Path

from growwise.api.child_profile_routes import ChildAvatarRequest, update_child_avatar
from growwise.backup.cli import create_backup, restore_backup
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.services.photo_activity import PhotoActivityService, PhotoAssetStore, PhotoUpload
from growwise.services.privacy import ChildPurgeService
from growwise.storage import EntityStore

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _create_photo(settings: Settings, child: ChildProfile) -> tuple[str, str]:
    store = EntityStore(settings.records_dir, settings.index_path)
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
    record, assets = service.create_draft(
        child_id=str(child.id),
        uploads=[PhotoUpload(filename="activity.png", mime_type="image/png", data=_ONE_PIXEL_PNG)],
        user_context="사진 백업 테스트",
    )
    return str(record.id), str(assets[0].id)


def test_portable_backup_roundtrips_photo_assets(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="샘플아이", stage=Stage.INFANT_0_2)
    store.save(child)
    record_id, asset_id = _create_photo(settings, child)

    created = create_backup(settings, "photo-roundtrip.zip")
    assert created["manifest"]["asset_count"] == 1

    shutil.rmtree(settings.records_dir)
    shutil.rmtree(settings.assets_dir)
    settings.index_path.unlink(missing_ok=True)

    restored = restore_backup(settings, "photo-roundtrip.zip", confirmed=True)
    assert restored["restored"] is True

    restored_store = EntityStore(settings.records_dir, settings.index_path)
    record = restored_store.index.get_entity(record_id, entity_type="photo_activity_record")
    asset = restored_store.index.get_entity(asset_id, entity_type="photo_asset")
    assert record is not None
    assert asset is not None
    assert (settings.assets_dir / asset["relative_path"]).read_bytes() == _ONE_PIXEL_PNG


def test_child_purge_deletes_photo_binaries_and_metadata(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="삭제아이", stage=Stage.INFANT_0_2)
    sibling = ChildProfile(name="보존아이", stage=Stage.INFANT_0_2)
    store.save(child)
    store.save(sibling)
    _record_id, asset_id = _create_photo(settings, child)
    _sibling_record, sibling_asset_id = _create_photo(settings, sibling)

    result = ChildPurgeService(settings).purge(str(child.id))

    assert result.photo_files_deleted == 1
    assert not (settings.photo_assets_dir / str(child.id)).exists()
    assert (settings.photo_assets_dir / str(sibling.id)).exists()
    assert store.index.get_entity(asset_id, entity_type="photo_asset") is None
    assert store.index.get_entity(sibling_asset_id, entity_type="photo_asset") is not None



def _set_avatar(settings: Settings, child: ChildProfile) -> tuple[str, Path]:
    store = EntityStore(settings.records_dir, settings.index_path)
    updated = update_child_avatar(
        child.id,
        ChildAvatarRequest(
            filename="avatar.png",
            mime_type="image/png",
            data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        ),
        settings,
        store,
    )
    assert updated.avatar_asset_id is not None
    payload = store.index.get_entity(str(updated.avatar_asset_id), entity_type="photo_asset")
    assert payload is not None
    return str(updated.avatar_asset_id), settings.assets_dir / payload["relative_path"]


def test_portable_backup_roundtrips_child_avatar(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="아바타아이", stage=Stage.ELEMENTARY)
    store.save(child)
    avatar_id, avatar_path = _set_avatar(settings, child)
    assert avatar_path.read_bytes() == _ONE_PIXEL_PNG

    create_backup(settings, "avatar-roundtrip.zip")
    shutil.rmtree(settings.records_dir)
    shutil.rmtree(settings.assets_dir)
    settings.index_path.unlink(missing_ok=True)

    restored = restore_backup(settings, "avatar-roundtrip.zip", confirmed=True)
    assert restored["restored"] is True

    restored_store = EntityStore(settings.records_dir, settings.index_path)
    restored_child_payload = restored_store.index.get_entity(
        str(child.id),
        entity_type="child_profile",
    )
    assert restored_child_payload is not None
    assert restored_child_payload["avatar_asset_id"] == avatar_id
    asset = restored_store.index.get_entity(avatar_id, entity_type="photo_asset")
    assert asset is not None
    assert (settings.assets_dir / asset["relative_path"]).read_bytes() == _ONE_PIXEL_PNG


def test_child_purge_deletes_avatar_binary_and_metadata(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path / "data",
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(name="삭제아바타", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(name="보존아바타", stage=Stage.ELEMENTARY)
    store.save(child)
    store.save(sibling)
    avatar_id, avatar_path = _set_avatar(settings, child)
    sibling_avatar_id, sibling_avatar_path = _set_avatar(settings, sibling)

    ChildPurgeService(settings).purge(str(child.id))

    assert not avatar_path.exists()
    assert sibling_avatar_path.exists()
    assert store.index.get_entity(avatar_id, entity_type="photo_asset") is None
    assert store.index.get_entity(sibling_avatar_id, entity_type="photo_asset") is not None
