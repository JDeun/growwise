from __future__ import annotations

import urllib.request

import pytest

from growwise.adapters.base import ExternalAdapterError
from growwise.adapters.http import (
    JsonHttpClient,
    _SameOriginHttpsRedirectHandler,
    _https_origin,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.invalid/api",
        "file:///tmp/public-data.json",
        "https://user:secret@example.invalid/api",
        "https:///missing-host",
        "https://example.invalid:bad-port/api",
    ],
)
def test_external_http_rejects_unsafe_endpoint_before_network(url: str) -> None:
    client = JsonHttpClient()

    with pytest.raises(ExternalAdapterError):
        client.get_json(url, params={})


def test_external_http_normalizes_default_https_origin() -> None:
    assert _https_origin("https://Example.Invalid/path") == ("example.invalid", 443)
    assert _https_origin("https://example.invalid:8443/path") == ("example.invalid", 8443)


@pytest.mark.parametrize(
    "target",
    [
        "https://other.invalid/redirected",
        "http://api.example.invalid/redirected",
        "https://api.example.invalid:8443/redirected",
    ],
)
def test_external_http_rejects_redirect_outside_original_https_origin(target: str) -> None:
    handler = _SameOriginHttpsRedirectHandler()
    request = urllib.request.Request("https://api.example.invalid/start", method="GET")

    with pytest.raises(ExternalAdapterError, match="redirect"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            target,
        )
