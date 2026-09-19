#!/usr/bin/env python3
"""Check official Korean curriculum boards for revisions unknown to GrowWise."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict

from growwise.adapters import OfficialCurriculumUpdateWatcher


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 2 when an unknown official revision candidate is found.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    candidates = OfficialCurriculumUpdateWatcher().check()
    payload = {
        "status": "update_candidate" if candidates else "current",
        "count": len(candidates),
        "candidates": [asdict(candidate) for candidate in candidates],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.strict and candidates:
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
