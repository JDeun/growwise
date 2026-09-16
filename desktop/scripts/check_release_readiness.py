from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CONFIG = ROOT / "desktop/src-tauri/tauri.release.conf.json"


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


def _load_release_config() -> dict[str, object]:
    if not RELEASE_CONFIG.exists():
        return {}
    payload = json.loads(RELEASE_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("stable release overlay must be a JSON object")
    return payload


def _check_updater_config() -> bool:
    payload = _load_release_config()
    bundle = payload.get("bundle", {})
    if not isinstance(bundle, dict):
        raise RuntimeError("stable release overlay bundle config must be an object")

    enabled = bundle.get("createUpdaterArtifacts", False)
    if enabled is False:
        return False
    if enabled is not True:
        raise RuntimeError("GrowWise updater must use createUpdaterArtifacts=true when enabled")

    plugins = payload.get("plugins", {})
    if not isinstance(plugins, dict):
        raise RuntimeError("stable release overlay plugins config must be an object")
    updater = plugins.get("updater")
    if not isinstance(updater, dict):
        raise RuntimeError("updater artifacts are enabled but plugins.updater is missing")

    pubkey = updater.get("pubkey")
    if not isinstance(pubkey, str) or not pubkey.strip():
        raise RuntimeError("updater artifacts are enabled but updater public key is missing")

    endpoints = updater.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise RuntimeError("updater artifacts are enabled but updater endpoints are missing")
    for endpoint in endpoints:
        if not isinstance(endpoint, str):
            raise RuntimeError("updater endpoints must be strings")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise RuntimeError("updater endpoints must use absolute HTTPS URLs")
    return True


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

    updater_enabled = _check_updater_config()
    version = unique_versions.pop()
    if tag:
        normalized_tag = tag.removeprefix("v")
        if normalized_tag != version:
            raise RuntimeError(f"tag {tag!r} does not match desktop version {version!r}")

        stable = "-" not in version
        if stable:
            if platform is None:
                raise RuntimeError(
                    "stable release preflight requires --platform windows or --platform macos"
                )
            if platform == "macos":
                _check_macos_credentials()
            elif platform == "windows":
                _check_windows_credentials()
            else:
                raise RuntimeError(f"unsupported release platform: {platform}")
            if updater_enabled:
                _require_environment(("TAURI_SIGNING_PRIVATE_KEY",), "Tauri updater signing")

    print(
        "release preflight ok: "
        f"version={version}, tag={tag or 'none'}, platform={platform or 'none'}, "
        f"updater={'enabled' if updater_enabled else 'disabled'}"
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
