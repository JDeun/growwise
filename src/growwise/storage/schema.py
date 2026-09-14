from __future__ import annotations

CURRENT_SCHEMA_VERSION = 1
MIN_SUPPORTED_SCHEMA_VERSION = 1


class UnsupportedSchemaVersion(ValueError):
    pass


def validate_schema_version(payload: dict) -> int:
    """Reject unknown future/legacy document schemas instead of silently misreading them."""
    raw = payload.get("schema_version", CURRENT_SCHEMA_VERSION)
    try:
        version = int(raw)
    except (TypeError, ValueError) as exc:
        raise UnsupportedSchemaVersion(f"invalid schema_version: {raw!r}") from exc

    if version < MIN_SUPPORTED_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"schema_version {version} is older than supported minimum "
            f"{MIN_SUPPORTED_SCHEMA_VERSION}"
        )
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(
            f"schema_version {version} is newer than this GrowWise build "
            f"({CURRENT_SCHEMA_VERSION})"
        )
    return version
