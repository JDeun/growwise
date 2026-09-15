"""Commercial-safe license filtering for optional external-enrichment results.

GrowWise is commercial-safe / permissive-license-only. External metadata and
image results must pass this allowlist before they are surfaced: only public
domain, CC0, CC-BY, CC-BY-SA, and permissive software-style licenses qualify.
Anything non-commercial (NC), no-derivatives (ND), copyleft-for-content,
proprietary, missing, or unknown is dropped.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable

# Canonical identifiers that permit commercial reuse with at most attribution
# and share-alike obligations (all attribution-compatible for this project).
_COMMERCIAL_SAFE: frozenset[str] = frozenset(
    {
        "public-domain",
        "cc0",
        "cc-by",
        "cc-by-sa",
        "odbl",
        "mit",
        "bsd",
        "apache-2.0",
        "isc",
        "unlicense",
        "zlib",
        "wtfpl",
        "boost",
    }
)

# Spelled-out phrases collapsed to their short-code tokens before tokenizing.
# Longer / more specific phrases must precede the substrings they contain.
_PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("creative commons", "cc"),
    ("creativecommons", "cc"),
    ("public domain mark", "publicdomain"),
    ("public domain", "publicdomain"),
    ("cc zero", "cc0"),
    ("cc-0", "cc0"),
    ("cc 0", "cc0"),
    ("all rights reserved", "arr"),
    ("non-commercial", "nc"),
    ("non commercial", "nc"),
    ("noncommercial", "nc"),
    ("no derivatives", "nd"),
    ("no derivs", "nd"),
    ("noderivatives", "nd"),
    ("noderivs", "nd"),
    ("share-alike", "sa"),
    ("share alike", "sa"),
    ("sharealike", "sa"),
    ("attribution", "by"),
)

# Tokens that carry no licensing signal and are dropped during normalization.
_IGNORED_TOKENS: frozenset[str] = frozenset(
    {
        "license",
        "licence",
        "licensed",
        "deed",
        "international",
        "unported",
        "generic",
        "universal",
        "the",
        "software",
    }
)

# Non-CC permissive aliases mapped to a canonical commercial-safe identifier.
_PERMISSIVE_ALIASES: dict[str, str] = {
    "mit": "mit",
    "expat": "mit",
    "x11": "mit",
    "bsd": "bsd",
    "apache": "apache-2.0",
    "asl": "apache-2.0",
    "isc": "isc",
    "unlicense": "unlicense",
    "zlib": "zlib",
    "libpng": "zlib",
    "wtfpl": "wtfpl",
    "boost": "boost",
    "bsl": "boost",
    "odbl": "odbl",
    "pddl": "public-domain",
}

_VERSION_RE = re.compile(r"^v?\d+(?:\.\d+)*$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _is_version(token: str) -> bool:
    return bool(_VERSION_RE.match(token))


def normalize_license(raw: str | None) -> str:
    """Reduce a free-form license string to a canonical identifier.

    Handles case, spacing, punctuation, version suffixes, and common spellings
    (``"CC BY 4.0"``, ``"cc-by 4.0"``, ``"Creative Commons Attribution"`` all
    normalize to ``"cc-by"``). Returns ``""`` when nothing meaningful remains.
    """
    if not raw:
        return ""
    text = raw.strip().lower()
    if not text:
        return ""
    for phrase, token in _PHRASE_REPLACEMENTS:
        text = text.replace(phrase, token)
    tokens = [
        token
        for token in _TOKEN_RE.findall(text)
        if token not in _IGNORED_TOKENS and not _is_version(token)
    ]
    if not tokens:
        return ""
    token_set = set(tokens)
    if "cc0" in token_set or "publicdomain" in token_set or "pdm" in token_set:
        return "public-domain"
    if tokens == ["pd"]:
        return "public-domain"
    if "cc" in token_set or {"by", "nc", "nd", "sa"} & token_set:
        parts = ["cc"]
        parts.extend(part for part in ("by", "nc", "nd", "sa") if part in token_set)
        return "-".join(parts)
    joined = "-".join(tokens)
    return _PERMISSIVE_ALIASES.get(joined) or _PERMISSIVE_ALIASES.get(tokens[0]) or joined


def is_commercial_safe(license_id: str) -> bool:
    """Return ``True`` only for permissive / commercial-safe, attribution-OK licenses.

    Non-commercial (NC), no-derivatives (ND), copyleft-for-content, proprietary,
    all-rights-reserved, empty, and unrecognized identifiers all return ``False``.
    """
    return normalize_license(license_id) in _COMMERCIAL_SAFE


def filter_licensed[T](
    items: Iterable[T],
    license_getter: Callable[[T], str | None],
) -> list[T]:
    """Keep only items whose license is commercial-safe, preserving input order.

    ``license_getter`` extracts each item's raw license string; items whose
    license is missing (``None``/empty), non-commercial, or unknown are dropped.
    """
    kept: list[T] = []
    for item in items:
        raw = license_getter(item)
        if raw and is_commercial_safe(raw):
            kept.append(item)
    return kept
