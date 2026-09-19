from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

_FORBIDDEN = (
    re.compile(r"affero|\bagpl(?:[- v]?\d)?\b", re.IGNORECASE),
    re.compile(r"(?<!l)\bgpl[- v]?(?:2|3)(?:\.0)?\b", re.IGNORECASE),
    re.compile(r"gnu general public license", re.IGNORECASE),
    re.compile(r"server side public|\bsspl\b", re.IGNORECASE),
    re.compile(r"business source|\bbsl[- ]?1\.1\b", re.IGNORECASE),
    re.compile(r"commons clause", re.IGNORECASE),
    re.compile(r"elastic license", re.IGNORECASE),
    re.compile(r"non[- ]?commercial", re.IGNORECASE),
)


def _node_lock(payload: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    for path, package in (payload.get("packages") or {}).items():
        if not path:
            continue
        license_value = package.get("license")
        if not license_value:
            continue
        name = package.get("name") or path.removeprefix("node_modules/")
        yield str(name), str(package.get("version") or "?"), str(license_value)


def _python(payload: Any) -> Iterable[tuple[str, str, str]]:
    if not isinstance(payload, list):
        raise ValueError("pip-licenses JSON must be a list")
    for package in payload:
        if not isinstance(package, dict):
            continue
        license_value = package.get("License") or package.get("license")
        if not license_value:
            continue
        yield (
            str(package.get("Name") or package.get("name") or "?"),
            str(package.get("Version") or package.get("version") or "?"),
            str(license_value),
        )


def _cargo(payload: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    for package in payload.get("packages") or []:
        license_value = package.get("license")
        if not license_value:
            continue
        yield (\n            str(package.get("name") or "?"),\n            str(package.get("version") or "?"),\n            str(license_value),\n        )


def _packages(ecosystem: str, payload: Any) -> Iterable[tuple[str, str, str]]:
    if ecosystem == "node-lock":
        if not isinstance(payload, dict):
            raise ValueError("package-lock JSON must be an object")
        return _node_lock(payload)
    if ecosystem == "python":
        return _python(payload)
    if ecosystem == "cargo":
        if not isinstance(payload, dict):
            raise ValueError("cargo metadata JSON must be an object")
        return _cargo(payload)
    raise ValueError(f"unsupported ecosystem: {ecosystem}")


def main() -> int:
    parser = argparse.ArgumentParser(\n        description="Fail CI on licenses forbidden by GrowWise policy."\n    )
    parser.add_argument("--ecosystem", choices=("node-lock", "python", "cargo"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    checked = 0
    violations: list[tuple[str, str, str]] = []
    for name, version, license_value in _packages(args.ecosystem, payload):
        checked += 1
        if any(pattern.search(license_value) for pattern in _FORBIDDEN):
            violations.append((name, version, license_value))

    if violations:
        for name, version, license_value in violations:
            print(f"FORBIDDEN LICENSE: {name} {version}: {license_value}")
        print(
            "A dependency with a strong-copyleft, source-available, or non-commercial license "
            "entered the dependency graph. Review and explicitly replace or relicense it."
        )
        return 1

    print(f"License policy passed for {checked} {args.ecosystem} packages with declared licenses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
