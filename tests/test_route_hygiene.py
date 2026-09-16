from fastapi.routing import APIRoute

from growwise.api.main import app


def _canonical_path(path: str) -> str:
    return path.rstrip("/") or "/"


def _matching_routes(path: str, method: str) -> list[APIRoute]:
    normalized = _canonical_path(path)
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and _canonical_path(route.path) == normalized
        and method in (route.methods or set())
    ]


def _resource_route_inventory() -> list[tuple[str, list[str], str, str]]:
    inventory: list[tuple[str, list[str], str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        endpoint = route.endpoint
        module = getattr(endpoint, "__module__", "")
        name = getattr(endpoint, "__name__", "")
        if "resource" in route.path or module == "growwise.api.resource_routes":
            inventory.append((route.path, sorted(route.methods or set()), module, name))
    return inventory


def test_resource_collection_routes_have_single_owner() -> None:
    posts = _matching_routes("/v1/resources", "POST")
    gets = _matching_routes("/v1/resources", "GET")
    inventory = _resource_route_inventory()

    assert len(posts) == 1, inventory
    assert len(gets) == 1, inventory
    assert posts[0].endpoint.__module__ == "growwise.api.resource_routes"
    assert gets[0].endpoint.__module__ == "growwise.api.resource_routes"
