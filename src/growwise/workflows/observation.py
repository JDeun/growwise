from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


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
    if not state.get("normalized_observation"):
        flags.append("empty_observation")
    return {"safety_flags": flags}


def build_observation_graph():
    builder = StateGraph(ObservationState)
    builder.add_node("normalize", normalize)
    builder.add_node("safety_check", safety_check)
    builder.add_edge(START, "normalize")
    builder.add_edge("normalize", "safety_check")
    builder.add_edge("safety_check", END)
    return builder.compile()
