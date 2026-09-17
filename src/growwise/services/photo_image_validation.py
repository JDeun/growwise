from __future__ import annotations

import struct


class PhotoImageValidationError(ValueError):
    pass


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if data[12:16] != b"IHDR":
        raise PhotoImageValidationError("malformed_image")
    width, height = struct.unpack(">II", data[16:24])
    if width == 0 or height == 0:
        raise PhotoImageValidationError("malformed_image")
    return width, height


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 4 or not data.startswith(b"\xff\xd8\xff"):
        return None
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
    }
    offset = 2
    while offset + 3 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        while marker == 0xFF and offset < len(data):
            marker = data[offset]
            offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if offset + 2 > len(data):
            break
        segment_length = int.from_bytes(data[offset : offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(data):
            raise PhotoImageValidationError("malformed_image")
        if marker in sof_markers:
            if segment_length < 7:
                raise PhotoImageValidationError("malformed_image")
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            if width == 0 or height == 0:
                raise PhotoImageValidationError("malformed_image")
            return width, height
        offset += segment_length
    raise PhotoImageValidationError("malformed_image")


def _webp_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    declared_size = int.from_bytes(data[4:8], "little") + 8
    if declared_size > len(data):
        raise PhotoImageValidationError("malformed_image")

    chunk = data[12:16]
    if chunk == b"VP8X":
        if len(data) < 30:
            raise PhotoImageValidationError("malformed_image")
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height

    if chunk == b"VP8L":
        if len(data) < 25 or data[20] != 0x2F:
            raise PhotoImageValidationError("malformed_image")
        b1, b2, b3, b4 = data[21:25]
        width = 1 + b1 + ((b2 & 0x3F) << 8)
        height = 1 + (b2 >> 6) + (b3 << 2) + ((b4 & 0x0F) << 10)
        return width, height

    if chunk == b"VP8 ":
        if len(data) < 30 or data[23:26] != b"\x9d\x01\x2a":
            raise PhotoImageValidationError("malformed_image")
        width = int.from_bytes(data[26:28], "little") & 0x3FFF
        height = int.from_bytes(data[28:30], "little") & 0x3FFF
        if width == 0 or height == 0:
            raise PhotoImageValidationError("malformed_image")
        return width, height

    raise PhotoImageValidationError("malformed_image")


def image_dimensions(data: bytes) -> tuple[int, int]:
    """Read dimensions from supported image containers without fully decoding pixel data."""
    for parser in (_png_dimensions, _jpeg_dimensions, _webp_dimensions):
        dimensions = parser(data)
        if dimensions is not None:
            return dimensions
    raise PhotoImageValidationError("unsupported_image_type")


def validate_image_dimensions(
    data: bytes,
    *,
    max_width: int,
    max_height: int,
    max_pixels: int,
) -> tuple[int, int]:
    width, height = image_dimensions(data)
    if width > max_width or height > max_height or width * height > max_pixels:
        raise PhotoImageValidationError("image_dimensions_too_large")
    return width, height
