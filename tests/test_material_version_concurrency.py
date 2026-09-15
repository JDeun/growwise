from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep
from typing import Any

from fastapi import HTTPException

import growwise.api.main as api
from growwise.api.main import MaterialEditRequest
from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialEditService
from growwise.storage import EntityStore


class InterruptReviewGraph:
    def invoke(self, value: Any, config: dict[str, Any]) -> dict[str, Any]:
        return {"__interrupt__": ("review",)}


def test_concurrent_parent_edits_create_only_one_successor(tmp_path, monkeypatch) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(nickname="학생", stage=Stage.ELEMENTARY, age_months=120)
    store.save(child)
    parent = GeneratedMaterial(
        child_id=child.id,
        kind=MaterialKind.READING_ACTIVITY,
        title="원본",
        content_markdown="# 원본",
        status=MaterialStatus.APPROVED,
    )
    store.save(parent)
    monkeypatch.setattr(api, "get_material_review_graph", lambda: InterruptReviewGraph())

    original_create_version = MaterialEditService.create_version

    def slow_create_version(self: MaterialEditService, **kwargs: Any) -> GeneratedMaterial:
        # Widen the historical check-then-save race window. With the endpoint guard, the
        # competing request cannot reach this method until the first successor is persisted.
        sleep(0.2)
        return original_create_version(self, **kwargs)

    monkeypatch.setattr(MaterialEditService, "create_version", slow_create_version)
    start = Barrier(2)

    def attempt(label: str) -> GeneratedMaterial | HTTPException:
        start.wait(timeout=5)
        try:
            return api.edit_material(
                parent.id,
                MaterialEditRequest(
                    title=f"편집본 {label}",
                    content_markdown=f"# 편집본 {label}",
                ),
                store,
            )
        except HTTPException as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["A", "B"]))

    successes = [item for item in results if isinstance(item, GeneratedMaterial)]
    conflicts = [item for item in results if isinstance(item, HTTPException)]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert conflicts[0].detail == "material_has_newer_version"

    materials = store.index.list_entities(
        entity_type="generated_material",
        child_id=str(child.id),
    )
    successors = [
        item for item in materials if item.get("parent_material_id") == str(parent.id)
    ]
    assert len(successors) == 1
    assert successors[0]["id"] == str(successes[0].id)
