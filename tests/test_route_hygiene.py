from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_resource_collection_routes_have_single_owner_on_clean_app_start() -> None:
    """Verify route ownership in a fresh interpreter against this checkout's source tree."""
    script = r'''
import json
import growwise.api.main as main_module
import growwise.api.resource_routes as resource_module
import growwise.api.study_routes as study_module
from fastapi.routing import APIRoute


def inventory(routes):
    result = []
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path.rstrip("/") or "/"
        if "resource" not in path:
            continue
        result.append({
            "path": path,
            "methods": sorted(route.methods or set()),
            "module": getattr(route.endpoint, "__module__", ""),
            "name": getattr(route.endpoint, "__name__", ""),
        })
    return result

print(json.dumps({
    "app": inventory(main_module.app.routes),
    "study": inventory(study_module.router.routes),
    "resource": inventory(resource_module.router.routes),
    "resource_route_count_at_mount": study_module._RESOURCE_ROUTE_COUNT_AT_MOUNT,
    "resource_router_id_at_mount": study_module._RESOURCE_ROUTER_ID_AT_MOUNT,
    "resource_router_id_final": id(resource_module.router),
    "study_paths_after_mount": study_module._RESOURCE_STUDY_PATHS_AFTER_MOUNT,
    "resource_import_stack": resource_module._IMPORT_STACK,
}, sort_keys=True))
'''
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH")
    source_path = str(repo_root / "src")
    env["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{current_pythonpath}" if current_pythonpath else source_path
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        cwd=repo_root,
        env=env,
    )
    result = json.loads(completed.stdout.strip())

    assert result["resource"], "resource router has no resource routes"
    study_collection = [route for route in result["study"] if route["path"] == "/v1/resources"]
    assert study_collection, result
    assert result["app"], f"resource routes lost before app mount: {result['study']}"

    routes = [route for route in result["app"] if route["path"] == "/v1/resources"]
    posts = [route for route in routes if "POST" in route["methods"]]
    gets = [route for route in routes if "GET" in route["methods"]]

    assert len(posts) == 1, result
    assert len(gets) == 1, result
    assert posts[0]["module"] == "growwise.api.resource_routes"
    assert gets[0]["module"] == "growwise.api.resource_routes"
