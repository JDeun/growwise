from growwise.domain import ChildProfile, Stage
from growwise.storage import MarkdownRepository


def test_markdown_roundtrip(tmp_path) -> None:
    repo = MarkdownRepository(tmp_path)
    profile = ChildProfile(nickname="sample-child", stage=Stage.INFANT_0_2, age_months=9)
    path = repo.save(profile)
    loaded = repo.load(path, ChildProfile)
    assert loaded.id == profile.id
    assert loaded.stage == profile.stage
