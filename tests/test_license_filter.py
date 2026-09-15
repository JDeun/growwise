from __future__ import annotations

import pytest

from growwise.adapters import filter_licensed, is_commercial_safe, normalize_license
from growwise.adapters.license_filter import _COMMERCIAL_SAFE

COMMERCIAL_SAFE = [
    "CC0",
    "cc-0",
    "CC Zero",
    "Public Domain",
    "publicdomain",
    "PD",
    "PDM",
    "CC BY",
    "cc-by",
    "CC-BY 4.0",
    "cc-by 4.0",
    "Creative Commons Attribution 4.0 International",
    "CC BY-SA",
    "cc-by-sa 3.0",
    "Creative Commons Attribution-ShareAlike",
    "MIT",
    "MIT License",
    "Expat",
    "BSD",
    "BSD 3-Clause",
    "Apache License 2.0",
    "apache-2.0",
    "ISC",
    "The Unlicense",
    "zlib",
    "ODbL 1.0",
]

NON_SAFE = [
    "CC BY-NC",
    "cc-by-nc-sa 4.0",
    "Creative Commons Attribution-NonCommercial",
    "CC BY-ND",
    "cc-by-nc-nd",
    "Creative Commons Attribution-NoDerivatives",
    "All Rights Reserved",
    "all rights reserved",
    "Proprietary",
    "Copyright",
    "GPL-3.0",
    "AGPL",
    "LGPL-2.1",
    "unknown-gibberish",
    "xyz-123",
    "",
    "   ",
]


@pytest.mark.parametrize("value", COMMERCIAL_SAFE)
def test_commercial_safe_licenses_pass(value: str) -> None:
    assert is_commercial_safe(value) is True


@pytest.mark.parametrize("value", NON_SAFE)
def test_non_safe_licenses_are_rejected(value: str) -> None:
    assert is_commercial_safe(value) is False


def test_none_is_rejected() -> None:
    assert is_commercial_safe(normalize_license(None)) is False
    assert normalize_license(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("CC BY 4.0", "cc-by"),
        ("cc-by 4.0", "cc-by"),
        ("CC-BY", "cc-by"),
        ("Creative Commons Attribution 4.0", "cc-by"),
        ("cc by-sa 3.0", "cc-by-sa"),
        ("Creative Commons Attribution-ShareAlike", "cc-by-sa"),
        ("CC BY-NC-SA 4.0", "cc-by-nc-sa"),
        ("cc-by-nd", "cc-by-nd"),
        ("CC0 1.0 Universal", "public-domain"),
        ("Public Domain", "public-domain"),
        ("MIT License", "mit"),
        ("Apache License 2.0", "apache-2.0"),
        ("All Rights Reserved", "arr"),
        ("", ""),
        ("   ", ""),
    ],
)
def test_normalization_across_spellings(value: str, expected: str) -> None:
    assert normalize_license(value) == expected


def test_normalized_safe_ids_are_all_in_allowlist() -> None:
    for value in COMMERCIAL_SAFE:
        assert normalize_license(value) in _COMMERCIAL_SAFE


def test_filter_licensed_keeps_only_safe_and_preserves_order() -> None:
    items = [
        {"id": 1, "license": "CC BY 4.0"},
        {"id": 2, "license": "CC BY-NC 4.0"},
        {"id": 3, "license": "CC0"},
        {"id": 4, "license": None},
        {"id": 5, "license": "All Rights Reserved"},
        {"id": 6, "license": "Apache License 2.0"},
        {"id": 7, "license": ""},
        {"id": 8, "license": "CC BY-SA 3.0"},
    ]
    kept = filter_licensed(items, license_getter=lambda item: item["license"])
    assert [item["id"] for item in kept] == [1, 3, 6, 8]


def test_filter_licensed_drops_everything_when_license_missing() -> None:
    items = [{"id": 1}, {"id": 2}]
    kept = filter_licensed(items, license_getter=lambda item: item.get("license"))
    assert kept == []


def test_filter_licensed_empty_input() -> None:
    assert filter_licensed([], license_getter=lambda item: "CC0") == []
