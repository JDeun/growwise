from __future__ import annotations

import os

import uvicorn
from fastapi import Request
from pydantic import ValidationError
from starlette.responses import JSONResponse

from growwise.api.background_ai import start_background_ai_runner
from growwise.api.desktop_security import install_desktop_security
from growwise.api.main import app
from growwise.api.photo_routes import start_photo_job_runner
from growwise.config import Settings

_SESSION_TOKEN_ENV = "GROWWISE_SESSION_TOKEN"


def _session_token() -> str:
    token = os.environ.get(_SESSION_TOKEN_ENV, "").strip()
    if not token:
        raise RuntimeError(f"{_SESSION_TOKEN_ENV} is required for the desktop Core sidecar")
    return token


install_desktop_security(app, session_token=_session_token())


@app.exception_handler(ValidationError)
async def domain_validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors(include_url=False)})


def run() -> None:
    settings = Settings()
    if settings.api_host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("desktop Core must bind to a loopback address")
    # Durable background workers reclaim interrupted jobs before the UI begins issuing requests.
    # They remain idle when their queues are empty, and AI failure never blocks Core startup.
    if settings.llm_features_enabled:
        start_background_ai_runner()
    if settings.vision_features_enabled:
        start_photo_job_runner()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port, log_level="warning")


if __name__ == "__main__":
    run()
