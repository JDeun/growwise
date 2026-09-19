from __future__ import annotations

from pathlib import Path

import pytest

from growwise.adapters.base import ExternalUnavailable
from growwise.adapters.cache import SQLiteExternalCache
from growwise.adapters.openlibrary import OpenLibraryAdapter

_REPO = Path(__file__).resolve().parents[1]


def test_open_library_live_adapter_is_default_denied(tmp_path: Path) -> None:
    adapter = OpenLibraryAdapter(
        cache=SQLiteExternalCache(tmp_path / "external-cache.sqlite3")
    )

    with pytest.raises(ExternalUnavailable, match="disabled by GrowWise commercial-use policy"):
        adapter.search_books(query="science")


def test_production_discovery_never_wires_open_library_live_api() -> None:
    discovery_source = (
        _REPO / "src" / "growwise" / "services" / "discovery.py"
    ).read_text(encoding="utf-8")
    config_source = (_REPO / "src" / "growwise" / "config.py").read_text(encoding="utf-8")

    assert "OpenLibraryAdapter" not in discovery_source
    assert "_collect_open_library" not in discovery_source
    assert "openlibrary_endpoint" not in config_source
    assert 'source="open_library"' in discovery_source
    assert 'status="policy_disabled"' in discovery_source


def test_docs_do_not_advertise_open_library_live_api_as_connected() -> None:
    readme = (_REPO / "README.md").read_text(encoding="utf-8")
    integrations = (_REPO / "docs" / "integrations.md").read_text(encoding="utf-8")
    curriculum = (_REPO / "docs" / "curriculum-sources.md").read_text(encoding="utf-8")

    assert "**Open Library / Google Books**" not in readme
    assert "Open Library live API를 production discovery에서 호출하지 않는다" in readme
    assert "Open Library, Google Books, Wikipedia" not in integrations
    assert "live API는 production에서 호출하지 않음" in integrations
    assert "Open Library API" not in curriculum
    assert "offline import only" in curriculum
