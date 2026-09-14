from growwise.domain import ResourceKind, ResourceRecord, Stage


def test_resource_record_keeps_provenance():
    resource = ResourceRecord(
        kind=ResourceKind.BOOK,
        title="Synthetic board book",
        source_name="fixture",
        tags=["동물"],
        stage_tags=[Stage.INFANT_0_2],
        provenance={"origin": "synthetic-test"},
    )

    assert resource.entity_type == "resource"
    assert resource.kind is ResourceKind.BOOK
    assert resource.provenance["origin"] == "synthetic-test"
