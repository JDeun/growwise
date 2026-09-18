import json
import sqlite3

from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore, SQLiteProjection


def test_projection_can_rebuild_from_markdown(tmp_path) -> None:
    records = tmp_path / "records"
    db = tmp_path / "index.sqlite3"
    store = EntityStore(records, db)
    child = ChildProfile(nickname="sample-child", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    store.save(LearningLog(child_id=child.id, parent_observation="책 표지를 오래 바라봄"))

    db.unlink()
    projection = SQLiteProjection(db)
    assert projection.rebuild(records) == 2
    logs = projection.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(logs) == 1
    assert logs[0]["parent_observation"] == "책 표지를 오래 바라봄"



def test_projection_repairs_corrupt_payload_from_markdown_source(tmp_path) -> None:
    records = tmp_path / "records"
    db = tmp_path / "index.sqlite3"
    store = EntityStore(records, db)
    child = ChildProfile(nickname="복구아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)

    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE entities SET payload_json = ? WHERE id = ?",
            ("{not-json", str(child.id)),
        )

    repaired = store.index.get_entity(str(child.id), entity_type="child_profile")
    assert repaired is not None
    assert repaired["nickname"] == "복구아이"

    with sqlite3.connect(db) as connection:
        row = connection.execute(
            "SELECT payload_json FROM entities WHERE id = ?",
            (str(child.id),),
        ).fetchone()
    assert row is not None
    persisted = json.loads(row[0])
    assert persisted["id"] == str(child.id)


def test_projection_drops_corrupt_row_when_authoritative_source_is_gone(tmp_path) -> None:
    records = tmp_path / "records"
    db = tmp_path / "index.sqlite3"
    store = EntityStore(records, db)
    child = ChildProfile(nickname="유령행", stage=Stage.INFANT_0_2, age_months=9)
    source = store.save(child)
    source.unlink()

    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE entities SET payload_json = ? WHERE id = ?",
            ("{not-json", str(child.id)),
        )

    assert store.index.get_entity(str(child.id), entity_type="child_profile") is None
    with sqlite3.connect(db) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM entities WHERE id = ?",
            (str(child.id),),
        ).fetchone()
    assert remaining is not None
    assert remaining[0] == 0
