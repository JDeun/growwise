from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, uuid5

from growwise.domain.models import ResourceKind, ResourceRecord, Stage

from .base import AdapterResult
from .curriculum import CurriculumRecord


def curriculum_resource_ref(curriculum_id: str) -> str:
    """Stable source-ref namespace used by generated materials."""
    return f"curriculum:{curriculum_id}"


def curriculum_records_to_resources(result: AdapterResult) -> list[ResourceRecord]:
    """Convert public curriculum records into canonical GrowWise resources.

    Curriculum resources are global (`child_id=None`) so importing public metadata does
    not accidentally bind or leak a child's private profile.
    """
    resources: list[ResourceRecord] = []
    for raw in result.records:
        try:
            record = CurriculumRecord.model_validate(raw)
        except (TypeError, ValueError):
            continue
        stage = _stage(record.stage)
        tags = _tags(record)
        resources.append(ResourceRecord(
            id=uuid5(
                NAMESPACE_URL,
                f"growwise:curriculum:{result.source}:{record.curriculum_id}",
            ),
            child_id=None,
            kind=ResourceKind.CURRICULUM,
            title=record.title,
            summary=record.achievement_standard or record.competency or record.domain,
            content=_content(record),
            source_url=record.source_url,
            source_name=result.attribution,
            tags=tags,
            stage_tags=[stage] if stage is not None else [],
            provenance={
                "adapter": result.source,
                "curriculum_id": record.curriculum_id,
                "cache_status": result.cache_status,
                "attribution": result.attribution,
                "license_note": result.license_note,
            },
        ))
    return resources


def curriculum_refs(result: AdapterResult) -> list[str]:
    refs: list[str] = []
    for raw in result.records:
        curriculum_id = str(raw.get("curriculum_id", "")).strip()
        if curriculum_id:
            refs.append(curriculum_resource_ref(curriculum_id))
    return refs


def _stage(value: str) -> Stage | None:
    aliases: dict[str, Stage] = {
        "infant": Stage.INFANT_0_2,
        "infant_0_2": Stage.INFANT_0_2,
        "preschool": Stage.PRESCHOOL_3_5,
        "preschool_3_5": Stage.PRESCHOOL_3_5,
        "elementary": Stage.ELEMENTARY,
        "초등": Stage.ELEMENTARY,
        "middle": Stage.MIDDLE,
        "중학교": Stage.MIDDLE,
        "high": Stage.HIGH,
        "고등학교": Stage.HIGH,
    }
    return aliases.get(value.strip().lower())


def _tags(record: CurriculumRecord) -> list[str]:
    values = [record.subject, record.domain, record.competency]
    return list(dict.fromkeys(value for value in values if value))


def _content(record: CurriculumRecord) -> str:
    fields: list[tuple[str, Any]] = [
        ("교과", record.subject),
        ("영역", record.domain),
        ("역량", record.competency),
        ("성취기준", record.achievement_standard),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value)
