from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from growwise.domain import MaterialStatus

logger = logging.getLogger(__name__)


class MaterialReviewState(TypedDict, total=False):
    material_id: str
    child_id: str
    title: str
    decision_status: str
    decision_note: str | None
    projection_degraded: bool


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


class ResilientMaterialReviewGraph:
    """Treat LangGraph checkpoint state as a rebuildable workflow projection.

    The GeneratedMaterial Markdown record is authoritative. A checkpoint database outage must not
    turn a committed material/version into an apparent failed request that callers retry into a
    sibling version. We therefore log checkpoint failures and fall back to the already-validated API
    command. The domain transition service remains authoritative for allowed status transitions.
    """

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def invoke(self, input: Any, *args: Any, **kwargs: Any) -> dict:
        try:
            return self._graph.invoke(input, *args, **kwargs)
        except Exception:
            logger.exception("material review checkpoint projection failed")
            if isinstance(input, Command):
                resume = input.resume
                if isinstance(resume, dict):
                    status = str(resume.get("status", ""))
                    if status not in _ALLOWED_DECISIONS:
                        raise
                    note_value = resume.get("note")
                    return {
                        "decision_status": status,
                        "decision_note": None if note_value is None else str(note_value),
                        "projection_degraded": True,
                    }
                raise
            if isinstance(input, dict):
                return {**input, "projection_degraded": True}
            raise

    def __getattr__(self, name: str) -> Any:
        return getattr(self._graph, name)


def build_material_review_graph(checkpointer=None):
    builder = StateGraph(MaterialReviewState)
    builder.add_node("parent_review", await_parent_review)
    builder.add_edge(START, "parent_review")
    builder.add_edge("parent_review", END)
    compiled = builder.compile(checkpointer=checkpointer)
    return ResilientMaterialReviewGraph(compiled)
