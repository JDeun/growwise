from datetime import date
from growwise.api.curriculum import generate_curriculum_grounded_material
from growwise.config import Settings
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService


class StubStore:
    def __init__(self) -> None:
        self.saved = []

    def save(self, item) -> None:
        self.saved.append(item)


class StubIngestor:
    def __init__(self) -> None:
        self.ingested = []

    def ingest(self, item) -> None:
        self.ingested.append(item)


def test_curriculum_helper_uses_official_catalog_without_configured_endpoint(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path, curriculum_endpoint=None)
    child = ChildProfile(
        name="child",
        stage=Stage.ELEMENTARY,
        birth_date=date(2018, 1, 1),
    )
    store = StubStore()
    ingestor = StubIngestor()

    material = generate_curriculum_grounded_material(
        settings=settings,
        store=store,  # type: ignore[arg-type]
        ingestor=ingestor,  # type: ignore[arg-type]
        child=child,
        kind=MaterialKind.ACTIVITY_GUIDE,
        topic="plants",
        goal=None,
        subject="science",
        source_refs=[],
        materials=MaterialGenerationService(),
    )

    assert material.curriculum_targets
    assert store.saved
    assert ingestor.ingested == store.saved
    assert all(resource.child_id is None for resource in store.saved)
