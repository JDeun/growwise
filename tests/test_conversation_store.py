from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore


def test_conversation_store_round_trip(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    session = ConversationSession(child_id="child-1", title="동물 관심")
    session.turns.append(ConversationTurn(role="user", content="최근 동물 관심 기록은?"))

    store.save(session)

    loaded = store.get(session.id)
    assert loaded is not None
    assert loaded.child_id == "child-1"
    assert loaded.turns[0].content == "최근 동물 관심 기록은?"
    assert store.list_for_child("child-1")[0].id == session.id

    assert store.delete(session.id) is True
    assert store.get(session.id) is None
