from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from growwise.workflows import build_observation_graph

app = FastAPI(title="GrowWise Core", version="0.1.0a0")
observation_graph = build_observation_graph()


class ObservationRequest(BaseModel):
    child_id: str
    observation: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/observations/normalize")
def normalize_observation(request: ObservationRequest) -> dict:
    return observation_graph.invoke(request.model_dump())


def run() -> None:
    uvicorn.run("growwise.api.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
