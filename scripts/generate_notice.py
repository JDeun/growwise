#!/usr/bin/env python3
"""Generate a deterministic third-party attribution NOTICE.

The inventory is read from installed distribution metadata via
``importlib.metadata`` (no network access). Output is sorted and stable so it
can be regenerated in CI and diffed. See ``docs/attribution.md`` for the
governing licensing obligations.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from importlib.metadata import Distribution, distributions
from pathlib import Path

# Distributions provided by the project itself are excluded from the inventory.
_SELF_NAMES = frozenset({"growwise"})

_CLASSIFIER_PREFIX = "License :: OSI Approved :: "
# Project-URL labels that identify a canonical homepage, in preference order.
_HOMEPAGE_LABELS = ("homepage", "home", "source", "repository", "source code")

_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, order=True)
class Package:
    """A single third-party dependency entry for the NOTICE."""

    sort_key: tuple[str, str]
    name: str
    version: str
    license: str
    homepage: str


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _resolve_license(dist: Distribution) -> str:
    """Best-effort license identifier from PEP 639 / classifiers / License."""
    meta = dist.metadata
    expression = _clean(meta.get("License-Expression"))
    if expression:
        return expression
    classifiers = [
        line[len(_CLASSIFIER_PREFIX):].strip()
        for line in meta.get_all("Classifier") or []
        if line.startswith(_CLASSIFIER_PREFIX)
    ]
    named = sorted({item for item in classifiers if item})
    if named:
        return " OR ".join(named)
    legacy = _clean(meta.get("License"))
    # A bare token (e.g. "MIT") is useful; full license text is not.
    if legacy and "\n" not in legacy and len(legacy) <= 40:
        return legacy
    return _UNKNOWN


def _resolve_homepage(dist: Distribution) -> str:
    """Prefer the Home-page header, then a labelled Project-URL entry."""
    meta = dist.metadata
    home_page = _clean(meta.get("Home-page"))
    if home_page:
        return home_page
    urls: dict[str, str] = {}
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        label = label.strip().casefold()
        url = url.strip()
        if label and url and label not in urls:
            urls[label] = url
    for label in _HOMEPAGE_LABELS:
        if label in urls:
            return urls[label]
    return ""


def collect_packages(dists: Iterable[Distribution] | None = None) -> list[Package]:
    """Return third-party packages sorted by lowercased name then version."""
    source: Iterable[Distribution] = distributions() if dists is None else dists
    packages: dict[tuple[str, str], Package] = {}
    for dist in source:
        name = _clean(dist.metadata["Name"])
        if not name or name.casefold() in _SELF_NAMES:
            continue
        version = _clean(dist.version)
        key = (name.casefold(), version)
        if key in packages:
            continue
        packages[key] = Package(
            sort_key=key,
            name=name,
            version=version or _UNKNOWN,
            license=_resolve_license(dist),
            homepage=_resolve_homepage(dist),
        )
    return sorted(packages.values())


def render_notice(packages: list[Package]) -> str:
    """Render a deterministic Markdown NOTICE from the collected packages."""
    lines = [
        "# Third-Party Notices",
        "",
        "GrowWise is distributed under the Apache-2.0 license. This project",
        "bundles or depends on the third-party packages listed below. Each",
        "remains under its own license; see the linked homepage for full",
        "terms. Regenerate with `python scripts/generate_notice.py`.",
        "",
        f"Total packages: {len(packages)}",
        "",
        "| Package | Version | License | Homepage |",
        "| --- | --- | --- | --- |",
    ]
    for pkg in packages:
        homepage = f"<{pkg.homepage}>" if pkg.homepage else ""
        lines.append(
            f"| {pkg.name} | {pkg.version} | {pkg.license} | {homepage} |"
        )
    return "\n".join(lines) + "\n"


def generate() -> str:
    """Collect installed packages and render the NOTICE document."""
    return render_notice(collect_packages())


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("THIRD_PARTY_NOTICES.md"),
        help="destination file (default: THIRD_PARTY_NOTICES.md)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the file is up to date instead of writing it",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    content = generate()
    output: Path = args.output
    if args.check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current != content:
            print(f"{output} is out of date; run scripts/generate_notice.py")
            return 1
        print(f"{output} is up to date")
        return 0
    output.write_text(content, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
