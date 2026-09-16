from fastapi.routing import APIRoute

from growwise.api.main import app


def _matching_routes(path: str, method: str) -> list[APIRoute]:
    normalized = path.rstrip("/") or "/"
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path.rstrip("/") or "/") == normalized
        and method in (route.methods or set())
    ]


def test_resource_collection_routes_have_single_owner() -> None:
    posts = _matching_routes("/v1/resources", "POST")
    gets = _matching_routes("/v1/resources", "GET")

    assert len(posts) == 1
    assert len(gets) == 1
    assert posts[0].endpoint.__module__ == "growwise.api.resource_routes"
    assert gets[0].endpoint.__module__ == "growwise.api.resource_routes"
