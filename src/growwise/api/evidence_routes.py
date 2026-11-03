"""Read current, visible originals behind saved conversation citation pointers."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from growwise.api.dependencies import get_rag_index, get_store
from growwise.rag import HybridRagIndex
from growwise.services.context import _ENTITY_TEXT_FIELDS, _entity_text
from growwise.services.entity_lock import entity_operation_lock
from growwise.services.record_time import record_time
from growwise.services.visibility import entity_visible_to_child
from growwise.storage import EntityStore

router = APIRouter(prefix="/v1", tags=["conversation-evidence"])
_ORIGINAL_TYPES = {
    "learning_log", "activity_plan", "resource", "generated_material", "photo_activity_record",
    "study_unit_progress", "mistake_record", "study_reflection", "self_explanation_log",
    "study_plan",
}
_DISPLAY_ENUMS = {
    "state": {"planned": "학습 예정", "in_progress": "학습 중", "review": "복습 필요",
              "revisit": "다시 확인", "comfortable": "현재는 편안함"},
    "mistake_type": {"concept": "개념", "process": "풀이 과정", "reading": "문제 읽기",
                     "calculation": "계산", "attention": "확인 누락",
                     "communication": "설명·표현", "other": "기타"},
}


class ConversationEvidence(BaseModel):
    source_id: str
    entity_id: UUID
    entity_type: str
    title: str
    occurred_at: datetime | None
    body: str
    source_url: str | None


def _display_body(payload: dict) -> str:
    # The header already supplies the title and event date. Preserve authored strings verbatim;
    # translate only typed metadata and never expose the context builder's raw-dict fallback.
    display = {key: value for key, _ in _ENTITY_TEXT_FIELDS
               if key not in {"title", "record_kind"}
               and isinstance(value := payload.get(key), str) and value.strip()}
    for field, labels in _DISPLAY_ENUMS.items():
        display.pop(field, None)
        value = payload.get(field)
        if isinstance(value, str) and value in labels:
            display[field] = labels[value]
    if isinstance(payload.get("evidence_checked"), bool):
        display["evidence_checked"] = payload["evidence_checked"]
    if payload.get("items"):
        display["items"] = payload["items"]
    return _entity_text(display)[:12_000] if display else "추가 본문이 없는 원본입니다."


def _safe_source_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 2048 or any(ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlparse(value)
        if (parsed.scheme in {"http", "https"} and parsed.hostname
                and parsed.username is None and parsed.password is None):
            return value
    except ValueError:
        pass
    return None


@router.get("/children/{child_id}/evidence", response_model=ConversationEvidence)
def resolve_conversation_evidence(
    child_id: UUID,
    source_id: Annotated[str, Query(min_length=1, max_length=500)],
    store: Annotated[EntityStore, Depends(get_store)],
    rag_index: Annotated[HybridRagIndex, Depends(get_rag_index)],
) -> ConversationEvidence:
    if store.index.get_entity(str(child_id), entity_type="child_profile") is None:
        raise HTTPException(status_code=404, detail="evidence_unavailable")
    prefix, separator, identifier = source_id.partition(":")
    if not separator or prefix not in {"record", "resource", "graph", "chunk"}:
        raise HTTPException(status_code=404, detail="evidence_unavailable")
    if prefix == "chunk":
        identifier = rag_index.source_entity_for_chunk(identifier) or ""
    try:
        entity_id = UUID(identifier)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="evidence_unavailable") from exc

    # Scope narrowing and child sharing use the same per-source lock. Never display a cached chunk
    # body: an old global chunk must not expose a source that is now private or has been edited.
    with store.mutation_window(), entity_operation_lock(entity_id):
        payload = store.index.get_entity(str(entity_id))
        if (
            payload is None or payload.get("entity_type") not in _ORIGINAL_TYPES
            or payload.get("derived") is True
            or not entity_visible_to_child(
                store.index, entity_id=str(entity_id), child_id=str(child_id),
            )
            or (payload.get("entity_type") == "photo_activity_record"
                and payload.get("status") != "committed")
        ):
            raise HTTPException(status_code=404, detail="evidence_unavailable")
        return ConversationEvidence(
            source_id=source_id, entity_id=entity_id, entity_type=payload["entity_type"],
            title=str(payload.get("title") or "저장된 원본 기록")[:500],
            occurred_at=record_time(payload), body=_display_body(payload),
            source_url=_safe_source_url(payload.get("source_url")),
        )
