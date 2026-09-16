from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/prepare_release_assets.py"
SPEC = importlib.util.spec_from_file_location("prepare_release_assets", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write(path: Path, content: str = "artifact") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_prepare_unsigned_release_copies_installers_without_manifest(tmp_path: Path) -> None:
    source = tmp_path / "dist"
    _write(source / "growwise-windows-x64" / "GrowWise.exe")
    _write(source / "growwise-macos-arm64" / "GrowWise-arm64.dmg")
    _write(source / "growwise-macos-x64" / "GrowWise-x64.dmg")
    output = tmp_path / "release"

    manifest = MODULE.prepare(source, output, "v0.1.0-alpha.0", "JDeun/growwise")

    assert manifest is None
    assert sorted(path.name for path in output.iterdir()) == [
        "GrowWise-arm64.dmg",
        "GrowWise-x64.dmg",
        "GrowWise.exe",
    ]


def test_prepare_signed_release_generates_three_platform_manifest(tmp_path: Path) -> None:
    source = tmp_path / "dist"
    win = _write(source / "growwise-windows-x64" / "GrowWise.exe")
    _write(Path(f"{win}.sig"), "windows-signature")
    arm = _write(source / "growwise-macos-arm64" / "GrowWise.app.tar.gz")
    _write(Path(f"{arm}.sig"), "arm-signature")
    intel = _write(source / "growwise-macos-x64" / "GrowWise.app.tar.gz")
    _write(Path(f"{intel}.sig"), "intel-signature")
    _write(source / "growwise-macos-arm64" / "GrowWise-arm64.dmg")
    _write(source / "growwise-macos-x64" / "GrowWise-x64.dmg")
    output = tmp_path / "release"

    manifest_path = MODULE.prepare(source, output, "v1.2.3", "JDeun/growwise")

    assert manifest_path == output / "latest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == "1.2.3"
    assert set(payload["platforms"]) == {
        "windows-x86_64",
        "darwin-aarch64",
        "darwin-x86_64",
    }
    assert payload["platforms"]["windows-x86_64"]["signature"] == "windows-signature"
    assert payload["platforms"]["darwin-aarch64"]["signature"] == "arm-signature"
    assert payload["platforms"]["darwin-x86_64"]["signature"] == "intel-signature"
    assert (
        "growwise-macos-arm64-GrowWise.app.tar.gz"
        in payload["platforms"]["darwin-aarch64"]["url"]
    )
    assert (
        "growwise-macos-x64-GrowWise.app.tar.gz"
        in payload["platforms"]["darwin-x86_64"]["url"]
    )


def test_prepare_rejects_partial_updater_artifact_set(tmp_path: Path) -> None:
    source = tmp_path / "dist"
    win = _write(source / "growwise-windows-x64" / "GrowWise.exe")
    _write(Path(f"{win}.sig"), "windows-signature")
    _write(source / "growwise-macos-arm64" / "GrowWise-arm64.dmg")
    _write(source / "growwise-macos-x64" / "GrowWise-x64.dmg")

    with pytest.raises(RuntimeError, match="partial updater"):
        MODULE.prepare(source, tmp_path / "release", "v1.2.3", "JDeun/growwise")
