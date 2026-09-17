from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api.photo_routes import PhotoDraftRequest, PhotoUploadInput, _decode_uploads
from growwise.config import Settings
from growwise.services.photo_image_validation import (
    PhotoImageValidationError,
    image_dimensions,
    validate_image_dimensions,
)

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _vp8x(width: int, height: int) -> bytes:
    data = bytearray(30)
    data[:4] = b"RIFF"
    data[4:8] = (22).to_bytes(4, "little")
    data[8:12] = b"WEBP"
    data[12:16] = b"VP8X"
    data[16:20] = (10).to_bytes(4, "little")
    data[24:27] = (width - 1).to_bytes(3, "little")
    data[27:30] = (height - 1).to_bytes(3, "little")
    return bytes(data)


def _vp8(width: int, height: int) -> bytes:
    data = bytearray(30)
    data[:4] = b"RIFF"
    data[4:8] = (22).to_bytes(4, "little")
    data[8:12] = b"WEBP"
    data[12:16] = b"VP8 "
    data[16:20] = (10).to_bytes(4, "little")
    data[23:26] = b"\x9d\x01\x2a"
    data[26:28] = width.to_bytes(2, "little")
    data[28:30] = height.to_bytes(2, "little")
    return bytes(data)


def _vp8l(width: int, height: int) -> bytes:
    width_bits = width - 1
    height_bits = height - 1
    data = bytearray(25)
    data[:4] = b"RIFF"
    data[4:8] = (17).to_bytes(4, "little")
    data[8:12] = b"WEBP"
    data[12:16] = b"VP8L"
    data[16:20] = (5).to_bytes(4, "little")
    data[20] = 0x2F
    data[21] = width_bits & 0xFF
    data[22] = ((width_bits >> 8) & 0x3F) | ((height_bits & 0x03) << 6)
    data[23] = (height_bits >> 2) & 0xFF
    data[24] = (height_bits >> 10) & 0x0F
    return bytes(data)


def _png_with_dimensions(width: int, height: int) -> bytes:
    data = bytearray(_ONE_PIXEL_PNG)
    data[16:20] = width.to_bytes(4, "big")
    data[20:24] = height.to_bytes(4, "big")
    return bytes(data)


def test_image_dimensions_reads_png_and_all_supported_webp_headers() -> None:
    assert image_dimensions(_ONE_PIXEL_PNG) == (1, 1)
    assert image_dimensions(_vp8x(1920, 1080)) == (1920, 1080)
    assert image_dimensions(_vp8(1280, 720)) == (1280, 720)
    assert image_dimensions(_vp8l(640, 480)) == (640, 480)


def test_image_dimension_guard_rejects_small_compressed_gigapixel_header() -> None:
    malicious = _png_with_dimensions(100_000, 100_000)

    with pytest.raises(PhotoImageValidationError, match="image_dimensions_too_large"):
        validate_image_dimensions(
            malicious,
            max_width=16_384,
            max_height=16_384,
            max_pixels=64_000_000,
        )


def test_image_dimension_guard_rejects_oversized_webp_canvas() -> None:
    malicious = _vp8x(16_384, 16_384)

    with pytest.raises(PhotoImageValidationError, match="image_dimensions_too_large"):
        validate_image_dimensions(
            malicious,
            max_width=16_384,
            max_height=16_384,
            max_pixels=64_000_000,
        )


def test_photo_decode_returns_413_before_storage_for_oversized_dimensions(tmp_path: Path) -> None:
    oversized = _png_with_dimensions(2, 1)
    request = PhotoDraftRequest(
        files=[
            PhotoUploadInput(
                filename="oversized.png",
                mime_type="image/png",
                data_base64=base64.b64encode(oversized).decode("ascii"),
            )
        ]
    )
    settings = Settings(data_dir=tmp_path, photo_max_width=1)

    with pytest.raises(HTTPException) as error:
        _decode_uploads(request, settings)

    assert error.value.status_code == 413
    assert error.value.detail == "image_dimensions_too_large"
