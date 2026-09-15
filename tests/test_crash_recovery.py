"""Crash-recovery coverage for the storage layer.

Markdown is the source of truth; the SQLite index is a disposable projection that
must be rebuildable from Markdown after any crash. These tests exercise realistic
post-crash on-disk states and assert clean recovery without data loss.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore, SQLiteProjection


def _seed(tmp_path: Path) -> tuple[Path, Path, ChildProfile, LearningLog]:
    records = tmp_path / "records"
    db = tmp_path / "index.sqlite3"
    store = EntityStore(records, db)
    child = ChildProfile(nickname="복구-아이", stage=Stage.INFANT_0_2, age_months=9)
    store.save(child)
    log = LearningLog(child_id=child.id, parent_observation="책 표지를 오래 바라봄")
    store.save(log)
    return records, db, child, log


def _assert_fully_recovered(db: Path, child: ChildProfile, log: LearningLog) -> None:
    projection = SQLiteProjection(db)
    assert projection.rebuild(db.parent / "records") == 2
    profile = projection.get_entity(str(child.id), entity_type="child_profile")
    assert profile is not None and profile["nickname"] == "복구-아이"
    logs = projection.list_entities(entity_type="learning_log", child_id=str(child.id))
    assert len(logs) == 1
    assert logs[0]["parent_observation"] == log.parent_observation


def test_deleted_index_rebuilds_all_entities(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    db.unlink()
    _assert_fully_recovered(db, child, log)


def test_zero_byte_index_rebuilds(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    db.write_bytes(b"")
    _assert_fully_recovered(db, child, log)


def test_garbage_index_is_detected_and_rebuilt(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    db.write_bytes(b"this is not a sqlite database at all" * 32)
    # Constructing the projection must not crash on a non-SQLite file.
    _assert_fully_recovered(db, child, log)


def test_truncated_index_is_detected_and_rebuilt(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    raw = db.read_bytes()
    db.write_bytes(raw[:64])  # valid header, truncated body -> "disk image malformed"
    _assert_fully_recovered(db, child, log)


def test_truncated_markdown_record_is_quarantined(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    # Simulate a write interrupted mid-flush: frontmatter cut before the closing fence.
    bad = records / "learning_log" / f"{log.id}.md"
    bad.write_text("---\nid: broken\nparent_obser", encoding="utf-8")

    db.unlink()
    projection = SQLiteProjection(db)
    assert projection.rebuild(records) == 1  # the intact child_profile still loads
    assert bad in projection.last_rebuild_skipped
    profile = projection.get_entity(str(child.id), entity_type="child_profile")
    assert profile is not None and profile["nickname"] == "복구-아이"


def test_unparseable_yaml_record_is_quarantined(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    bad = records / "learning_log" / f"{log.id}.md"
    bad.write_text("---\nid: [unterminated\n---\nbody\n", encoding="utf-8")

    db.unlink()
    projection = SQLiteProjection(db)
    assert projection.rebuild(records) == 1
    assert bad in projection.last_rebuild_skipped


def test_future_schema_record_still_hard_fails(tmp_path: Path) -> None:
    """Corruption is quarantined, but an unsupported schema is a hard error."""
    from growwise.storage.schema import UnsupportedSchemaVersion

    records, db, _, log = _seed(tmp_path)
    doc = records / "learning_log" / f"{log.id}.md"
    text = doc.read_text(encoding="utf-8").replace("schema_version: 1", "schema_version: 99")
    doc.write_text(text, encoding="utf-8")

    db.unlink()
    projection = SQLiteProjection(db)
    with pytest.raises(UnsupportedSchemaVersion, match="newer"):
        projection.rebuild(records)


def test_stale_index_is_overwritten_by_markdown(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    store = EntityStore(records, db)
    # Markdown moves ahead (source of truth); pretend the index reflects an older state.
    child.nickname = "새-별명"
    store.markdown.save(child)  # write Markdown only, leaving the index stale

    projection = SQLiteProjection(db)
    stale = projection.get_entity(str(child.id), entity_type="child_profile")
    assert stale is not None and stale["nickname"] == "복구-아이"

    assert projection.rebuild(records) == 2
    fresh = projection.get_entity(str(child.id), entity_type="child_profile")
    assert fresh is not None and fresh["nickname"] == "새-별명"


def test_interrupted_write_temp_files_are_ignored(tmp_path: Path) -> None:
    records, db, child, log = _seed(tmp_path)
    child_dir = records / "child_profile"
    # An interrupted atomic write can leave hidden temp files and a rolling .bak.
    (child_dir / f".{child.id}.md.partial123").write_text("garbage", encoding="utf-8")
    (child_dir / f"{child.id}.md.bak").write_text("stale-backup", encoding="utf-8")

    db.unlink()
    projection = SQLiteProjection(db)
    # Only the two real .md records are indexed; temp/.bak files are skipped silently.
    assert projection.rebuild(records) == 2
    assert projection.last_rebuild_skipped == []
    _assert_fully_recovered(db, child, log)
