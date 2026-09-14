import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from growwise.workflows import build_material_review_graph


def test_material_review_interrupts_and_resumes_from_sqlite_checkpoint(tmp_path):
    connection = sqlite3.connect(tmp_path / "review-checkpoints.sqlite3", check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    graph = build_material_review_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "material-review-1"}}

    first = graph.invoke(
        {"material_id": "material-1", "child_id": "child-1", "title": "테스트 자료"},
        config=config,
    )

    assert first["__interrupt__"]
    resumed = graph.invoke(
        Command(resume={"status": "approved", "note": "검토 완료"}),
        config=config,
    )

    assert resumed["decision_status"] == "approved"
    assert resumed["decision_note"] == "검토 완료"
    connection.close()
