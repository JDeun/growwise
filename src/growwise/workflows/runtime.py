from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.types import RetryPolicy, TimeoutPolicy


TRANSIENT_RETRY_POLICY = RetryPolicy(
    initial_interval=0.25,
    backoff_factor=2.0,
    max_interval=2.0,
    max_attempts=3,
    jitter=True,
    retry_on=(ConnectionError, TimeoutError),
)

EXTERNAL_NODE_TIMEOUT = TimeoutPolicy(
    run_timeout=30.0,
    idle_timeout=10.0,
    refresh_on="auto",
)


class DuplicateNodeName(ValueError):
    pass


class NodeRegistry:
    """Small explicit registry that prevents silently replacing workflow nodes."""

    def __init__(self) -> None:
        self._nodes: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, node: Callable[..., Any]) -> NodeRegistry:
        if not name or not name.strip():
            raise ValueError("node name must not be empty")
        if name in self._nodes:
            raise DuplicateNodeName(name)
        self._nodes[name] = node
        return self

    def get(self, name: str) -> Callable[..., Any]:
        try:
            return self._nodes[name]
        except KeyError as exc:
            raise KeyError(f"workflow node is not registered: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(self._nodes)
