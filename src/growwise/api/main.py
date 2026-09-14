from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field
from uuid6 import uuid7

from growwise.config import Settings
from growwise.domain import (
    ChildProfile,
    LearningLog,
    Stage,
    WorkflowRun,
    WorkflowStatus,
)
from growwise.model import ModelProvider, create_model_provider
from growwise.services import InfantActivityService, NaturalLanguageSearch, ObservationEnricher
from growwise.storage import EntityStore
from growwise.workflows import build_observation_graph

app = FastAPI(title="GrowWise Core", version="0.1.0a0")


class ChildCreateRequest(BaseModel):
    nickname: str
    stage: Stage
    age_months: int | None = None
    interests: list[str] = Field(default_factory=list)


class ObservationRequest(BaseModel):
    child_id: UUID
    observation: str = Field(min_length=1, max_length=10_000)


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
    return create_model_provider(settings)


@lru_cache
def get_observation_graph():
    settings = get_settings()
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    checkpointer = SqliteSaver(connection)
    checkpointer.setup()
    return build_observation_graph(checkpointer=checkpointer)


@app.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_features_enabled": settings.llm_features_enabled,
        "model_provider": settings.model_provider,
    }


@app.post("/v1/children", response_model=ChildProfile)
def create_child(
    request: ChildCreateRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> ChildProfile:
    profile = ChildProfile(**request.model_dump())
    store.save(profile)
    return profile


@app.post("/v1/observations", response_model=LearningLog)
def create_observation(
    request: ObservationRequest,
    store: Annotated[EntityStore, Depends(get_store)],
) -> LearningLog:
    workflow = WorkflowRun(
        child_id=request.child_id,
        workflow_type="observation_ingest",
        thread_id=str(uuid7()),
    )
    store.save(workflow)

    try:
        graph = get_observation_graph()
        state = graph.invoke(
            {"child_id": str(request.child_id), "observation": request.observation},
            config={"configurable": {"thread_id": workflow.thread_id}},
        )
        if state.get("safety_flags"):
            workflow.status = WorkflowStatus.FAILED
            workflow.last_error_code = "observation_validation_failed"
            workflow.updated_at = datetime.now(UTC)
            store.save(workflow)
            raise HTTPException(status_code=422, detail={"flags": state["safety_flags"]})

        tags: list[str] = []
        interest: str | None = None
        difficulty_note: str | None = None
        next_activity: str | None = None
        provider = get_model_provider()
        if provider is not None:
            try:
                enrichment = ObservationEnricher(provider).enrich(state["normalized_observation"])
                tags = enrichment.tags
                interest = enrichment.interest
                difficulty_note = enrichment.difficulty_note
                next_activity = enrichment.next_activity
            except Exception:
                pass

        log = LearningLog(
            child_id=request.child_id,
            parent_observation=state["normalized_observation"],
            tags=tags,
            interest=interest,
            difficulty_note=difficulty_note,
            next_activity=next_activity,
        )
        store.save(log)
        workflow.status = WorkflowStatus.COMPLETED
        workflow.output_ref = str(log.id)
        workflow.updated_at = datetime.now(UTC)
        store.save(workflow)
        return log
    except HTTPException:
        raise
    except Exception:
        workflow.status = WorkflowStatus.FAILED
        workflow.last_error_code = "observation_workflow_failed"
        workflow.updated_at = datetime.now(UTC)
        store.save(workflow)
        raise


@app.get("/v1/children/{child_id}/observations")
def list_observations(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
) -> list[dict]:
    return store.index.list_entities(entity_type="learning_log", child_id=str(child_id))


@app.get("/v1/children/{child_id}/search")
def search_child_context(
    child_id: UUID,
    q: Annotated[str, Query(min_length=2, max_length=500)],
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict:
    service = NaturalLanguageSearch(store.index, provider=get_model_provider())
    return service.search(child_id=str(child_id), query=q, limit=limit).model_dump(mode="json")


@app.get("/v1/children/{child_id}/infant-activities")
def suggest_infant_activities(
    child_id: UUID,
    store: Annotated[EntityStore, Depends(get_store)],
    limit: Annotated[int, Query(ge=1, le=5)] = 3,
) -> dict:
    child_payload = store.index.get_entity(str(child_id), entity_type="child_profile")
    if child_payload is None:
        raise HTTPException(status_code=404, detail="child_not_found")

    child = ChildProfile.model_validate(child_payload)
    if child.stage is not Stage.INFANT_0_2:
        raise HTTPException(status_code=409, detail="child_is_not_in_infant_stage")

    logs = store.index.list_entities(entity_type="learning_log", child_id=str(child_id))
    recent_observations = [
        str(item.get("parent_observation", ""))
        for item in logs[:8]
        if item.get("parent_observation")
    ]
    service = InfantActivityService(provider=get_model_provider())
    result = service.suggest(
        age_months=child.age_months,
        recent_observations=recent_observations,
        interests=child.interests,
        limit=limit,
    )
    return result.model_dump(mode="json")


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "growwise.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
