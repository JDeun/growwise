from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from uuid6 import uuid7

from growwise.domain import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLink, EntityLinkRelation
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore, SQLiteProjection


def test_entity_link_index_backfills_legacy_projection_rows(tmp_path: Path) -> None:
    db = tmp_path / "index.sqlite3"
    link = EntityLink(
        source_id=uuid7(),
        target_id=uuid7(),
        relation=EntityLinkRelation.RELATED,
    )
    payload = link.model_dump(mode="json")

    with sqlite3.connect(db) as connection:
        connection.execute(
            """
            CREATE TABLE entities (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                child_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source_path TEXT NOT NULL UNIQUE,
                payload_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO entities (
                id, entity_type, child_id, created_at, updated_at, source_path, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(link.id),
                link.entity_type,
                None,
                link.created_at.isoformat(),
                link.updated_at.isoformat(),
                str(tmp_path / "legacy-link.md"),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )

    projection = SQLiteProjection(db)

    matches = projection.list_entity_links(
        source_id=str(link.source_id),
        target_id=str(link.target_id),
        relation=link.relation.value,
    )
    assert [item["id"] for item in matches] == [str(link.id)]


def test_entity_links_touching_survives_low_sqlite_variable_limit(tmp_path: Path) -> None:
    class LowVariableProjection(SQLiteProjection):
        def _connect(self) -> sqlite3.Connection:
            connection = super()._connect()
            connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 512)
            return connection

    projection = LowVariableProjection(tmp_path / "index.sqlite3")
    source_ids: list[str] = []
    with projection._connection() as connection:
        for index in range(600):
            link = EntityLink(
                source_id=uuid7(),
                target_id=uuid7(),
                relation=EntityLinkRelation.RELATED,
                label=f"link-{index}",
            )
            source_ids.append(str(link.source_id))
            projection._upsert_on(
                connection,
                link.model_dump(mode="json"),
                tmp_path / f"link-{index}.md",
            )

    matches = projection.entity_links_touching(set(source_ids))

    assert len(matches) == 600
    assert {str(item["source_id"]) for item in matches} == set(source_ids)


def test_entity_link_service_uses_indexed_queries_not_full_link_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    owner = ChildProfile(nickname="원소유", stage=Stage.ELEMENTARY)
    sibling = ChildProfile(nickname="공유아이", stage=Stage.ELEMENTARY)
    store.save(owner)
    store.save(sibling)
    resource = ResourceRecord(
        child_id=owner.id,
        kind=ResourceKind.NOTE,
        title="공유 자료",
    )
    store.save(resource)

    service = EntityLinkService(store)
    created = service.share_with_children(
        source_id=resource.id,
        child_ids=[sibling.id],
    )[0]

    def forbid_full_scan(*args: object, **kwargs: object) -> list[dict]:
        if kwargs.get("entity_type") == "entity_link":
            raise AssertionError("entity-link full scan is forbidden")
        return []

    monkeypatch.setattr(store.index, "list_entities", forbid_full_scan)

    duplicate = service.create(
        source_id=resource.id,
        target_id=sibling.id,
        relation=EntityLinkRelation.CHILD_SCOPE,
    )
    assert duplicate.id == created.id
    assert service.child_scope_targets(resource.id) == [sibling.id]

    backlinks = service.backlinks(resource.id)
    assert len(backlinks["outgoing"]) == 1
    assert backlinks["outgoing"][0]["link"]["id"] == str(created.id)

    assert service.delete_for_entities({str(resource.id)}) == 1
    assert store.index.get_entity(str(created.id), entity_type="entity_link") is None
