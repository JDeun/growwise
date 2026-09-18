from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from .base import ExternalAdapterError


def _https_origin(url: str) -> tuple[str, int]:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port or 443
    except ValueError as exc:
        raise ExternalAdapterError("external endpoint URL is invalid") from exc
    if parsed.scheme.casefold() != "https":
        raise ExternalAdapterError("external endpoint must use HTTPS")
    if not parsed.hostname:
        raise ExternalAdapterError("external endpoint must include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ExternalAdapterError("external endpoint must not embed credentials")
    return parsed.hostname.casefold(), port


class _SameOriginHttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        resolved = urllib.parse.urljoin(req.full_url, newurl)
        if _https_origin(resolved) != _https_origin(req.full_url):
            raise ExternalAdapterError("external redirect changed HTTPS origin")
        return super().redirect_request(req, fp, code, msg, headers, resolved)


class JsonHttpClient:
    """Minimal bounded HTTP client for public-data adapters.

    The adapter layer intentionally accepts only explicit public query parameters. Child records,
    observations, and other private GrowWise entities are never passed to this client.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 5_000_000,
        user_agent: str = "GrowWise/0.1 (+https://github.com/JDeun/growwise)",
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.user_agent = user_agent
        self._opener = urllib.request.build_opener(_SameOriginHttpsRedirectHandler())

    def get_json(self, url: str, *, params: Mapping[str, str | int | float]) -> dict[str, Any]:
        _https_origin(url)
        query = urllib.parse.urlencode(params)
        separator = "&" if "?" in url else "?"
        return self._request_json(f"{url}{separator}{query}")

    def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
    ) -> dict[str, Any]:
        _https_origin(url)
        body = urllib.parse.urlencode(form).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": self.user_agent,
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "Accept": "application/json",
            },
            method="POST",
        )
        return self._open_json(request)

    def _request_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            method="GET",
        )
        return self._open_json(request)

    def _open_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > self.max_response_bytes:
                    raise ExternalAdapterError("external response exceeds configured size limit")
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise ExternalAdapterError("external response exceeds configured size limit")
        except (OSError, urllib.error.URLError, ValueError) as exc:
            if isinstance(exc, ExternalAdapterError):
                raise
            raise ExternalAdapterError(f"external request failed: {exc}") from exc

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ExternalAdapterError("external response is not valid UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ExternalAdapterError("external JSON root must be an object")
        return payload
