from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.api.child_profile_routes import ChildProfileUpdateRequest
from growwise.api.curriculum_routes import CurriculumMaterialRequest
from growwise.api.learning_record_routes import LearningRecordRequest
from growwise.api.material_result_routes import MaterialResultRequest
from growwise.api.study_routes import SelfExplanationRequest
from growwise.domain import LearningRecordKind, Stage


def test_child_profile_route_bounds_each_list_item() -> None:
    with pytest.raises(ValidationError):
        ChildProfileUpdateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            interests=["x" * 201],
        )
    with pytest.raises(ValidationError):
        ChildProfileUpdateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            additional_languages=["x" * 36],
        )
    with pytest.raises(ValidationError):
        ChildProfileUpdateRequest(
            nickname="아이",
            stage=Stage.ELEMENTARY,
            learning_goals=["x" * 201],
        )


def test_curriculum_source_refs_match_generated_material_bounds() -> None:
    with pytest.raises(ValidationError):
        CurriculumMaterialRequest(topic="주제", source_refs=["x" * 501])
    with pytest.raises(ValidationError):
        CurriculumMaterialRequest(topic="주제", source_refs=["resource:x"] * 101)


def test_learning_and_material_result_tags_match_learning_log_bounds() -> None:
    with pytest.raises(ValidationError):
        LearningRecordRequest(
            kind=LearningRecordKind.DIARY,
            title="기록",
            summary="요약",
            tags=["x" * 201],
        )
    with pytest.raises(ValidationError):
        MaterialResultRequest(
            observation="관찰",
            tags=["x" * 201],
        )


def test_study_evidence_refs_are_bounded_per_item() -> None:
    with pytest.raises(ValidationError):
        SelfExplanationRequest(
            subject="수학",
            unit="방정식",
            explanation="설명",
            evidence_refs=["x" * 501],
        )
