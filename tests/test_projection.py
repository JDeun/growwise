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
