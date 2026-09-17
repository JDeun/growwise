from growwise.services.photo_activity import _COMMIT_LOCKS, _commit_lock


def test_photo_commit_lock_registry_is_bounded() -> None:
    locks = {_commit_lock(f"record-{index}") for index in range(10_000)}

    assert len(_COMMIT_LOCKS) == 256
    assert locks.issubset(set(_COMMIT_LOCKS))
    assert _commit_lock("same-record") is _commit_lock("same-record")
