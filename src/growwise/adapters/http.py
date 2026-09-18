from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib import error, parse, request

from .base import ExternalAdapterError


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def validate_public_endpoint(url: str) -> str:
    """Accept encrypted public endpoints plus explicit loopback HTTP for local development."""

    candidate = url.strip()
    parsed = parse.urlsplit(candidate)
    if not candidate or parsed.hostname is None:
        raise ValueError("external endpoint must be an absolute URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("external endpoint must not contain credentials")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if scheme == "https":
        return candidate
    if scheme == "http" and hostname in _LOOPBACK_HOSTS:
        return candidate
    raise ValueError("external endpoint must use HTTPS or loopback HTTP")


class _ValidatedRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> request.Request | None:
        try:
            validate_public_endpoint(newurl)
        except ValueError as exc:
            raise ExternalAdapterError(f"unsafe external redirect: {exc}") from exc
        return super().redirect_request(req, fp, code, msg, headers, newurl)


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
        self._opener = request.build_opener(_ValidatedRedirectHandler())

    def get_json(self, url: str, *, params: Mapping[str, str | int | float]) -> dict[str, Any]:
        query = parse.urlencode(params)
        separator = "&" if "?" in url else "?"
        return self._request_json(f"{url}{separator}{query}")

    def post_form_json(
        self,
        url: str,
        *,
        form: Mapping[str, str],
    ) -> dict[str, Any]:
        body = parse.urlencode(form).encode("utf-8")
        request = request.Request(
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
        request = request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept": "application/json"},
            method="GET",
        )
        return self._open_json(request)

    def _open_json(self, request: request.Request) -> dict[str, Any]:
        try:
            validate_public_endpoint(request.full_url)
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                length = response.headers.get("Content-Length")
                if length is not None and int(length) > self.max_response_bytes:
                    raise ExternalAdapterError("external response exceeds configured size limit")
                raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise ExternalAdapterError("external response exceeds configured size limit")
        except (OSError, error.URLError, ValueError) as exc:
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
