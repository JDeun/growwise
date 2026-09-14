import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.workflows import build_observation_graph


def test_observation_graph_persists_checkpoint(tmp_path) -> None:
    connection = sqlite3.connect(
        tmp_path / "checkpoints.sqlite3",
        check_same_thread=False,
    )
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    graph = build_observation_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "test-observation-thread"}}

    result = graph.invoke(
        {"child_id": "child-1", "observation": "  책 표지를 오래 바라봄  "},
        config=config,
    )

    assert result["normalized_observation"] == "책 표지를 오래 바라봄"
    assert checkpointer.get_tuple(config) is not None
