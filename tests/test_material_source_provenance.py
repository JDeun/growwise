from __future__ import annotations

from typing import cast

from growwise.api.material_routes import material_source_evidence
from growwise.domain import MaterialSourceCitation
from growwise.storage import EntityStore


class _MissingIndex:
    def get_entity(self, entity_id: str, *, entity_type: str):
        del entity_id, entity_type
        return None


class _MissingStore:
    index = _MissingIndex()


def test_material_evidence_falls_back_to_immutable_citation_snapshot() -> None:
    citation = MaterialSourceCitation(
        source_ref="resource:11111111-1111-1111-1111-111111111111",
        title="삭제 전 저장한 공개 자료",
        excerpt="생성 당시 사용한 bounded evidence",
        source_name="public_source",
        source_url="https://example.org/source",
        attribution="Example Education",
        license_note="CC BY 4.0",
    )

    evidence = material_source_evidence(
        source_refs=[citation.source_ref],
        store=cast(EntityStore, _MissingStore()),
        fallback_citations=[citation],
    )

    assert len(evidence) == 1
    assert evidence[0].source_ref == citation.source_ref
    assert evidence[0].title == citation.title
    assert evidence[0].excerpt == citation.excerpt
    assert evidence[0].source_name == "public_source"
    assert evidence[0].source_url == "https://example.org/source"
    assert evidence[0].attribution == "Example Education"
    assert evidence[0].license_note == "CC BY 4.0"
