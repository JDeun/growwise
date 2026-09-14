from growwise.services import ConversationService, ConversationSession


class FakeContextService:
    def __init__(self):
        self.queries = []

    def ask(self, *, child_id: str, query: str, limit: int = 8):
        from growwise.services import ContextAnswer

        self.queries.append((child_id, query, limit))
        return ContextAnswer(answer="근거 기반 답변", source_ids=["record:1"])


def test_conversation_without_provider_keeps_child_scope_and_turns():
    context = FakeContextService()
    service = ConversationService(context_service=context, provider=None)
    session = ConversationSession(child_id="child-1")

    answer = service.ask(session=session, question="최근 동물 관심 기록은?", limit=5)

    assert answer.source_ids == ["record:1"]
    assert context.queries == [("child-1", "최근 동물 관심 기록은?", 5)]
    assert [turn.role for turn in session.turns] == ["user", "assistant"]
    assert session.turns[1].source_ids == ["record:1"]
