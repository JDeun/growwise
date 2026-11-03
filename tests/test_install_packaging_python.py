from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/install_packaging_python.py"
SPEC = importlib.util.spec_from_file_location("install_packaging_python", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_reviewed_packaging_runtime_matches_source_floor_and_security_release():
    import tomllib

    spec = module.reviewed_runtime()
    project = tomllib.loads((SCRIPT.parents[2] / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["requires-python"] == ">=3.12.16"
    assert spec["python_version"] == "3.12.16"
    assert spec["build_release"] == "20261026"
    assert len(spec["archives"]) == 4


def test_installer_verifies_catalog_and_never_changes_global_python_links_or_registry(
    tmp_path,
    monkeypatch,
):
    spec = module.reviewed_runtime()
    catalog = b'{"synthetic_official_catalog_fixture": {}}'
    spec["download_metadata_sha256"] = hashlib.sha256(catalog).hexdigest()
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(tmp_path / "private-python"))
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: io.BytesIO(catalog))
    commands = []

    def run(command, *, check):
        from urllib.parse import unquote, urlsplit
        from urllib.request import url2pathname

        assert check
        commands.append(command)
        uri = command[command.index("--python-downloads-json-url") + 1]
        assert uri.startswith("file:")
        assert Path(url2pathname(unquote(urlsplit(uri).path))).read_bytes() == catalog

    monkeypatch.setattr(module.subprocess, "run", run)
    module.install(spec)
    assert commands[0][:5] == ["uv", "python", "install", "--no-bin", "--no-registry"]
    assert commands[0][-1] == "3.12.16"


@pytest.mark.parametrize("content", [b"tampered", b"x" * (8 * 1024 * 1024 + 1)])
def test_installer_rejects_changed_or_oversized_catalog_before_launch(
    tmp_path, monkeypatch, content
):
    monkeypatch.setenv("UV_PYTHON_INSTALL_DIR", str(tmp_path))
    monkeypatch.setattr(module, "urlopen", lambda url, timeout: io.BytesIO(content))
    monkeypatch.setattr(
        module.subprocess, "run", lambda *args, **kwargs: pytest.fail("must not run")
    )
    with pytest.raises(RuntimeError, match="catalog hash mismatch"):
        module.install(module.reviewed_runtime())


def test_installer_requires_private_directory_before_network(monkeypatch):
    monkeypatch.delenv("UV_PYTHON_INSTALL_DIR", raising=False)
    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: pytest.fail("must not fetch"))
    with pytest.raises(RuntimeError, match="private packaging directory"):
        module.install(module.reviewed_runtime())


def test_installer_rejects_unpinned_source(tmp_path, monkeypatch):
    spec = module.reviewed_runtime()
    spec["download_metadata_url"] = "https://example.invalid/mutable.json"
    path = tmp_path / "provenance.json"
    path.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(module, "SPEC", path)
    with pytest.raises(RuntimeError, match="invalid reviewed"):
        module.reviewed_runtime()
