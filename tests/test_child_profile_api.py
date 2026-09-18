import base64
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from growwise.api.child_profile_routes import (
    ChildAvatarRequest,
    ChildProfileUpdateRequest,
    delete_child_avatar,
    update_child_avatar,
    update_child_profile,
)
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.storage import EntityStore


def test_update_child_profile_preserves_identity_and_updates_learning_context(
    tmp_path: Path,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(
        nickname="별이",
        stage=Stage.INFANT_0_2,
        age_months=8,
        interests=["그림책"],
        preferences={"books": ["동물"]},
    )
    store.save(child)

    updated = update_child_profile(
        child.id,
        ChildProfileUpdateRequest(
            nickname="별",
            stage=Stage.PRESCHOOL_3_5,
            age_months=36,
            interests=["공룡", "그림"],
            primary_language="ko-KR",
            additional_languages=["en-US"],
            learning_goals=["읽은 내용을 자기 말로 설명하기"],
            notes="부모가 필요할 때만 남기는 메모",
        ),
        store,
    )

    assert updated.id == child.id
    assert updated.nickname == "별"
    assert updated.name == "별"
    assert updated.stage is Stage.PRESCHOOL_3_5
    assert updated.age_months == 36
    assert updated.interests == ["공룡", "그림"]
    assert updated.primary_language == "ko-KR"
    assert updated.additional_languages == ["en-US"]
    assert updated.learning_goals == ["읽은 내용을 자기 말로 설명하기"]
    assert updated.notes == "부모가 필요할 때만 남기는 메모"
    assert updated.preferences == {"books": ["동물"]}
    assert updated.updated_at >= child.updated_at

    stored = ChildProfile.model_validate(
        store.index.get_entity(str(child.id), entity_type="child_profile")
    )
    assert stored.nickname == "별"
    assert stored.learning_goals == ["읽은 내용을 자기 말로 설명하기"]


def test_update_child_profile_rejects_missing_child_and_invalid_age(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    request = ChildProfileUpdateRequest(
        nickname="아이",
        stage=Stage.ELEMENTARY,
        age_months=120,
    )

    with pytest.raises(HTTPException) as exc_info:
        update_child_profile(uuid4(), request, store)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "child_not_found"

    with pytest.raises(ValidationError):
        ChildProfileUpdateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            age_months=241,
        )



_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_child_avatar_roundtrip_updates_profile_and_managed_asset(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="별이", stage=Stage.ELEMENTARY)
    store.save(child)

    updated = update_child_avatar(
        child.id,
        ChildAvatarRequest(
            filename="profile.png",
            mime_type="image/png",
            data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        ),
        settings,
        store,
    )

    assert updated.avatar_asset_id is not None
    asset_payload = store.index.get_entity(
        str(updated.avatar_asset_id),
        entity_type="photo_asset",
    )
    assert asset_payload is not None
    assert asset_payload["child_id"] == str(child.id)
    assert asset_payload["relative_path"].startswith(f"avatars/{child.id}/")
    asset_path = settings.assets_dir / asset_payload["relative_path"]
    assert asset_path.read_bytes() == _ONE_PIXEL_PNG

    cleared = delete_child_avatar(child.id, settings, store)

    assert cleared.avatar_asset_id is None
    assert not asset_path.exists()
    assert (
        store.index.get_entity(str(updated.avatar_asset_id), entity_type="photo_asset")
        is None
    )


def test_replacing_child_avatar_removes_previous_binary_and_metadata(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path / "data")
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="별이", stage=Stage.ELEMENTARY)
    store.save(child)

    first = update_child_avatar(
        child.id,
        ChildAvatarRequest(
            filename="first.png",
            mime_type="image/png",
            data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
        ),
        settings,
        store,
    )
    assert first.avatar_asset_id is not None
    first_payload = store.index.get_entity(
        str(first.avatar_asset_id),
        entity_type="photo_asset",
    )
    assert first_payload is not None
    first_path = settings.assets_dir / first_payload["relative_path"]

    second_bytes = _ONE_PIXEL_PNG + b"\n"
    with pytest.raises(HTTPException):
        update_child_avatar(
            child.id,
            ChildAvatarRequest(
                filename="invalid.png",
                mime_type="image/png",
                data_base64=base64.b64encode(second_bytes).decode("ascii"),
            ),
            settings,
            store,
        )

    # A rejected replacement cannot damage the current avatar.
    current = ChildProfile.model_validate(
        store.index.get_entity(str(child.id), entity_type="child_profile")
    )
    assert current.avatar_asset_id == first.avatar_asset_id
    assert first_path.read_bytes() == _ONE_PIXEL_PNG
