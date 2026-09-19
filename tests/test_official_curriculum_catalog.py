from __future__ import annotations

from growwise.adapters import (
    OfficialKoreanCurriculumCatalogAdapter,
    curriculum_records_to_resources,
)
from growwise.domain import ResourceKind, Stage


def test_infant_catalog_is_offline_and_metadata_only() -> None:
    result = OfficialKoreanCurriculumCatalogAdapter().search(
        stage=Stage.INFANT_0_2.value,
        offline=True,
    )

    assert result.cache_status == "fresh"
    assert len(result.records) == 4
    assert all(
        record["source_url"].startswith("https://i-nuri.go.kr/") for record in result.records
    )
    assert all(record["metadata"]["content_policy"] == "link_only" for record in result.records)
    assert all(record.get("achievement_standard") is None for record in result.records)
    assert "재배포하지 않음" in result.license_note


def test_catalog_filters_by_stage_and_public_query_only() -> None:
    result = OfficialKoreanCurriculumCatalogAdapter().search(
        stage=Stage.ELEMENTARY.value,
        query="2022",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["curriculum_id"] == "kr-national-2022-elementary"
    assert record["metadata"]["official_notice"] == "국가교육위원회고시 제2024-3호"
    assert record["source_url"].startswith("https://ncic.go.kr/")


def test_catalog_keeps_stage_framework_when_topic_is_not_a_catalog_keyword() -> None:
    result = OfficialKoreanCurriculumCatalogAdapter().search(
        stage=Stage.ELEMENTARY.value,
        subject="science",
        query="곤충 관찰",
    )

    assert len(result.records) == 1
    assert result.records[0]["curriculum_id"] == "kr-national-2022-elementary"


def test_catalog_records_convert_to_global_resource_links() -> None:
    result = OfficialKoreanCurriculumCatalogAdapter().search(stage=Stage.PRESCHOOL_3_5.value)
    resources = curriculum_records_to_resources(result)

    assert len(resources) == 1
    resource = resources[0]
    assert resource.child_id is None
    assert resource.kind is ResourceKind.CURRICULUM
    assert resource.stage_tags == [Stage.PRESCHOOL_3_5]
    assert resource.source_url and resource.source_url.startswith("https://i-nuri.go.kr/")
    assert resource.provenance["adapter"] == "kr_official_curriculum_catalog"
    assert "링크" in resource.provenance["license_note"]


def test_catalog_does_not_accept_private_child_dimensions() -> None:
    adapter = OfficialKoreanCurriculumCatalogAdapter()

    # The public adapter boundary intentionally has no child/profile/observation argument.
    try:
        adapter.search(stage="elementary", child_id="private-child")  # type: ignore[call-arg]
    except TypeError as exc:
        assert "child_id" in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError("private child data unexpectedly crossed the adapter boundary")
