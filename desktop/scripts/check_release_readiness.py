from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_versions() -> dict[str, str]:
    package = json.loads((ROOT / "desktop/package.json").read_text(encoding="utf-8"))
    tauri = json.loads((ROOT / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    with (ROOT / "desktop/src-tauri/Cargo.toml").open("rb") as handle:
        cargo = tomllib.load(handle)
    return {
        "desktop/package.json": package["version"],
        "desktop/src-tauri/tauri.conf.json": tauri["version"],
        "desktop/src-tauri/Cargo.toml": cargo["package"]["version"],
    }


def _require_environment(names: tuple[str, ...], label: str) -> None:
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError(f"{label}: missing required release credentials: {', '.join(missing)}")


def _check_macos_credentials() -> None:
    _require_environment(
        ("APPLE_CERTIFICATE", "APPLE_CERTIFICATE_PASSWORD", "KEYCHAIN_PASSWORD"),
        "macOS signing",
    )
    _require_environment(
        ("APPLE_ID", "APPLE_PASSWORD", "APPLE_TEAM_ID"),
        "macOS notarization",
    )


def _check_windows_credentials() -> None:
    _require_environment(
        (
            "WINDOWS_CERTIFICATE",
            "WINDOWS_CERTIFICATE_PASSWORD",
            "WINDOWS_TIMESTAMP_URL",
        ),
        "Windows signing",
    )


def check(tag: str | None, platform: str | None) -> None:
    versions = _load_versions()
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(f"{path}={version}" for path, version in versions.items())
        raise RuntimeError(f"desktop versions are inconsistent: {details}")

    version = unique_versions.pop()
    if tag:
        normalized_tag = tag.removeprefix("v")
        if normalized_tag != version:
            raise RuntimeError(f"tag {tag!r} does not match desktop version {version!r}")

        stable = "-" not in version
        if stable:
            if platform == "macos":
                _check_macos_credentials()
            elif platform == "windows":
                _check_windows_credentials()
            elif platform:
                raise RuntimeError(f"unsupported release platform: {platform}")

    print(
        "release preflight ok: "
        f"version={version}, tag={tag or 'none'}, platform={platform or 'none'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GrowWise desktop release invariants.")
    parser.add_argument("--tag", default=None, help="Release tag, for example v0.1.0-alpha.0")
    parser.add_argument("--platform", choices=("windows", "macos"), default=None)
    args = parser.parse_args()

    try:
        check(args.tag, args.platform)
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"release preflight failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
