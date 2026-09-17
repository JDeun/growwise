"""Write-through consistency: the SQLite index upsert must run under the Markdown per-path
lock, so a concurrent save cannot leave the index reflecting an older generation than the
authoritative Markdown source of truth (adversarial-review Finding 1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from growwise.domain.models import ChildProfile, ResourceKind, ResourceRecord, Stage
from growwise.storage import EntityStore
from growwise.storage.markdown import MarkdownRepository


def test_index_upsert_runs_under_the_path_lock(tmp_path: Path, monkeypatch) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    path = store.markdown.path_for(child)
    lock = MarkdownRepository.lock_for(path)

    observed: dict[str, bool] = {}
    original = store.index.upsert

    def spy(entity, entity_path):  # type: ignore[no-untyped-def]
        observed["locked"] = lock.locked()
        return original(entity, entity_path)

    monkeypatch.setattr(store.index, "upsert", spy)
    store.save(child)

    assert observed.get("locked") is True  # index write was serialized with the Markdown write


def test_index_and_markdown_agree_after_save(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="샘플아이", stage=Stage.INFANT_0_2, age_months=9)
    path = store.save(child)

    from_markdown = store.markdown.load(path, ChildProfile)
    from_index = store.index.get_entity(str(child.id))
    assert from_index is not None
    assert from_index["id"] == str(child.id) == str(from_markdown.id)


def test_store_revalidates_mutated_entity_before_authoritative_write(tmp_path):
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    resource = ResourceRecord(kind=ResourceKind.NOTE, title="valid")
    resource.title = ""

    with pytest.raises(ValidationError):
        store.save(resource)

    assert not store.markdown.path_for(resource).exists()
    assert store.index.get_entity(str(resource.id), entity_type="resource") is None
