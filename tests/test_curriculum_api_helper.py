from datetime import date

import pytest

from growwise.api.curriculum import generate_curriculum_grounded_material
from growwise.config import Settings
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService


def test_curriculum_helper_fails_closed_without_endpoint(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, curriculum_endpoint=None)
    child = ChildProfile(
        name="child",
        stage=Stage.ELEMENTARY,
        birth_date=date(2018, 1, 1),
    )

    with pytest.raises(ValueError, match="curriculum_endpoint_not_configured"):
        generate_curriculum_grounded_material(
            settings=settings,
            store=None,  # type: ignore[arg-type]
            ingestor=None,  # type: ignore[arg-type]
            child=child,
            kind=MaterialKind.ACTIVITY_GUIDE,
            topic="plants",
            goal=None,
            subject="science",
            source_refs=[],
            materials=MaterialGenerationService(),
        )
