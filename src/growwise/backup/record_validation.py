from __future__ import annotations

from pathlib import Path
from uuid import UUID

import frontmatter

from growwise.domain.links import EntityLink
from growwise.domain.models import (
    ActivityPlan,
    ChildProfile,
    EntityBase,
    GeneratedMaterial,
    LearningLog,
    ResourceRecord,
    WorkflowRun,
)
from growwise.domain.photo import PhotoActivityRecord, PhotoAsset
from growwise.domain.study import (
    MistakeRecord,
    SelfExplanationLog,
    StudyPlan,
    StudyReflection,
    StudyUnitProgress,
)
from growwise.storage.markdown import _decode_metadata
from growwise.storage.schema import validate_schema_version

_RECORD_MODELS: dict[str, type[EntityBase]] = {
    "activity_plan": ActivityPlan,
    "child_profile": ChildProfile,
    "entity_link": EntityLink,
    "generated_material": GeneratedMaterial,
    "learning_log": LearningLog,
    "mistake_record": MistakeRecord,
    "photo_activity_record": PhotoActivityRecord,
    "photo_asset": PhotoAsset,
    "resource": ResourceRecord,
    "self_explanation_log": SelfExplanationLog,
    "study_plan": StudyPlan,
    "study_reflection": StudyReflection,
    "study_unit_progress": StudyUnitProgress,
    "workflow_run": WorkflowRun,
}
_REQUIRED_RECORD_KEYS = {"id", "entity_type", "schema_version", "created_at", "updated_at"}


class InvalidRecordTree(ValueError):
    pass


def validate_record_tree(records_root: Path) -> int:
    """Validate the canonical Markdown tree before any restore swaps authoritative state.

    GrowWise stores exactly one record at ``<entity_type>/<id>.md``. This validator rejects path /
    metadata disagreement, unknown entity types, duplicate IDs, unsupported schema versions, and
    payloads that fail the concrete domain model. SQLite therefore never gets a chance to collapse
    ambiguous duplicate IDs through its ``ON CONFLICT(id)`` projection behavior.
    """
    if not records_root.exists():
        return 0

    seen_ids: set[str] = set()
    count = 0
    for path in sorted(records_root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix != ".md":
            raise InvalidRecordTree(f"unexpected record file: {path.name}")

        try:
            relative = path.relative_to(records_root)
        except ValueError as exc:  # pragma: no cover - rglob guarantees containment
            raise InvalidRecordTree(f"record escaped records root: {path}") from exc
        if len(relative.parts) != 2:
            raise InvalidRecordTree(
                f"record must use canonical <entity_type>/<id>.md path: {relative.as_posix()}"
            )

        try:
            post = frontmatter.load(path)
            payload = _decode_metadata(dict(post.metadata))
        except Exception as exc:
            raise InvalidRecordTree(f"invalid Markdown record: {relative.as_posix()}") from exc

        if not _REQUIRED_RECORD_KEYS.issubset(payload):
            raise InvalidRecordTree(f"record metadata incomplete: {relative.as_posix()}")
        try:
            validate_schema_version(payload)
        except Exception as exc:
            raise InvalidRecordTree(
                f"record schema is unsupported: {relative.as_posix()}"
            ) from exc

        entity_type = payload.get("entity_type")
        if not isinstance(entity_type, str) or entity_type not in _RECORD_MODELS:
            raise InvalidRecordTree(
                f"unknown record entity_type={entity_type!r}: {relative.as_posix()}"
            )
        if relative.parts[0] != entity_type:
            raise InvalidRecordTree(
                "record entity_type does not match its directory: "
                f"{relative.as_posix()} declares {entity_type!r}"
            )

        try:
            canonical_id = str(UUID(str(payload["id"])))
        except (TypeError, ValueError, AttributeError) as exc:
            raise InvalidRecordTree(f"record id is not a UUID: {relative.as_posix()}") from exc
        if path.stem != canonical_id:
            raise InvalidRecordTree(
                "record id does not match its filename: "
                f"{relative.as_posix()} declares {canonical_id!r}"
            )
        if canonical_id in seen_ids:
            raise InvalidRecordTree(f"duplicate record id: {canonical_id}")

        model = _RECORD_MODELS[entity_type]
        try:
            validated = model.model_validate(payload)
        except Exception as exc:
            raise InvalidRecordTree(
                f"record payload failed {model.__name__} validation: {relative.as_posix()}"
            ) from exc
        if str(validated.id) != canonical_id or validated.entity_type != entity_type:
            raise InvalidRecordTree(
                f"record identity changed during validation: {relative.as_posix()}"
            )

        seen_ids.add(canonical_id)
        count += 1

    return count
