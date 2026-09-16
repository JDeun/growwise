from __future__ import annotations

import json
import subprocess
import sys


def test_resource_collection_routes_have_single_owner_on_clean_app_start() -> None:
    """Verify the production app's route table in a fresh interpreter."""
    script = r'''
import json
import growwise.api.main as main
from fastapi.routing import APIRoute
from growwise.api.resource_routes import router as resource_router

routes = []
for route in main.app.routes:
    if not isinstance(route, APIRoute):
        continue
    routes.append(
        {
            "path": route.path.rstrip("/") or "/",
            "methods": sorted(route.methods or set()),
            "module": getattr(route.endpoint, "__module__", ""),
            "name": getattr(route.endpoint, "__name__", ""),
        }
    )
print(
    json.dumps(
        {
            "main_file": main.__file__,
            "resource_router_paths": [
                route.path for route in resource_router.routes if isinstance(route, APIRoute)
            ],
            "routes": routes,
        },
        sort_keys=True,
    )
)
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    diagnostic = json.loads(completed.stdout.strip())
    routes = [route for route in diagnostic["routes"] if route["path"] == "/v1/resources"]

    posts = [route for route in routes if "POST" in route["methods"]]
    gets = [route for route in routes if "GET" in route["methods"]]

    assert len(posts) == 1, diagnostic
    assert len(gets) == 1, diagnostic
    assert posts[0]["module"] == "growwise.api.resource_routes"
    assert gets[0]["module"] == "growwise.api.resource_routes"
