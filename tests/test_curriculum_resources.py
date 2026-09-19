from growwise.adapters import AdapterResult, curriculum_records_to_resources, curriculum_refs
from growwise.domain.models import ResourceKind, Stage


def test_curriculum_result_maps_to_global_provenance_resource() -> None:
    result = AdapterResult(
        source="public_curriculum",
        attribution="교육부",
        license_note="공공누리 조건 확인",
        records=[{
            "curriculum_id": "SCI-01",
            "title": "생물의 특징을 관찰한다",
            "stage": "elementary",
            "subject": "science",
            "domain": "life",
            "competency": "inquiry",
            "achievement_standard": "주변 생물의 특징을 관찰하고 설명한다.",
            "source_url": "https://example.invalid/SCI-01",
            "metadata": {"revision": "2022"},
        }],
    )

    resources = curriculum_records_to_resources(result)

    assert len(resources) == 1
    resource = resources[0]
    assert resource.child_id is None
    assert resource.kind is ResourceKind.CURRICULUM
    assert resource.stage_tags == [Stage.ELEMENTARY]
    assert resource.tags == ["science", "life", "inquiry"]
    assert resource.provenance["curriculum_id"] == "SCI-01"
    assert resource.provenance["adapter"] == "public_curriculum"
    assert "성취기준" in (resource.content or "")
    assert curriculum_refs(result) == ["curriculum:SCI-01"]



def test_curriculum_resource_identity_is_stable_across_retry() -> None:
    result = AdapterResult(
        source="public_curriculum",
        attribution="교육부",
        license_note="공공누리 조건 확인",
        records=[{
            "curriculum_id": "SCI-STABLE-01",
            "title": "안정 ID",
            "stage": "elementary",
            "subject": "science",
            "metadata": {},
        }],
    )

    first = curriculum_records_to_resources(result)[0]
    second = curriculum_records_to_resources(result)[0]

    assert first.id == second.id


def test_unknown_stage_does_not_invent_stage_tag() -> None:
    result = AdapterResult(
        source="public_curriculum",
        attribution="provider",
        license_note="license",
        records=[{
            "curriculum_id": "X",
            "title": "unknown",
            "stage": "other",
            "metadata": {},
        }],
    )

    [resource] = curriculum_records_to_resources(result)
    assert resource.stage_tags == []
