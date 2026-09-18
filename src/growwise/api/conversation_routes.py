from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from uuid6 import uuid7

from growwise.api.contracts import ConversationCreateRequest, ConversationTurnRequest
from growwise.api.dependencies import (
    build_child_context_service,
    get_conversation_store,
    get_idempotency_store,
    get_model_provider,
    get_store,
)
from growwise.idempotency import (
    IdempotencyConflict,
    IdempotencyStatus,
    request_fingerprint,
)
from growwise.services import ConversationService, ConversationSession
from growwise.storage import EntityStore

router = APIRouter(tags=["conversations"])


@router.post("/v1/children/{child_id}/conversations", response_model=ConversationSession)
def create_conversation(
    child_id: UUID,
    request: ConversationCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> ConversationSession:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="child_not_found")
    conversation_store = get_conversation_store()
    idempotency_store = get_idempotency_store() if idempotency_key is not None else None
    request_hash = request_fingerprint(
        {"child_id": str(child_id), **request.model_dump(mode="json")}
    )
    reserved_session_id = str(uuid7())
    claim = None
    if idempotency_key is not None:
        assert idempotency_store is not None
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="conversation_session",
                resource_id=reserved_session_id,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        reserved_session_id = claim.record.resource_id
        if not claim.acquired:
            existing = conversation_store.get(reserved_session_id)
            if existing is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return existing
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    session = ConversationSession(
        id=reserved_session_id,
        child_id=str(child_id),
        title=request.title,
    )
    try:
        conversation_store.save(session)
        if claim is not None and claim.acquired and idempotency_store is not None:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return session
    except Exception:
        if claim is not None and claim.acquired and idempotency_store is not None:
            existing = conversation_store.get(claim.record.resource_id)
            if existing is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
            else:
                idempotency_store.complete(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise


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


def _existing_exchange(
    *,
    session: ConversationSession,
    operation_key: str,
    operation_hash: str,
) -> dict[str, object] | None:
    matched = [turn for turn in session.turns if turn.operation_key == operation_key]
    if not matched:
        return None
    if any(turn.operation_hash != operation_hash for turn in matched):
        raise HTTPException(status_code=409, detail="idempotency_key_reused_for_different_request")
    user_turn = next((turn for turn in matched if turn.role == "user"), None)
    assistant_turn = next((turn for turn in matched if turn.role == "assistant"), None)
    if user_turn is None or assistant_turn is None:
        return None
    return {
        "session_id": session.id,
        "thread_id": session.id,
        "answer": {
            "answer": assistant_turn.content,
            "source_ids": assistant_turn.source_ids,
            "insufficient_evidence": bool(assistant_turn.insufficient_evidence),
        },
        "turn_count": len(session.turns),
    }


@router.post("/v1/conversations/{session_id}/turns")
def append_conversation_turn(
    session_id: str,
    request: ConversationTurnRequest,
    store: Annotated[EntityStore, Depends(get_store)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> dict[str, object]:
    conversation_store = get_conversation_store()
    session = conversation_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    if store.index.get_entity(session.child_id, entity_type="child_profile") is None:
        raise HTTPException(status_code=409, detail="conversation_child_not_found")

    idempotency_store = get_idempotency_store() if idempotency_key is not None else None
    request_hash = request_fingerprint(
        {"session_id": session_id, **request.model_dump(mode="json")}
    )
    claim = None
    if idempotency_key is not None:
        assert idempotency_store is not None
        try:
            claim = idempotency_store.claim(
                key=idempotency_key,
                request_hash=request_hash,
                resource_type="conversation_turn",
                resource_id=str(uuid7()),
            )
        except IdempotencyConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not claim.acquired:
            existing_exchange = _existing_exchange(
                session=session,
                operation_key=idempotency_key,
                operation_hash=request_hash,
            )
            if existing_exchange is not None:
                if claim.record.status is IdempotencyStatus.PENDING:
                    idempotency_store.complete(
                        key=claim.record.key,
                        request_hash=claim.record.request_hash,
                        resource_id=claim.record.resource_id,
                    )
                return existing_exchange
            if claim.record.status is IdempotencyStatus.COMPLETED:
                raise HTTPException(status_code=409, detail="idempotency_resource_missing")
            raise HTTPException(status_code=409, detail="idempotency_in_progress")

    service = ConversationService(
        context_service=build_child_context_service(store),
        provider=get_model_provider(),
    )
    try:
        answer = service.ask(
            session=session,
            question=request.question,
            limit=request.limit,
            operation_key=idempotency_key,
            operation_hash=request_hash if idempotency_key is not None else None,
        )
        conversation_store.save(session)
        if claim is not None and claim.acquired and idempotency_store is not None:
            idempotency_store.complete(
                key=claim.record.key,
                request_hash=claim.record.request_hash,
                resource_id=claim.record.resource_id,
            )
        return {
            "session_id": session.id,
            "thread_id": session.id,
            "answer": answer.model_dump(mode="json"),
            "turn_count": len(session.turns),
        }
    except Exception:
        if claim is not None and claim.acquired and idempotency_store is not None:
            persisted = conversation_store.get(session_id)
            existing_exchange = (
                _existing_exchange(
                    session=persisted,
                    operation_key=idempotency_key,
                    operation_hash=request_hash,
                )
                if persisted is not None and idempotency_key is not None
                else None
            )
            if existing_exchange is None:
                idempotency_store.release(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
            else:
                idempotency_store.complete(
                    key=claim.record.key,
                    request_hash=claim.record.request_hash,
                    resource_id=claim.record.resource_id,
                )
        raise


@router.delete("/v1/conversations/{session_id}")
def delete_conversation(session_id: str) -> dict[str, bool]:
    return {"deleted": get_conversation_store().delete(session_id)}
