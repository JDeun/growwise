from growwise.services import InfantActivityService


def test_infant_activity_service_has_offline_fallback() -> None:
    result = InfantActivityService().suggest(
        age_months=9,
        recent_observations=["그림책의 동물 그림을 오래 바라봄"],
        interests=["동물"],
        limit=2,
    )

    assert len(result.suggestions) == 2
    assert all(item.title for item in result.suggestions)
    assert all(item.description for item in result.suggestions)
