from __future__ import annotations

import base64
import io
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from growwise.api import main, photo_routes
from growwise.config import Settings
from growwise.domain import ChildProfile, Stage
from growwise.services.photo_activity import PhotoAssetStore, PhotoUpload, PhotoValidationError
from growwise.services.photo_image_validation import PhotoImageValidationError
from growwise.services.photo_thumbnail import THUMBNAIL_EDGE, THUMBNAIL_MAX_BYTES, photo_thumbnail
from growwise.storage import EntityStore


def jpeg(width=1600, height=1000) -> bytes:
    with Image.new("RGB", (width, height), "#39745d") as image:
        exif = Image.Exif()
        exif[274] = 6
        exif[315] = "private parent metadata"
        output = io.BytesIO()
        image.save(output, format="JPEG", exif=exif)
        return output.getvalue()


def test_http_thumbnail_is_small_oriented_metadata_free_and_preserves_private_original(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(data_dir=tmp_path)
    store = EntityStore(settings.records_dir, settings.index_path)
    owner = ChildProfile(nickname="사진 소유 아이", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="다른 아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    original = jpeg()
    asset_store = PhotoAssetStore(settings.assets_dir, max_file_bytes=settings.photo_max_file_bytes)
    asset, _ = asset_store.store(
        child_id=str(owner.id),
        upload=PhotoUpload(
            filename="private.jpg",
            mime_type="image/jpeg",
            data=original,
        ),
    )
    store.save(asset)
    monkeypatch.setitem(
        main.app.dependency_overrides, photo_routes.get_photo_settings, lambda: settings
    )
    monkeypatch.setitem(main.app.dependency_overrides, photo_routes.get_photo_store, lambda: store)
    client = TestClient(main.app)
    path = f"/v1/children/{owner.id}/photo-assets/{asset.id}/thumbnail"
    response = client.get(path)
    assert response.status_code == 200, response.text
    body = response.json()
    thumbnail = base64.b64decode(body["data_base64"])
    assert body["mime_type"] == "image/jpeg"
    assert max(body["width"], body["height"]) <= THUMBNAIL_EDGE
    assert body["width"] < body["height"]  # EXIF 90-degree orientation retained visually.
    assert len(thumbnail) <= THUMBNAIL_MAX_BYTES
    assert thumbnail != original
    with Image.open(io.BytesIO(thumbnail)) as decoded:
        assert decoded.format == "JPEG"
        assert not decoded.getexif()
    assert asset_store.read_verified(asset) == original

    def forbidden_read(*_args):
        raise AssertionError("must authorize before reading another child's original")

    with monkeypatch.context() as guard:
        guard.setattr(PhotoAssetStore, "read_verified", forbidden_read)
        denied = client.get(f"/v1/children/{sibling.id}/photo-assets/{asset.id}/thumbnail")
        assert denied.status_code == 404
    (settings.assets_dir / asset.relative_path).write_bytes(b"tampered original")
    assert client.get(path).status_code == 409


def test_thumbnail_rejects_image_bombs_before_decoding() -> None:
    oversized_png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + struct.pack(">II", 100_000, 100_000)
    with pytest.raises(PhotoImageValidationError, match="image_dimensions_too_large"):
        photo_thumbnail(
            lambda: oversized_png, max_width=16384, max_height=16384, max_pixels=64_000_000
        )


def test_verified_asset_read_bounds_tampered_files_before_hashing(tmp_path: Path) -> None:
    asset_store = PhotoAssetStore(tmp_path, max_file_bytes=1024)
    asset, _ = asset_store.store(
        child_id="11111111-2222-4333-8444-555555555555",
        upload=PhotoUpload(
            filename="small.jpg",
            mime_type="image/jpeg",
            data=jpeg(1, 1),
        ),
    )
    with (tmp_path / asset.relative_path).open("r+b") as handle:
        handle.truncate(1025)
    with pytest.raises(PhotoValidationError, match="image_too_large"):
        asset_store.read_verified(asset)


def test_thumbnail_original_reads_and_decoders_do_not_run_in_parallel() -> None:
    original = jpeg(32, 24)
    lock = threading.Lock()
    active = 0
    peak = 0

    def read():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return original

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: photo_thumbnail(
                    read,
                    max_width=16384,
                    max_height=16384,
                    max_pixels=64_000_000,
                ),
                range(8),
            )
        )
    assert peak == 1
    assert all(len(result[0]) <= THUMBNAIL_MAX_BYTES for result in results)
