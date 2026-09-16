from __future__ import annotations

import json
import subprocess
import sys


def test_resource_collection_routes_have_single_owner_on_clean_app_start() -> None:
    """Verify the production app's resource route table in a fresh interpreter."""
    script = r'''
import json
import growwise.api.main as main
from fastapi.routing import APIRoute
from growwise.api.resource_routes import router as resource_router


def describe(route):
    return {
        "path": route.path,
        "methods": sorted(route.methods or set()),
        "module": getattr(route.endpoint, "__module__", ""),
        "name": getattr(route.endpoint, "__name__", ""),
    }

app_resource_routes = [
    describe(route)
    for route in main.app.routes
    if isinstance(route, APIRoute)
    and (
        "resource" in route.path
        or getattr(route.endpoint, "__module__", "") == "growwise.api.resource_routes"
    )
]
router_routes = [
    describe(route) for route in resource_router.routes if isinstance(route, APIRoute)
]
print(
    json.dumps(
        {
            "main_file": main.__file__,
            "app_resource_routes": app_resource_routes,
            "resource_router_routes": router_routes,
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
    routes = [
        route
        for route in diagnostic["app_resource_routes"]
        if (route["path"].rstrip("/") or "/") == "/v1/resources"
    ]

    posts = [route for route in routes if "POST" in route["methods"]]
    gets = [route for route in routes if "GET" in route["methods"]]

    assert len(posts) == 1, diagnostic
    assert len(gets) == 1, diagnostic
    assert posts[0]["module"] == "growwise.api.resource_routes"
    assert gets[0]["module"] == "growwise.api.resource_routes"
