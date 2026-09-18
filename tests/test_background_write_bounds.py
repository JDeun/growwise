from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.api.background_write_routes import (
    BackgroundMaterialRequest,
    BackgroundObservationRequest,
)
from growwise.domain import ExperienceAxis


def test_background_observation_axes_are_bounded() -> None:
    with pytest.raises(ValidationError):
        BackgroundObservationRequest(
            child_id="00000000-0000-0000-0000-000000000001",
            observation="관찰",
            experience_axes=[ExperienceAxis.READING] * 21,
        )


def test_background_material_source_refs_are_bounded() -> None:
    with pytest.raises(ValidationError):
        BackgroundMaterialRequest(
            topic="주제",
            source_refs=["resource:x"] * 101,
        )

    with pytest.raises(ValidationError):
        BackgroundMaterialRequest(
            topic="주제",
            source_refs=["x" * 501],
        )
