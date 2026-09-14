from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from growwise.domain import MaterialStatus


class MaterialReviewState(TypedDict, total=False):
    material_id: str
    child_id: str
    title: str
    decision_status: str
    decision_note: str | None


_ALLOWED_DECISIONS = {
    MaterialStatus.APPROVED.value,
    MaterialStatus.REVISION_REQUESTED.value,
    MaterialStatus.REJECTED.value,
}


def await_parent_review(state: MaterialReviewState) -> MaterialReviewState:
    response = interrupt(
        {
            "kind": "material_parent_review",
            "material_id": state["material_id"],
            "child_id": state["child_id"],
            "title": state["title"],
            "allowed": sorted(_ALLOWED_DECISIONS),
        }
    )
    if not isinstance(response, dict):
        raise ValueError("parent review response must be an object")
    status = str(response.get("status", ""))
    if status not in _ALLOWED_DECISIONS:
        raise ValueError(f"unsupported parent review decision: {status}")
    note_value = response.get("note")
    note = None if note_value is None else str(note_value)
    return {"decision_status": status, "decision_note": note}


def build_material_review_graph(checkpointer=None):
    builder = StateGraph(MaterialReviewState)
    builder.add_node("parent_review", await_parent_review)
    builder.add_edge(START, "parent_review")
    builder.add_edge("parent_review", END)
    return builder.compile(checkpointer=checkpointer)
