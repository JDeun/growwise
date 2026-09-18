from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from langgraph.checkpoint.sqlite import SqliteSaver

from growwise.config import Settings
from growwise.idempotency import SQLiteIdempotencyStore
from growwise.maintenance import DATA_MAINTENANCE
from growwise.model import ModelProvider, create_model_provider
from growwise.rag import HybridRagIndex, OllamaEmbeddingProvider
from growwise.services import ChildContextService, SQLiteConversationStore
from growwise.storage import EntityStore
from growwise.workflows import build_material_review_graph, build_observation_graph

logger = logging.getLogger(__name__)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_store(settings: Annotated[Settings, Depends(get_settings)]) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@lru_cache
def get_model_provider() -> ModelProvider | None:
    settings = get_settings()
    if not settings.llm_features_enabled:
        return None
    try:
        return create_model_provider(settings)
    except Exception:
        logger.exception("model provider unavailable; continuing in deterministic core-only mode")
        return None


@lru_cache
def get_rag_index() -> HybridRagIndex:
    settings = get_settings()
    embedding = None
    if settings.embedding_features_enabled:
        try:
            embedding = OllamaEmbeddingProvider(
                model=settings.embedding_model_id,
                base_url=settings.model_base_url,
            )
        except Exception:
            logger.exception("embedding provider unavailable; RAG will use lexical search")
            embedding = None
    return HybridRagIndex(settings.rag_index_path, embedding=embedding)


@lru_cache(maxsize=4)
def _get_conversation_store(path: str, generation: int) -> SQLiteConversationStore:
    del generation
    return SQLiteConversationStore(Path(path))


def get_conversation_store() -> SQLiteConversationStore:
    settings = get_settings()
    generation = DATA_MAINTENANCE.generation
    with DATA_MAINTENANCE.mutation(expected_generation=generation):
        return _get_conversation_store(
            str(settings.conversations_path.absolute()),
            generation,
        )


@lru_cache(maxsize=4)
def _get_idempotency_store(path: str, generation: int) -> SQLiteIdempotencyStore:
    del generation
    return SQLiteIdempotencyStore(Path(path))


def get_idempotency_store() -> SQLiteIdempotencyStore:
    settings = get_settings()
    generation = DATA_MAINTENANCE.generation
    with DATA_MAINTENANCE.mutation(expected_generation=generation):
        return _get_idempotency_store(
            str(settings.idempotency_path.absolute()),
            generation,
        )


# Preserve the historical test/downstream cache-reset seam while keying the actual cached object by
# data generation. A destructive restore therefore obtains fresh generation-bound stores without
# forcing every caller to know about the coordinator.
get_conversation_store.cache_clear = _get_conversation_store.cache_clear  # type: ignore[attr-defined]
get_idempotency_store.cache_clear = _get_idempotency_store.cache_clear  # type: ignore[attr-defined]


@lru_cache
def get_observation_graph():
    settings = get_settings()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_observation_graph(checkpointer=checkpointer)


@lru_cache
def get_material_review_graph():
    settings = get_settings()
    try:
        settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(connection)
        checkpointer.setup()
        return build_material_review_graph(checkpointer=checkpointer)
    except Exception:
        logger.exception(
            "material review checkpoint unavailable; using rebuildable in-memory projection"
        )
        return build_material_review_graph(checkpointer=None)


def build_child_context_service(store: EntityStore) -> ChildContextService:
    return ChildContextService(
        entity_index=store.index,
        rag_index=get_rag_index(),
        provider=get_model_provider(),
    )
