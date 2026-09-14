from pathlib import Path

from growwise.domain import ChildProfile, Stage
from growwise.storage.markdown import MarkdownRepository


def test_markdown_repository_recovers_previous_generation(tmp_path: Path) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    child = ChildProfile(nickname="first", stage=Stage.INFANT_0_2, age_months=9)

    path = repository.save(child)
    child.nickname = "second"
    repository.save(child)

    path.write_text("not-valid-frontmatter: [", encoding="utf-8")

    recovered = repository.recover(path, ChildProfile)

    assert recovered.nickname == "first"
    assert repository.load(path, ChildProfile).nickname == "first"
    assert repository.backup_path(path).exists()
