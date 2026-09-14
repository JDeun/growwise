from growwise.domain import ChildProfile, Stage


def test_child_profile_defaults() -> None:
    profile = ChildProfile(nickname="sample-child", stage=Stage.INFANT_0_2, age_months=9)
    assert profile.schema_version == 1
    assert profile.entity_type == "child_profile"
    assert profile.age_months == 9
