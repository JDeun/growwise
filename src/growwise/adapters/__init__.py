from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .data4library import Data4LibraryAdapter
from .http import JsonHttpClient
from .license_filter import filter_licensed, is_commercial_safe, normalize_license
from .overpass import OverpassAdapter

__all__ = [
    "AdapterResult",
    "CachedPayload",
    "Data4LibraryAdapter",
    "ExternalAdapterError",
    "ExternalUnavailable",
    "JsonHttpClient",
    "OverpassAdapter",
    "SQLiteExternalCache",
    "filter_licensed",
    "is_commercial_safe",
    "normalize_license",
]
