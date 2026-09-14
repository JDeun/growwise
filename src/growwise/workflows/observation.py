from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .runtime import NodeRegistry


class ObservationState(TypedDict, total=False):
    child_id: str
    observation: str
    normalized_observation: str
    tags: list[str]
    safety_flags: list[str]


def normalize(state: ObservationState) -> ObservationState:
    text = " ".join(state["observation"].split())
    return {"normalized_observation": text}


def safety_check(state: ObservationState) -> ObservationState:
    flags: list[str] = []
    if not state.get("normalized_observation", "").strip():
        flags.append("empty_observation")
    return {"safety_flags": flags}


def observation_node_registry() -> NodeRegistry:
    return NodeRegistry().register("normalize", normalize).register("safety_check", safety_check)


def build_observation_graph(checkpointer=None):
    registry = observation_node_registry()
    builder = StateGraph(ObservationState)
    builder.add_node("normalize", registry.get("normalize"))
    builder.add_node("safety_check", registry.get("safety_check"))
    builder.add_edge(START, "normalize")
    builder.add_edge("normalize", "safety_check")
    builder.add_edge("safety_check", END)
    return builder.compile(checkpointer=checkpointer)
