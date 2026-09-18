from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.api.background_write_routes import (
    BackgroundMaterialRequest,
    BackgroundObservationRequest,
)
from growwise.api.child_profile_routes import ChildProfileUpdateRequest
from growwise.api.contracts import (
    ActivityCreateRequest,
    ChildCreateRequest,
    MaterialGenerateRequest,
    ObservationRequest,
    ResourceCreateRequest,
)
from growwise.domain import ExperienceAxis, MaterialKind, ResourceKind, Stage


@pytest.mark.parametrize(
    "payload",
    [
        {"nickname": "x" * 121, "stage": Stage.ELEMENTARY},
        {"nickname": "아이", "stage": Stage.ELEMENTARY, "age_months": 241},
        {
            "nickname": "아이",
            "stage": Stage.ELEMENTARY,
            "interests": ["관심"] * 101,
        },
        {
            "nickname": "아이",
            "stage": Stage.ELEMENTARY,
            "interests": ["x" * 201],
        },
    ],
)
def test_child_create_rejects_values_looser_than_domain(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ChildCreateRequest(**payload)


def test_observation_and_activity_collection_bounds_match_domain() -> None:
    with pytest.raises(ValidationError):
        ObservationRequest(
            child_id="00000000-0000-0000-0000-000000000001",
            observation="관찰",
            experience_axes=[ExperienceAxis.READING] * 21,
        )

    with pytest.raises(ValidationError):
        ActivityCreateRequest(
            title="활동",
            source_refs=[f"resource-{index}" for index in range(101)],
        )

    with pytest.raises(ValidationError):
        ActivityCreateRequest(title="활동", source_refs=["x" * 501])


@pytest.mark.parametrize(
    "overrides",
    [
        {"content": "x" * 500_001},
        {"tags": ["x"] * 101},
        {"tags": ["x" * 201]},
        {"stage_tags": [Stage.ELEMENTARY] * 11},
        {"provenance": {"": "bad"}},
        {"provenance": {"origin": "x" * 4_001}},
    ],
)
def test_legacy_resource_contract_rejects_out_of_domain_payloads(
    overrides: dict,
) -> None:
    payload = {
        "kind": ResourceKind.NOTE,
        "title": "자료",
        **overrides,
    }
    with pytest.raises(ValidationError):
        ResourceCreateRequest(**payload)


def test_material_source_refs_are_bounded_at_http_contract() -> None:
    with pytest.raises(ValidationError):
        MaterialGenerateRequest(
            kind=MaterialKind.ACTIVITY_GUIDE,
            topic="주제",
            source_refs=[f"resource-{index}" for index in range(101)],
        )

    with pytest.raises(ValidationError):
        MaterialGenerateRequest(
            kind=MaterialKind.ACTIVITY_GUIDE,
            topic="주제",
            source_refs=["x" * 501],
        )


def test_background_contracts_bound_collection_cardinality() -> None:
    with pytest.raises(ValidationError):
        BackgroundObservationRequest(
            child_id="00000000-0000-0000-0000-000000000001",
            observation="관찰",
            experience_axes=[ExperienceAxis.READING] * 21,
        )

    with pytest.raises(ValidationError):
        BackgroundMaterialRequest(
            topic="주제",
            source_refs=[f"resource-{index}" for index in range(101)],
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"interests": ["x" * 201]},
        {"additional_languages": ["x" * 36]},
        {"learning_goals": ["x" * 201]},
    ],
)
def test_child_update_bounds_collection_items(overrides: dict) -> None:
    payload = {
        "nickname": "아이",
        "stage": Stage.ELEMENTARY,
        **overrides,
    }
    with pytest.raises(ValidationError):
        ChildProfileUpdateRequest(**payload)
