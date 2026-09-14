from growwise.domain import ChildProfile, Stage


def test_domain_ids_are_uuid7() -> None:
    child = ChildProfile(nickname="sample-child", stage=Stage.INFANT_0_2, age_months=9)
    assert child.id.version == 7
