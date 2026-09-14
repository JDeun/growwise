from __future__ import annotations

from functools import lru_cache
from uuid import UUID

import uvicorn
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from growwise.config import Settings
from growwise.domain import ChildProfile, LearningLog, Stage
from growwise.storage import EntityStore
from growwise.workflows import build_observation_graph

app = FastAPI(title="GrowWise Core", version="0.1.0a0")
observation_graph = build_observation_graph()


class ChildCreateRequest(BaseModel):
    nickname: str
    stage: Stage
    age_months: int | None = None
    interests: list[str] = []


class ObservationRequest(BaseModel):
    child_id: UUID
    observation: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_store(settings: Settings = Depends(get_settings)) -> EntityStore:
    return EntityStore(settings.records_dir, settings.index_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/children", response_model=ChildProfile)
def create_child(request: ChildCreateRequest, store: EntityStore = Depends(get_store)) -> ChildProfile:
    profile = ChildProfile(**request.model_dump())
    store.save(profile)
    return profile


@app.post("/v1/observations", response_model=LearningLog)
def create_observation(
    request: ObservationRequest,
    store: EntityStore = Depends(get_store),
) -> LearningLog:
    state = observation_graph.invoke(
        {"child_id": str(request.child_id), "observation": request.observation}
    )
    if state.get("safety_flags"):
        # First milestone has only deterministic validation. Rich policy errors will become typed
        # API errors when the safety layer expands.
        raise ValueError(f"Observation rejected: {state['safety_flags']}")

    log = LearningLog(
        child_id=request.child_id,
        parent_observation=state["normalized_observation"],
        tags=state.get("tags", []),
    )
    store.save(log)
    return log


@app.get("/v1/children/{child_id}/observations")
def list_observations(
    child_id: UUID,
    store: EntityStore = Depends(get_store),
) -> list[dict]:
    return store.index.list_entities(entity_type="learning_log", child_id=str(child_id))


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
