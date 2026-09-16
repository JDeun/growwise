from __future__ import annotations

import json
import subprocess
import sys


def test_resource_collection_routes_have_single_owner_on_clean_app_start() -> None:
    """Verify the production app's route table in a fresh interpreter.

    Several API tests intentionally share the module-level FastAPI application for dependency
    overrides. Route ownership is a cold-start invariant, so validate it in an isolated interpreter
    instead of depending on mutable process-global state left by unrelated tests.
    """
    script = r'''
import json
from fastapi.routing import APIRoute
from growwise.api.main import app

routes = []
for route in app.routes:
    if not isinstance(route, APIRoute):
        continue
    path = route.path.rstrip("/") or "/"
    if path != "/v1/resources":
        continue
    routes.append(
        {
            "path": path,
            "methods": sorted(route.methods or set()),
            "module": getattr(route.endpoint, "__module__", ""),
            "name": getattr(route.endpoint, "__name__", ""),
        }
    )
print(json.dumps(routes, sort_keys=True))
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    routes = json.loads(completed.stdout.strip())

    posts = [route for route in routes if "POST" in route["methods"]]
    gets = [route for route in routes if "GET" in route["methods"]]

    assert len(posts) == 1, routes
    assert len(gets) == 1, routes
    assert posts[0]["module"] == "growwise.api.resource_routes"
    assert gets[0]["module"] == "growwise.api.resource_routes"
