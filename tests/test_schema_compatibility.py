from pathlib import Path

import pytest

from growwise.domain import ChildProfile, Stage
from growwise.storage.markdown import MarkdownRepository
from growwise.storage.schema import UnsupportedSchemaVersion, validate_schema_version


def test_current_schema_is_accepted() -> None:
    assert validate_schema_version({"schema_version": 1}) == 1


def test_future_schema_is_rejected() -> None:
    with pytest.raises(UnsupportedSchemaVersion, match="newer"):
        validate_schema_version({"schema_version": 2})


def test_markdown_load_rejects_future_schema(tmp_path: Path) -> None:
    repository = MarkdownRepository(tmp_path / "records")
    child = ChildProfile(nickname="schema", stage=Stage.INFANT_0_2, age_months=9)
    path = repository.save(child)
    text = path.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: 2")
    path.write_text(text, encoding="utf-8")

    with pytest.raises(UnsupportedSchemaVersion, match="newer"):
        repository.load(path, ChildProfile)
