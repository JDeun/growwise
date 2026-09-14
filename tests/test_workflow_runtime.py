import pytest

from growwise.workflows import (
    EXTERNAL_NODE_TIMEOUT,
    TRANSIENT_RETRY_POLICY,
    DuplicateNodeName,
    NodeRegistry,
)


def test_node_registry_rejects_duplicate_names():
    registry = NodeRegistry().register("node", lambda state: state)

    with pytest.raises(DuplicateNodeName):
        registry.register("node", lambda state: state)


def test_runtime_policies_are_bounded_for_local_desktop_use():
    assert TRANSIENT_RETRY_POLICY.max_attempts == 3
    assert TRANSIENT_RETRY_POLICY.max_interval == 2.0
    assert EXTERNAL_NODE_TIMEOUT.run_timeout == 30.0
    assert EXTERNAL_NODE_TIMEOUT.idle_timeout == 10.0
