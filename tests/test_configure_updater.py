from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/configure_updater.py"
SPEC = importlib.util.spec_from_file_location("configure_updater", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_release_config_contains_public_key_and_https_endpoint(tmp_path: Path) -> None:
    path = tmp_path / "tauri.release.conf.json"
    MODULE._write_release_config(
        path,
        "PUBLIC-KEY",
        "https://github.com/JDeun/growwise/releases/latest/download/latest.json",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["bundle"]["createUpdaterArtifacts"] is True
    assert payload["plugins"]["updater"]["pubkey"] == "PUBLIC-KEY"
    assert payload["plugins"]["updater"]["windows"]["installMode"] == "passive"


def test_release_config_rejects_non_https_endpoint(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="HTTPS"):
        MODULE._write_release_config(tmp_path / "config.json", "PUBLIC-KEY", "http://example.test")


def test_patch_cargo_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "Cargo.toml"
    path.write_text(
        '[dependencies]\ntauri = { version = "2", features = [] }\ntauri-plugin-dialog = "2"\n',
        encoding="utf-8",
    )

    assert MODULE._patch_cargo(path) is True
    assert MODULE._patch_cargo(path) is False
    assert path.read_text(encoding="utf-8").count('tauri-plugin-updater = "2"') == 1


def test_patch_lib_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "lib.rs"
    path.write_text(
        "pub fn run() {\n"
        "    tauri::Builder::default()\n"
        "        .plugin(tauri_plugin_dialog::init())\n"
        "        .run(tauri::generate_context!())\n"
        "        .unwrap();\n"
        "}\n",
        encoding="utf-8",
    )

    assert MODULE._patch_lib(path) is True
    assert MODULE._patch_lib(path) is False
    assert path.read_text(encoding="utf-8").count("tauri_plugin_updater::Builder") == 1


def test_read_public_key_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "growwise.key.pub"
    path.write_text(" \n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        MODULE._read_public_key(path)
