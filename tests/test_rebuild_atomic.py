"""rebuild() must be atomic: a hard error mid-rebuild leaves the prior index intact."""

from __future__ import annotations

from pathlib import Path

import pytest

from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore, SQLiteProjection
from growwise.storage.schema import UnsupportedSchemaVersion


def test_rebuild_is_atomic_on_unsupported_schema(tmp_path: Path) -> None:
    records, index = tmp_path / "records", tmp_path / "index.sqlite3"
    store = EntityStore(records, index)
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    store.save(LearningLog(child_id=child.id, parent_observation="책 표지를 오래 바라봄"))

    projection = SQLiteProjection(index)
    before = len(projection.list_entities())
    assert before == 2

    # One record is written by an incompatible future build -> a hard error, not corruption.
    for path in sorted(records.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "schema_version: 1" in text:
            bumped = text.replace("schema_version: 1", "schema_version: 99")
            path.write_text(bumped, encoding="utf-8")
            break

    with pytest.raises(UnsupportedSchemaVersion):
        projection.rebuild(records)

    # The transaction rolled back: the prior index is preserved, not emptied.
    assert len(SQLiteProjection(index).list_entities()) == before
