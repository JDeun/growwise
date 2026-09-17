from uuid import uuid4

from growwise.jobs import SQLiteJobQueue


def test_delete_for_child_matches_structured_owner_only(tmp_path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    target_child_id = str(uuid4())
    other_child_id = str(uuid4())

    owned = queue.enqueue(
        "photo_activity_analysis",
        {"child_id": target_child_id, "record_id": "owned-record"},
    )
    incidental = queue.enqueue(
        "background_note",
        {
            "child_id": other_child_id,
            "note": f"parent text happens to mention {target_child_id}",
        },
    )
    unrelated = queue.enqueue(
        "background_note",
        {"child_id": other_child_id, "note": "unrelated"},
    )

    assert queue.delete_for_child(target_child_id) == 1
    assert queue.get(owned.id) is None
    assert queue.get(incidental.id) is not None
    assert queue.get(unrelated.id) is not None
