"""Integrated material pipeline: one thread runs generation -> parent-review -> decision.

The draft is produced by the ``generate`` node and then flows straight into the reused
parent-review interrupt on the *same* ``thread_id`` and checkpointer, resuming (even after a
full process restart) from the persisted checkpoint. A ``review_applier`` hook records the
approved/revision/rejected outcome against a real ``MaterialReviewService`` transition.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from growwise.domain import (
    ChildProfile,
    GeneratedMaterial,
    MaterialKind,
    MaterialStatus,
    Stage,
)
from growwise.generators.material import MaterialGenerationService
from growwise.review.material import MaterialReviewService
from growwise.workflows import build_material_pipeline_graph


def _child() -> ChildProfile:
    return ChildProfile(nickname="테스터", stage=Stage.ELEMENTARY, age_months=84, interests=["물"])


def _pieces() -> tuple[Callable[[], GeneratedMaterial], dict[str, GeneratedMaterial]]:
    """A deterministic (provider=None) generator plus a captured-material handle."""
    service = MaterialGenerationService()
    child = _child()
    captured: dict[str, GeneratedMaterial] = {}

    def generator() -> GeneratedMaterial:
        material = service.generate(
            child=child, kind=MaterialKind.SCIENCE_INQUIRY, topic="물의 상태 변화"
        )
        captured["material"] = material
        return material

    return generator, captured


def _applier(
    captured: dict[str, GeneratedMaterial],
) -> Callable[[Mapping[str, Any]], dict[str, str]]:
    reviewer = MaterialReviewService()

    def apply(state: Mapping[str, Any]) -> dict[str, str]:
        material = captured["material"]
        target = MaterialStatus(state["decision_status"])
        reviewer.transition(material, target, note=state.get("decision_note"))
        return {"material_status": material.status.value}

    return apply


def _sqlite(path: str) -> tuple[sqlite3.Connection, SqliteSaver]:
    connection = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return connection, saver


def test_pipeline_generates_then_interrupts_then_applies_approval() -> None:
    generator, captured = _pieces()
    connection, saver = _sqlite(":memory:")
    graph = build_material_pipeline_graph(
        generator=generator, review_applier=_applier(captured), checkpointer=saver
    )
    config = {"configurable": {"thread_id": "pipeline-approve-1"}}

    first = graph.invoke({}, config=config)

    # Generation ran, then the reused parent-review interrupt fired on the same thread.
    interrupts = first["__interrupt__"]
    payload = interrupts[0].value
    assert payload["kind"] == "material_parent_review"
    assert payload["title"] == captured["material"].title
    assert payload["allowed"] == ["approved", "rejected", "revision_requested"]
    assert first["generator_mode"] == "template"
    assert first["material_status"] == "review_pending"

    resumed = graph.invoke(
        Command(resume={"status": "approved", "note": "검토 완료"}), config=config
    )
    assert resumed["decision_status"] == "approved"
    assert resumed["applied_status"] == "approved"
    assert resumed["applied_note"] == "검토 완료"
    assert resumed["material_status"] == "approved"
    assert captured["material"].status is MaterialStatus.APPROVED
    connection.close()


def test_pipeline_resumes_across_restart(tmp_path: Path) -> None:
    db_path = str(tmp_path / "pipeline-checkpoints.sqlite3")
    config = {"configurable": {"thread_id": "pipeline-restart-1"}}

    # Process 1: generate, hit the parent-review interrupt, then "crash".
    gen1, cap1 = _pieces()
    conn1, saver1 = _sqlite(db_path)
    graph1 = build_material_pipeline_graph(generator=gen1, checkpointer=saver1)
    first = graph1.invoke({}, config=config)
    assert first["__interrupt__"]
    generated_title = first["title"]
    conn1.close()
    del graph1, saver1, conn1  # nothing in memory survives the restart

    # Process 2: brand-new connection + graph over the same on-disk checkpoint resumes.
    gen2, _cap2 = _pieces()
    conn2, saver2 = _sqlite(db_path)
    graph2 = build_material_pipeline_graph(generator=gen2, checkpointer=saver2)
    resumed = graph2.invoke(
        Command(resume={"status": "approved", "note": "재시작 후 승인"}), config=config
    )
    assert resumed["title"] == generated_title  # draft survived from the persisted checkpoint
    assert resumed["decision_status"] == "approved"
    assert resumed["applied_status"] == "approved"
    assert resumed["applied_note"] == "재시작 후 승인"
    conn2.close()


def test_pipeline_revision_path() -> None:
    generator, captured = _pieces()
    connection, saver = _sqlite(":memory:")
    graph = build_material_pipeline_graph(
        generator=generator, review_applier=_applier(captured), checkpointer=saver
    )
    config = {"configurable": {"thread_id": "pipeline-revision-1"}}

    graph.invoke({}, config=config)
    resumed = graph.invoke(
        Command(resume={"status": "revision_requested", "note": "힌트를 늘려 주세요"}),
        config=config,
    )
    assert resumed["applied_status"] == "revision_requested"
    assert resumed["material_status"] == "revision_requested"
    assert captured["material"].status is MaterialStatus.REVISION_REQUESTED
    connection.close()


def test_pipeline_reject_path() -> None:
    generator, captured = _pieces()
    connection, saver = _sqlite(":memory:")
    graph = build_material_pipeline_graph(
        generator=generator, review_applier=_applier(captured), checkpointer=saver
    )
    config = {"configurable": {"thread_id": "pipeline-reject-1"}}

    graph.invoke({}, config=config)
    resumed = graph.invoke(
        Command(resume={"status": "rejected", "note": None}), config=config
    )
    assert resumed["applied_status"] == "rejected"
    assert resumed["applied_note"] is None
    assert resumed["material_status"] == "rejected"
    assert captured["material"].status is MaterialStatus.REJECTED
    connection.close()
