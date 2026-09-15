from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from growwise.domain import ChildProfile, Stage
from growwise.storage.markdown import MarkdownRepository


def test_concurrent_saves_preserve_immediately_previous_generation(tmp_path: Path) -> None:
    repository_a = MarkdownRepository(tmp_path / "records")
    repository_b = MarkdownRepository(tmp_path / "records")
    child = ChildProfile(nickname="initial", stage=Stage.INFANT_0_2, age_months=9)
    path = repository_a.save(child)

    first = child.model_copy(update={"nickname": "first"})
    second = child.model_copy(update={"nickname": "second"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(repository_a.save, first),
            pool.submit(repository_b.save, second),
        ]
        for future in futures:
            future.result()

    current = repository_a.load(path, ChildProfile)
    backup = repository_a.load(repository_a.backup_path(path), ChildProfile)

    # The two concurrent generations must be adjacent in history. The scheduler may choose either
    # writer first, but the backup must never regress to the pre-concurrency "initial" generation.
    assert {current.nickname, backup.nickname} == {"first", "second"}


def test_recover_is_serialized_with_save(tmp_path: Path) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    child = ChildProfile(nickname="initial", stage=Stage.INFANT_0_2, age_months=9)
    path = repository.save(child)
    repository.save(child.model_copy(update={"nickname": "second"}))

    with ThreadPoolExecutor(max_workers=2) as pool:
        save_future = pool.submit(
            repository.save, child.model_copy(update={"nickname": "third"})
        )
        recover_future = pool.submit(repository.recover, path, ChildProfile)
        save_future.result()
        recover_future.result()

    # Regardless of scheduling, the source document remains parseable and corresponds to a valid
    # committed generation; save/recover cannot interleave copy/replace operations.
    current = repository.load(path, ChildProfile)
    assert current.nickname in {"initial", "second", "third"}
