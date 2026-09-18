from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from growwise.api.contracts import ConversationCreateRequest, ConversationTurnRequest
from growwise.api.dependencies import (
    build_child_context_service,
    get_conversation_store,
    get_model_provider,
    get_store,
)
from growwise.services import ConversationService, ConversationSession
from growwise.storage import EntityStore

router = APIRouter(tags=["conversations"])


@router.post("/v1/children/{child_id}/conversations", response_model=ConversationSession)
def create_conversation(
    child_id: UUID,
    request: ConversationCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ConversationSession:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    session = ConversationSession(child_id=str(child_id), title=request.title)
    get_conversation_store().save(session)
    return session


@router.get("/v1/children/{child_id}/conversations")
def list_conversations(
    child_id: UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict]:
    sessions = get_conversation_store().list_for_child(str(child_id), limit=limit)
    return [session.model_dump(mode="json") for session in sessions]


@router.get("/v1/conversations/{session_id}", response_model=ConversationSession)
def get_conversation(session_id: str) -> ConversationSession:
    session = get_conversation_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return session


@router.post("/v1/conversations/{session_id}/turns")
def append_conversation_turn(
    session_id: str,
    request: ConversationTurnRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> dict:
    conversation_store = get_conversation_store()
    session = conversation_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    if store.index.get_entity(session.child_id, entity_type="child_profile") is None:
        raise HTTPException(status_code=409, detail="conversation_child_not_found")

    service = ConversationService(
        context_service=build_child_context_service(store),
        provider=get_model_provider(),
    )
    answer = service.ask(session=session, question=request.question, limit=request.limit)
    conversation_store.save(session)
    return {
        "session_id": session.id,
        "thread_id": session.id,
        "answer": answer.model_dump(mode="json"),
        "turn_count": len(session.turns),
    }


@router.delete("/v1/conversations/{session_id}")
def delete_conversation(session_id: str) -> dict[str, bool]:
    return {"deleted": get_conversation_store().delete(session_id)}
