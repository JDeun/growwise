"""Integrated material pipeline: generate -> parent-review interrupt -> apply decision.

This runs generation and the human-in-the-loop parent review on ONE LangGraph thread with
ONE checkpointer, so a freshly generated draft flows straight into the parent-review interrupt
on the same ``thread_id`` and resumes (even across a full process restart) from the persisted
checkpoint. The interrupt contract is reused verbatim from the standalone review graph
(``await_parent_review``); the separate review graph and ``MaterialReviewService`` are untouched.

The generator is injected as a zero-argument producer so no generation *request* (which may
carry PII such as a child nickname) is ever placed into graph state or the checkpoint. Only the
resulting draft's non-identifying fields (id/child_id/title/content) are persisted for review.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from growwise.domain import GeneratedMaterial

from .material_review import await_parent_review

# A bound draft producer. Kept zero-arg on purpose: the caller binds the request at build time
# (e.g. ``lambda: service.generate(child=child, kind=kind, topic=topic)``) so untrusted request
# data never reaches the persisted state.
GeneratorFn = Callable[[], GeneratedMaterial]

# Optional side-effect hook run after a decision is reached (e.g. persist the transition). It
# receives the current state and may return extra keys to merge into the state.
ReviewApplierFn = Callable[["MaterialPipelineState"], Mapping[str, Any] | None]

class MaterialPipelineState(TypedDict, total=False):
    # Populated by the ``generate`` node (also feeds the reused review interrupt contract).
    material_id: str
    child_id: str
    title: str
    content_markdown: str
    generator_mode: str
    material_status: str
    # Populated by the reused ``parent_review`` interrupt node.
    decision_status: str
    decision_note: str | None
    # Populated by the ``apply_decision`` node.
    applied_status: str
    applied_note: str | None


def _make_generate(generator: GeneratorFn):
    def generate(_state: MaterialPipelineState) -> MaterialPipelineState:
        material = generator()
        return {
            "material_id": str(material.id),
            "child_id": str(material.child_id),
            "title": material.title,
            "content_markdown": material.content_markdown,
            "generator_mode": material.generator_mode,
            "material_status": material.status.value,
        }

    return generate


def _make_apply(review_applier: ReviewApplierFn | None):
    def apply_decision(state: MaterialPipelineState) -> MaterialPipelineState:
        result: MaterialPipelineState = {
            "applied_status": state["decision_status"],
            "applied_note": state.get("decision_note"),
        }
        if review_applier is not None:
            extra = review_applier(state)
            if extra:
                result.update(extra)  # type: ignore[typeddict-item]
        return result

    return apply_decision


def build_material_pipeline_graph(
    *,
    generator: GeneratorFn,
    review_applier: ReviewApplierFn | None = None,
    checkpointer: Any = None,
) -> Any:
    """Compile the integrated generate -> parent_review -> apply_decision pipeline.

    ``generator`` is the injected draft producer; ``review_applier`` is an optional hook to apply
    the decision to durable storage. Pass a checkpointer (e.g. ``SqliteSaver``) to make the
    parent-review interrupt resumable across restarts on the same ``thread_id``.
    """
    builder = StateGraph(MaterialPipelineState)
    builder.add_node("generate", _make_generate(generator))
    builder.add_node("parent_review", await_parent_review)  # reuse the exact review interrupt
    builder.add_node("apply_decision", _make_apply(review_applier))
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "parent_review")
    builder.add_edge("parent_review", "apply_decision")
    builder.add_edge("apply_decision", END)
    return builder.compile(checkpointer=checkpointer)
