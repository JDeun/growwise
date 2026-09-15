import pytest
from pydantic import ValidationError

from growwise.api.curriculum_routes import CurriculumMaterialRequest
from growwise.domain import MaterialKind


def test_curriculum_material_request_defaults() -> None:
    request = CurriculumMaterialRequest(topic="plants")

    assert request.kind is MaterialKind.ACTIVITY_GUIDE
    assert request.subject is None
    assert request.source_refs == []


def test_curriculum_material_request_rejects_empty_topic() -> None:
    with pytest.raises(ValidationError):
        CurriculumMaterialRequest(topic="")
