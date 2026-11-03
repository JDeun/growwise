from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/configure_updater.py"
SPEC = importlib.util.spec_from_file_location("configure_updater", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PUBLIC_KEY = base64.b64encode(b"untrusted comment: synthetic public fixture\n" +
                              base64.b64encode(b"Ed" + bytes(range(40)))).decode()


def test_release_config_contains_public_key_and_https_endpoint(tmp_path: Path) -> None:
    path = tmp_path / "tauri.release.conf.json"
    MODULE._write_release_config(
        path,
        PUBLIC_KEY,
        "https://github.com/JDeun/growwise/releases/latest/download/latest.json",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["bundle"]["createUpdaterArtifacts"] is True
    assert payload["plugins"]["updater"]["pubkey"] == PUBLIC_KEY
    assert payload["plugins"]["updater"]["windows"]["installMode"] == "passive"


def test_release_config_rejects_non_https_endpoint(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="HTTPS"):
        MODULE._write_release_config(tmp_path / "config.json", "PUBLIC-KEY", "http://example.test")


def test_configurator_enables_committed_feature_and_rolls_back_on_compile_failure(
    tmp_path, monkeypatch,
):
    public = tmp_path / "key.pub"
    public.write_text(PUBLIC_KEY, encoding="utf-8")
    config = tmp_path / "release.json"
    original = '{"bundle":{"createUpdaterArtifacts":false}}'
    config.write_text(original, encoding="utf-8")
    monkeypatch.setattr(MODULE, "RELEASE_CONFIG", config)
    MODULE.configure(public, "https://example.org/latest.json", run_cargo=False)
    assert json.loads(config.read_text())["build"]["features"] == ["updater"]
    config.write_text(original, encoding="utf-8")
    def failure():
        raise RuntimeError("synthetic compile failure")
    monkeypatch.setattr(MODULE, "_cargo_check", failure)
    with pytest.raises(RuntimeError, match="compile failure"):
        MODULE.configure(public, "https://example.org/latest.json")
    assert config.read_text() == original


@pytest.mark.parametrize("value", ["PUBLIC-KEY", "/private/key", "c2VjcmV0IGtleQ=="])
def test_configurator_rejects_non_public_key_inputs(tmp_path, value):
    path = tmp_path / "key.pub"
    path.write_text(value, encoding="utf-8")
    with pytest.raises(RuntimeError, match="public key"):
        MODULE._read_public_key(path)


def test_read_public_key_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "growwise.key.pub"
    path.write_text(" \n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="empty"):
        MODULE._read_public_key(path)
