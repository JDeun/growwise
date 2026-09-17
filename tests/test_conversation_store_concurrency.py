from __future__ import annotations

from datetime import UTC, datetime, timedelta

from growwise.services import ConversationSession, ConversationTurn, SQLiteConversationStore


def test_concurrent_session_snapshots_merge_distinct_turns(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    session = ConversationSession(child_id="child-a")
    store.save(session)

    first = store.get(session.id)
    second = store.get(session.id)
    assert first is not None and second is not None

    base = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)
    first.turns.append(ConversationTurn(role="user", content="첫 질문", created_at=base))
    first.updated_at = base
    second.turns.append(
        ConversationTurn(
            role="user",
            content="동시에 온 다른 질문",
            created_at=base + timedelta(seconds=1),
        )
    )
    second.updated_at = base + timedelta(seconds=1)

    store.save(first)
    store.save(second)

    merged = store.get(session.id)
    assert merged is not None
    assert [turn.content for turn in merged.turns] == ["첫 질문", "동시에 온 다른 질문"]


def test_stale_snapshot_cannot_overwrite_newer_session_metadata(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    base = datetime(2026, 9, 16, 1, 0, tzinfo=UTC)
    session = ConversationSession(
        child_id="child-a",
        title="처음 제목",
        created_at=base,
        updated_at=base,
    )
    store.save(session)

    stale = store.get(session.id)
    fresh = store.get(session.id)
    assert stale is not None and fresh is not None

    fresh.title = "최신 제목"
    fresh.updated_at = base + timedelta(seconds=2)
    fresh.turns.append(
        ConversationTurn(role="user", content="최신 질문", created_at=base + timedelta(seconds=2))
    )
    store.save(fresh)

    stale.title = "오래된 제목"
    stale.updated_at = base + timedelta(seconds=1)
    stale.turns.append(
        ConversationTurn(role="user", content="늦게 저장된 질문", created_at=base + timedelta(seconds=1))
    )
    store.save(stale)

    merged = store.get(session.id)
    assert merged is not None
    assert merged.title == "최신 제목"
    assert [turn.content for turn in merged.turns] == ["늦게 저장된 질문", "최신 질문"]


def test_delete_for_child_cascades_turns_without_touching_sibling(tmp_path) -> None:
    store = SQLiteConversationStore(tmp_path / "conversations.sqlite3")
    target = ConversationSession(child_id="child-a")
    target.turns.append(ConversationTurn(role="user", content="삭제할 질문"))
    sibling = ConversationSession(child_id="child-b")
    sibling.turns.append(ConversationTurn(role="user", content="보존할 질문"))
    store.save(target)
    store.save(sibling)

    assert store.delete_for_child("child-a") == 1
    assert store.get(target.id) is None
    preserved = store.get(sibling.id)
    assert preserved is not None
    assert preserved.turns[0].content == "보존할 질문"
