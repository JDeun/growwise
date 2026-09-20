from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse


def is_loopback_endpoint(base_url: str) -> bool:
    """Return whether an HTTP(S) model endpoint is confined to the local machine."""

    try:
        parsed = urlparse(base_url.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False

    normalized = parsed.hostname.strip().strip("[]").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def provider_is_loopback(provider: object | None) -> bool:
    if provider is None:
        return False
    base_url = getattr(provider, "base_url", None)
    return isinstance(base_url, str) and is_loopback_endpoint(base_url)
