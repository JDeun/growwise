from __future__ import annotations

import base64
from pathlib import Path

import pytest

from growwise.api import photo_routes
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.services.photo_activity import (
    PhotoActivityService,
    PhotoAssetStore,
    PhotoUpload,
)
from growwise.storage import EntityStore

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class VisionSpy:
    model = "vision-spy"

    def __init__(self) -> None:
        self.contexts: list[str] = []

    def caption(self, *, image_base64: str, mime_type: str, context: str) -> str:
        assert image_base64
        assert mime_type == "image/png"
        self.contexts.append(context)
        return "블록과 손이 보이는 활동 사진"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        llm_features_enabled=True,
        vision_features_enabled=True,
        embedding_features_enabled=False,
    )


def test_manual_photo_api_never_touches_ai_providers_or_job_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2)
    store.save(child)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("manual photo mode must not touch AI infrastructure")

    monkeypatch.setattr(photo_routes, "get_photo_text_provider", forbidden)
    monkeypatch.setattr(photo_routes, "get_photo_vision_provider", forbidden)
    monkeypatch.setattr(photo_routes, "get_photo_job_runner", forbidden)

    manual_text = "종이컵을 여러 번 포개고 다시 꺼내며 놀았다."
    request = photo_routes.PhotoDraftRequest(
        files=[
            photo_routes.PhotoUploadInput(
                filename="play.png",
                mime_type="image/png",
                data_base64=base64.b64encode(_ONE_PIXEL_PNG).decode("ascii"),
            )
        ],
        manual_observation=manual_text,
        ai_assist=False,
    )

    response = photo_routes.create_photo_record(
        child_id=child.id,
        request=request,
        settings=settings,
        store=store,
    )

    assert response["job"] is None
    record = response["record"]
    assert isinstance(record, dict)
    assert record["generation_mode"] == "manual_photo_diary"
    assert record["generated_observation"] == manual_text
    assert record["status"] == "draft"


def test_vision_caption_receives_image_only_not_parent_note(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    child = ChildProfile(nickname="아이", stage=Stage.INFANT_0_2)
    store.save(child)
    vision = VisionSpy()
    service = PhotoActivityService(
        store=store,
        asset_store=PhotoAssetStore(
            settings.assets_dir,
            max_file_bytes=settings.photo_max_file_bytes,
        ),
        text_provider=None,
        vision_provider=vision,  # type: ignore[arg-type]
        max_images=settings.photo_max_images_per_record,
    )

    parent_note = "부모만 작성한 비공개 메모"
    record, assets = service.create_draft(
        child_id=str(child.id),
        uploads=[
            PhotoUpload(
                filename="play.png",
                mime_type="image/png",
                data=_ONE_PIXEL_PNG,
            )
        ],
        user_context=parent_note,
    )

    assert vision.contexts == [""]
    assert parent_note not in (assets[0].caption or "")
    assert parent_note in record.generated_observation
