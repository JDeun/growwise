from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/check_release_readiness.py"
SPEC = importlib.util.spec_from_file_location("check_release_readiness", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


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

    MODULE.check("v1.0.0", "windows")
