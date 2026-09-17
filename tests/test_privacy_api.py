from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from growwise.api.privacy_routes import purge_child
from growwise.config import Settings
from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore


def test_privacy_route_purges_child_and_preserves_sibling(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path))
    settings = Settings()
    store = EntityStore(settings.records_dir, settings.index_path)
    target = ChildProfile(nickname="삭제아이", stage=Stage.INFANT_0_2, age_months=9)
    sibling = ChildProfile(nickname="보존아이", stage=Stage.PRESCHOOL_3_5, age_months=48)
    store.save(target)
    store.save(sibling)
    store.save(LearningLog(child_id=target.id, parent_observation="삭제할 관찰"))

    result = purge_child(target.id)

    assert result["child_id"] == str(target.id)
    assert result["markdown_files_deleted"] >= 2
    rebuilt = EntityStore(settings.records_dir, settings.index_path)
    assert rebuilt.index.get_entity(str(target.id), entity_type="child_profile") is None
    assert rebuilt.index.get_entity(str(sibling.id), entity_type="child_profile") is not None


def test_privacy_route_returns_not_found_for_unknown_child(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GROWWISE_DATA_DIR", str(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        purge_child(ChildProfile(nickname="임시", stage=Stage.INFANT_0_2).id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "child_not_found"
