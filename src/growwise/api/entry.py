from __future__ import annotations

import uvicorn

from growwise.config import Settings
from growwise.runtime_lock import DataDirectoryLock

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def run() -> None:
    settings = Settings()
    if settings.api_host not in _LOOPBACK_HOSTS:
        raise RuntimeError(
            "GrowWise Core is local-only and must bind to a loopback address; "
            "remote serving requires a separately authenticated deployment mode"
        )
    with DataDirectoryLock(settings.data_dir):
        uvicorn.run(
            "growwise.api.main:app",
            host=settings.api_host,
            port=settings.api_port,
            reload=False,
        )
