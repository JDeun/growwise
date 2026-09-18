from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.api.contracts import (
    ActivityCreateRequest,
    ChildCreateRequest,
    MaterialGenerateRequest,
    ObservationRequest,
    ResourceCreateRequest,
)
from growwise.domain import ExperienceAxis, MaterialKind, ResourceKind, Stage


def test_child_request_matches_profile_storage_bounds() -> None:
    with pytest.raises(ValidationError):
        ChildCreateRequest(nickname="x" * 121, stage=Stage.ELEMENTARY)
    with pytest.raises(ValidationError):
        ChildCreateRequest(nickname="아이", stage=Stage.ELEMENTARY, age_months=241)
    with pytest.raises(ValidationError):
        ChildCreateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            interests=["관심"] * 101,
        )
    with pytest.raises(ValidationError):
        ChildCreateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            interests=["x" * 201],
        )


def test_observation_and_source_ref_lists_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ObservationRequest(
            child_id="00000000-0000-0000-0000-000000000001",
            observation="관찰",
            experience_axes=[ExperienceAxis.READING] * 21,
        )
    with pytest.raises(ValidationError):
        ActivityCreateRequest(
            title="활동",
            source_refs=["resource:x"] * 101,
        )
    with pytest.raises(ValidationError):
        MaterialGenerateRequest(
            kind=MaterialKind.ACTIVITY_GUIDE,
            topic="주제",
            source_refs=["x" * 501],
        )


def test_resource_request_matches_resource_record_bounds() -> None:
    base = {"kind": ResourceKind.NOTE, "title": "자료"}

    with pytest.raises(ValidationError):
        ResourceCreateRequest(**base, source_url="x" * 2_049)
    with pytest.raises(ValidationError):
        ResourceCreateRequest(**base, tags=["태그"] * 101)
    with pytest.raises(ValidationError):
        ResourceCreateRequest(**base, stage_tags=[Stage.ELEMENTARY] * 11)
    with pytest.raises(ValidationError):
        ResourceCreateRequest(**base, provenance={"x" * 201: "value"})
    with pytest.raises(ValidationError):
        ResourceCreateRequest(**base, provenance={"key": "x" * 4_001})
