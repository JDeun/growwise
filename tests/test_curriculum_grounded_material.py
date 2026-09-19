from datetime import date

from growwise.adapters import PublicCurriculumAdapter, SQLiteExternalCache
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService
from growwise.services import CurriculumGroundedMaterialService


class StubHttp:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def get_json(self, endpoint: str, *, params: dict[str, str]) -> dict[str, object]:
        self.calls.append(params)
        return {
            "records": [
                {
                    "code": "SCI-01",
                    "title": "주변 생물 관찰",
                    "stage": "elementary",
                    "subject": "science",
                    "achievement_standard": "주변 생물의 특징을 관찰하고 설명한다.",
                }
            ]
        }


def test_grounded_material_persists_canonical_resource_without_child_identity(
    tmp_path,
) -> None:
    http = StubHttp()
    curriculum = PublicCurriculumAdapter(
        endpoint="https://example.invalid/curriculum",
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=http,
    )
    service = CurriculumGroundedMaterialService(
        curriculum=curriculum,
        materials=MaterialGenerationService(),
    )
    child = ChildProfile(
        name="private-child-name",
        stage=Stage.ELEMENTARY,
        birth_date=date(2018, 4, 1),
        interests=["곤충"],
    )
    persisted = []

    material, resources = service.generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="곤충 관찰",
        subject="science",
        source_refs=["resource:parent-note"],
        persist_resource=persisted.append,
    )

    assert len(resources) == 1
    assert persisted == resources
    curriculum_ref = f"resource:{resources[0].id}"
    assert material.source_refs == ["resource:parent-note", curriculum_ref]
    assert f"`{curriculum_ref}`" in material.content_markdown
    assert resources[0].provenance["curriculum_id"] == "SCI-01"
    assert http.calls == [
        {
            "stage": "elementary",
            "subject": "science",
            "query": "곤충 관찰",
        }
    ]
    serialized_calls = repr(http.calls)
    assert child.name not in serialized_calls
    assert str(child.id) not in serialized_calls
    assert "곤충" in serialized_calls


class TrustedRevisionHttp:
    def get_json(self, endpoint: str, *, params: dict[str, str]) -> dict[str, object]:
        del endpoint, params
        return {
            "records": [
                {
                    "code": "MID-NEW-01",
                    "title": "중학교 최신 개정 메타데이터",
                    "stage": "middle",
                    "subject": "science",
                    "framework": "검증된 최신 중학교 교육과정",
                    "revision": "2026-correction",
                    "official_notice": "국가교육위원회고시 제2026-9호",
                    "effective_from": "2026-09-01",
                    "grades": [8],
                    "source_url": "https://ncic.go.kr/curriculum/2026-9",
                }
            ]
        }


def test_grounded_material_auto_activates_trusted_effective_revision(tmp_path) -> None:
    curriculum = PublicCurriculumAdapter(
        endpoint="https://example.invalid/curriculum",
        cache=SQLiteExternalCache(tmp_path / "external.sqlite3"),
        http=TrustedRevisionHttp(),
    )
    service = CurriculumGroundedMaterialService(
        curriculum=curriculum,
        materials=MaterialGenerationService(),
    )
    child = ChildProfile(
        name="private-child-name",
        stage=Stage.MIDDLE,
        grade=8,
    )

    material, _resources = service.generate(
        child=child,
        kind=MaterialKind.SCIENCE_INQUIRY,
        topic="증거 비교",
        subject="science",
    )

    target = material.curriculum_targets[0]
    assert target.framework == "검증된 최신 중학교 교육과정"
    assert target.revision == "2026-correction"
    assert target.source_ref == "국가교육위원회고시 제2026-9호"
    assert target.resolution_precision == "external_verified_metadata"
    assert "검증된 최신 중학교 교육과정" in material.content_markdown
