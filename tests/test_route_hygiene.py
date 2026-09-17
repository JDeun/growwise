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
from fastapi.routing import APIRoute
from growwise.api.main import app

routes = []
inventory = []
for route in app.routes:
    if not isinstance(route, APIRoute):
        continue
    path = route.path.rstrip("/") or "/"
    item = {
        "path": path,
        "methods": sorted(route.methods or set()),
        "module": getattr(route.endpoint, "__module__", ""),
        "name": getattr(route.endpoint, "__name__", ""),
    }
    if "resource" in path:
        inventory.append(item)
    if path == "/v1/resources":
        routes.append(item)
print(json.dumps({"routes": routes, "inventory": inventory}, sort_keys=True))
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
    routes = result["routes"]
    posts = [route for route in routes if "POST" in route["methods"]]
    gets = [route for route in routes if "GET" in route["methods"]]

    assert len(posts) == 1, result
    assert len(gets) == 1, result
    assert posts[0]["module"] == "growwise.api.resource_routes"
    assert gets[0]["module"] == "growwise.api.resource_routes"
