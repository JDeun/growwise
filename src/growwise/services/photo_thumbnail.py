"""Small metadata-free previews; original photo assets remain authoritative."""

from __future__ import annotations

import io
import threading
from collections.abc import Callable

from PIL import Image, ImageOps

from .photo_image_validation import PhotoImageValidationError, validate_image_dimensions

THUMBNAIL_EDGE = 384
THUMBNAIL_MAX_BYTES = 128 * 1024
_DECODE_LOCK = threading.Lock()


def photo_thumbnail(
    read_original: Callable[[], bytes],
    *,
    max_width: int,
    max_height: int,
    max_pixels: int,
) -> tuple[bytes, int, int]:
    # Keep even a custom upload allowance from creating a >256MiB preview decoder surface.
    max_pixels = min(max_pixels, 64_000_000)
    with _DECODE_LOCK:
        data = read_original()
        validate_image_dimensions(
            data, max_width=max_width, max_height=max_height, max_pixels=max_pixels
        )
        with Image.open(io.BytesIO(data), formats=("JPEG", "PNG", "WEBP")) as image:
            if (
                image.width > max_width
                or image.height > max_height
                or image.width * image.height > max_pixels
            ):
                raise PhotoImageValidationError("image_dimensions_too_large")
            image.draft("RGB", (THUMBNAIL_EDGE, THUMBNAIL_EDGE))
            image.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE), Image.Resampling.LANCZOS)
            # Orient only after reducing: EXIF transposition must not copy a full-resolution image.
            with (
                ImageOps.exif_transpose(image) as oriented,
                oriented.convert("RGBA") as rgba,
                Image.new("RGB", rgba.size, "white") as preview,
            ):
                preview.paste(rgba, mask=rgba.getchannel("A"))
                for quality in (75, 50):
                    output = io.BytesIO()
                    preview.save(output, format="JPEG", quality=quality, optimize=True)
                    encoded = output.getvalue()
                    if len(encoded) <= THUMBNAIL_MAX_BYTES:
                        return encoded, preview.width, preview.height
    raise PhotoImageValidationError("thumbnail_too_large")
