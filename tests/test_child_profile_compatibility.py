from growwise.domain import ChildProfile, Stage


def test_legacy_name_only_profile_restores_nickname() -> None:
    child = ChildProfile.model_validate(
        {
            "entity_type": "child_profile",
            "name": "수아",
            "stage": Stage.INFANT_0_2,
            "age_months": 9,
        }
    )

    assert child.name == "수아"
    assert child.nickname == "수아"


def test_legacy_nickname_only_profile_restores_name() -> None:
    child = ChildProfile.model_validate(
        {
            "entity_type": "child_profile",
            "nickname": "수아",
            "stage": Stage.INFANT_0_2,
            "age_months": 9,
        }
    )

    assert child.name == "수아"
    assert child.nickname == "수아"
