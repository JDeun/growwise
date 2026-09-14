from growwise.workflows import build_observation_graph


def test_observation_graph_normalizes_whitespace() -> None:
    graph = build_observation_graph()
    result = graph.invoke({"child_id": "child-1", "observation": "  책을   오래 바라봄  "})
    assert result["normalized_observation"] == "책을 오래 바라봄"
    assert result["safety_flags"] == []
