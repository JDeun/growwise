from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CONFIG = ROOT / "desktop/src-tauri/tauri.release.conf.json"


def is_stable_version(version: str) -> bool:
    match = re.fullmatch(
        r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
        r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?", version,
    )
    if match is None or (match["pre"] and any(
        item.isdigit() and len(item) > 1 and item.startswith("0")
        for item in match["pre"].split(".")
    )):
        raise RuntimeError("desktop version must be a valid SemVer version")
    return match["pre"] is None


def validate_public_key(key: str) -> None:
    try:
        decoded = base64.b64decode(key, validate=True).decode("utf-8")
        lines = decoded.strip().splitlines()
        raw = base64.b64decode(lines[-1], validate=True)
        if len(lines) != 2 or not lines[0].startswith("untrusted comment:") or (
            len(raw) != 42 or raw[:2] != b"Ed"
        ):
            raise ValueError("invalid public key")
    except (ValueError, UnicodeError, IndexError, binascii.Error) as exc:
        raise RuntimeError(
            "updater public key must be a Tauri/minisign public key, not a path or secret key"
        ) from exc


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
    validate_public_key(pubkey)

    endpoints = updater.get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise RuntimeError("updater artifacts are enabled but updater endpoints are missing")
    for endpoint in endpoints:
        if not isinstance(endpoint, str):
            raise RuntimeError("updater endpoints must be strings")
        parsed = urlparse(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.fragment or any(ord(char) < 32 for char in endpoint)):
            raise RuntimeError("updater endpoints must use absolute HTTPS URLs")
    if updater.get("requireSignedVersion") is not True or any(updater.get(key) is True for key in (
        "allowDowngrades", "dangerousInsecureTransportProtocol", "dangerousAcceptInvalidCerts",
        "dangerousAcceptInvalidHostnames",
    )):
        raise RuntimeError(
            "updater must require signed versions and retain TLS/downgrade protection"
        )
    features = payload.get("build", {})
    if not isinstance(features, dict) or "updater" not in features.get("features", []):
        raise RuntimeError("stable updater overlay must enable build.features updater")
    return True


def _check_updater_runtime() -> None:
    lock = json.loads((ROOT / "desktop/package-lock.json").read_text(encoding="utf-8"))
    cli_version = lock.get("packages", {}).get("node_modules/@tauri-apps/cli", {}).get(
        "version", "",
    )
    core = cli_version.split("-", 1)[0].split("+", 1)[0]
    if not re.fullmatch(r"\d+\.\d+\.\d+", core) or tuple(map(int, core.split("."))) < (2, 12, 0):
        raise RuntimeError("Tauri CLI2.12+ is required to bind updater signatures to app versions")
    with (ROOT / "desktop/src-tauri/Cargo.toml").open("rb") as handle:
        cargo = tomllib.load(handle)
    dependency = cargo.get("dependencies", {}).get("tauri-plugin-updater", {})
    if ("dep:tauri-plugin-updater" not in cargo.get("features", {}).get("updater", [])
            or not isinstance(dependency, dict) or dependency.get("optional") is not True):
        raise RuntimeError("native updater Cargo feature/dependency is not wired")
    native = ROOT / "desktop/src-tauri/src/updater_commands.rs"
    shell = (ROOT / "desktop/src-tauri/src/lib.rs").read_text(encoding="utf-8")
    if not native.is_file() or any(command not in shell for command in (
        "app_update_status", "check_app_update", "install_app_update", "updater_commands::register",
    )):
        raise RuntimeError("native updater commands are not registered")


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


def check(tag: str | None, platform: str | None) -> bool:
    versions = _load_versions()
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(f"{path}={version}" for path, version in versions.items())
        raise RuntimeError(f"desktop versions are inconsistent: {details}")

    updater_enabled = _check_updater_config()
    version = unique_versions.pop()
    stable = is_stable_version(version)
    if tag:
        normalized_tag = tag.removeprefix("v")
        if normalized_tag != version:
            raise RuntimeError(f"tag {tag!r} does not match desktop version {version!r}")

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
            if not updater_enabled:
                raise RuntimeError("stable release requires an activated updater trust root")
            _check_updater_runtime()
            _require_environment(("TAURI_SIGNING_PRIVATE_KEY",), "Tauri updater signing")

    print(
        "release preflight ok: "
        f"version={version}, tag={tag or 'none'}, platform={platform or 'none'}, "
        f"updater={'enabled' if updater_enabled else 'disabled'}"
    )
    return bool(tag and stable)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate GrowWise desktop release invariants.")
    parser.add_argument("--tag", default=None, help="Release tag, for example v0.1.0-alpha.0")
    parser.add_argument("--platform", choices=("windows", "macos"), default=None)
    parser.add_argument("--github-output", type=Path, default=None)
    args = parser.parse_args()

    try:
        stable = check(args.tag, args.platform)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                handle.write(f"stable={'true' if stable else 'false'}\n")
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"release preflight failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
