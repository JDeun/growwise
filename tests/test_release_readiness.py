from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/check_release_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_release_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PUBLIC_KEY = base64.b64encode(b"untrusted comment: synthetic public fixture\n" +
                              base64.b64encode(b"Ed" + bytes(range(40)))).decode()


def test_pr_metadata_check_accepts_matching_versions() -> None:
    MODULE.check(None, None)


def test_prerelease_tag_does_not_require_production_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPLE_CERTIFICATE", raising=False)
    MODULE.check("v0.1.0-alpha.0", "macos")


def test_stable_tag_requires_explicit_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_load_versions",
        lambda: {"package": "1.0.0", "cargo": "1.0.0", "tauri": "1.0.0"},
    )

    with pytest.raises(RuntimeError, match="requires --platform"):
        MODULE.check("v1.0.0", None)


def test_stable_macos_requires_signing_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_load_versions",
        lambda: {"package": "1.0.0", "cargo": "1.0.0", "tauri": "1.0.0"},
    )
    for name in (
        "APPLE_CERTIFICATE",
        "APPLE_CERTIFICATE_PASSWORD",
        "KEYCHAIN_PASSWORD",
        "APPLE_ID",
        "APPLE_PASSWORD",
        "APPLE_TEAM_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match="macOS signing"):
        MODULE.check("v1.0.0", "macos")


def test_stable_windows_accepts_complete_signing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        MODULE,
        "_load_versions",
        lambda: {"package": "1.0.0", "cargo": "1.0.0", "tauri": "1.0.0"},
    )
    for name in (
        "WINDOWS_CERTIFICATE",
        "WINDOWS_CERTIFICATE_PASSWORD",
        "WINDOWS_TIMESTAMP_URL",
    ):
        monkeypatch.setenv(name, "configured")

    monkeypatch.setattr(MODULE, "_check_updater_config", lambda: True)
    monkeypatch.setenv("TAURI_SIGNING_PRIVATE_KEY", "synthetic-signing-presence-only")
    MODULE.check("v1.0.0", "windows")


def test_stable_updater_requires_private_signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        MODULE,
        "_load_versions",
        lambda: {"package": "1.0.0", "cargo": "1.0.0", "tauri": "1.0.0"},
    )
    monkeypatch.setattr(MODULE, "_check_updater_config", lambda: True)
    for name in (
        "WINDOWS_CERTIFICATE",
        "WINDOWS_CERTIFICATE_PASSWORD",
        "WINDOWS_TIMESTAMP_URL",
    ):
        monkeypatch.setenv(name, "configured")
    monkeypatch.delenv("TAURI_SIGNING_PRIVATE_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Tauri updater signing"):
        MODULE.check("v1.0.0", "windows")


def test_updater_config_requires_https_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    config = tmp_path / "tauri.release.conf.json"
    config.write_text(
        json.dumps(
            {
                "build": {"features": ["updater"]},
                "bundle": {"createUpdaterArtifacts": True},
                "plugins": {
                    "updater": {
                        "pubkey": PUBLIC_KEY,
                        "requireSignedVersion": True,
                        "endpoints": ["http://example.test/latest.json"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(MODULE, "RELEASE_CONFIG", config)

    with pytest.raises(RuntimeError, match="HTTPS"):
        MODULE._check_updater_config()


@pytest.mark.parametrize("version", ["1.0.0", "1.0.0+windows-x64"])
def test_stable_signed_platform_cannot_ship_without_updater_activation(monkeypatch, version):
    monkeypatch.setattr(MODULE, "_load_versions", lambda: {"package": version})
    monkeypatch.setattr(MODULE, "_check_updater_config", lambda: False)
    for name in ("WINDOWS_CERTIFICATE", "WINDOWS_CERTIFICATE_PASSWORD", "WINDOWS_TIMESTAMP_URL"):
        monkeypatch.setenv(name, "synthetic presence only")
    with pytest.raises(RuntimeError, match="activated updater trust root"):
        MODULE.check("v" + version, "windows")


@pytest.mark.parametrize("version,stable", [("1.0.0", True), ("1.0.0+build-x64", True),
    ("1.0.0-beta.1+build-x64", False)])
def test_stability_uses_prerelease_part_not_build_metadata(version, stable):
    assert MODULE.is_stable_version(version) is stable


@pytest.mark.parametrize("version", ["not-semver", "1.0", "01.0.0", "1.0.0-01"])
def test_invalid_release_versions_are_rejected(version):
    with pytest.raises(RuntimeError, match="SemVer"):
        MODULE.is_stable_version(version)


@pytest.mark.parametrize("key", ["PUBLIC-KEY", "c2VjcmV0IGtleQ==", "/private/key"])
def test_invalid_or_non_public_updater_keys_are_rejected(key):
    with pytest.raises(RuntimeError, match="public key"):
        MODULE.validate_public_key(key)
