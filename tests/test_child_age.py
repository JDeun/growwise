from datetime import date

import pytest
from pydantic import ValidationError

from growwise.domain.models import ChildProfile, Stage, age_in_months


def test_age_in_months_respects_partial_month_boundary() -> None:
    birth = date(2025, 12, 19)
    assert age_in_months(birth, on_date=date(2026, 9, 18)) == 8
    assert age_in_months(birth, on_date=date(2026, 9, 19)) == 9


def test_child_birth_date_overrides_stale_legacy_age() -> None:
    child = ChildProfile(
        nickname="child",
        stage=Stage.INFANT_0_2,
        birth_date=date(2025, 12, 19),
        age_months=1,
    )
    assert child.age_months_on(date(2026, 9, 19)) == 9
    assert child.age_months != 1


def test_legacy_profile_without_birth_date_keeps_age_months() -> None:
    child = ChildProfile(nickname="legacy", stage=Stage.INFANT_0_2, age_months=9)
    assert child.birth_date is None
    assert child.age_months_on(date(2030, 1, 1)) == 9


def test_future_birth_date_is_rejected() -> None:
    with pytest.raises(ValidationError, match="birth_date cannot be in the future"):
        ChildProfile(
            nickname="future",
            stage=Stage.INFANT_0_2,
            birth_date=date(2999, 1, 1),
        )
