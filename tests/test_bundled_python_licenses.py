from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/build_license_bundle.py"
SPEC = importlib.util.spec_from_file_location("build_license_bundle", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeDistribution:
    def __init__(self, name, root, *, requires=(), files=(), version="1.0"):
        self.metadata = {"Name": name, "License": "MIT"}
        self.version = version
        self.requires = list(requires)
        self.files = list(files)
        self.root = root

    def locate_file(self, path):
        return self.root / path


def fixture_package(tmp_path, name="synthetic-license", *, with_notice=True):
    prefix = Path(f"{name}-1.0.dist-info/licenses")
    license_path = prefix / "LICENSE"
    (tmp_path / prefix).mkdir(parents=True)
    (tmp_path / license_path).write_bytes(b"MIT License\nCopyright synthetic fixture\n")
    files = [license_path]
    if with_notice:
        notice = prefix / "NOTICE"
        (tmp_path / notice).write_bytes(b"Original upstream NOTICE bytes\r\n")
        files.append(notice)
    return FakeDistribution(name, tmp_path, files=files)


def test_runtime_closure_includes_dependency_extras_without_development_extras(tmp_path):
    lookup = {
        "growwise": FakeDistribution(
            "growwise",
            tmp_path,
            requires=[
                "server[standard]",
                "pytest; extra == 'dev'",
            ],
        ),
        "server": FakeDistribution(
            "server",
            tmp_path,
            requires=[
                "codec; extra == 'standard'",
                "never; python_version < '1.0'",
            ],
        ),
        "codec": FakeDistribution("codec", tmp_path),
    }
    result = MODULE.runtime_distributions(lookup=lookup.__getitem__)
    assert [dist.metadata["Name"] for dist in result] == ["codec", "server"]


def test_full_license_and_notice_are_verbatim_and_hash_checked(tmp_path, monkeypatch):
    package = fixture_package(tmp_path / "installed")
    output = tmp_path / "bundle"
    manifest = MODULE.generate(
        output, runtime=[package], include_support=False, include_ecosystems=False
    )
    files = manifest["packages"][0]["files"]
    assert {Path(row["path"]).name for row in files} == {"LICENSE", "NOTICE"}
    for row in files:
        content = (output / row["path"]).read_bytes()
        assert content == package.locate_file(row["wheel_path"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == row["sha256"]
    monkeypatch.setattr(MODULE, "runtime_distributions", lambda: [package])
    MODULE.check(output, require_ecosystems=False)
    (output / files[0]["path"]).write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        MODULE.check(output, require_ecosystems=False)


def test_license_identifier_alone_cannot_satisfy_packaging(tmp_path):
    package = FakeDistribution("synthetic-missing", tmp_path)
    with pytest.raises(RuntimeError, match="no full license text"):
        MODULE.generate(
            tmp_path / "bundle", runtime=[package], include_support=False, include_ecosystems=False
        )


def test_reviewed_override_requires_exact_version_and_digest(tmp_path, monkeypatch):
    overrides = tmp_path / "overrides"
    overrides.mkdir()
    content = b"Verbatim official synthetic copyright/license fixture\n"
    (overrides / "LICENSE").write_bytes(content)
    entry = {
        "name": "synthetic-missing",
        "version": "1.0",
        "file": "LICENSE",
        "source_url": "https://example.org/commit/LICENSE",
        "revision": "fixed-test-revision",
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    (overrides / "provenance.json").write_text(json.dumps([entry]), encoding="utf-8")
    monkeypatch.setattr(MODULE, "OVERRIDES", overrides)
    package = FakeDistribution("synthetic-missing", tmp_path)
    manifest = MODULE.generate(
        tmp_path / "bundle", runtime=[package], include_support=False, include_ecosystems=False
    )
    row = manifest["packages"][0]["files"][0]
    assert row["source_url"] == entry["source_url"] and row["revision"] == entry["revision"]
    (overrides / "LICENSE").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="override hash mismatch"):
        MODULE.generate(
            tmp_path / "bundle", runtime=[package], include_support=False, include_ecosystems=False
        )
    package.version = "2.0"
    with pytest.raises(RuntimeError, match="no full license text"):
        MODULE.generate(
            tmp_path / "bundle", runtime=[package], include_support=False, include_ecosystems=False
        )


@pytest.mark.parametrize(
    "path", ["../../private/LICENSE", "/private/LICENSE", "C:/private/LICENSE"]
)
def test_metadata_cannot_escape_license_resource_directory(tmp_path, path):
    package = FakeDistribution("unsafe", tmp_path, files=[Path(path)])
    with pytest.raises(RuntimeError, match="unsafe license"):
        MODULE.generate(
            tmp_path / "bundle", runtime=[package], include_support=False, include_ecosystems=False
        )


def test_build_rejects_development_tools_in_shared_environment(monkeypatch):
    monkeypatch.setattr(
        "importlib.metadata.distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "pytest"}),
        ],
    )
    with pytest.raises(RuntimeError, match="clean runtime.*pytest"):
        MODULE.assert_clean_build_environment()


def test_package_resources_and_ci_include_license_verification():
    root = SCRIPT.parents[2]
    config = json.loads((root / "desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    assert "licenses" in config["bundle"]["resources"]
    workflow = (root / ".github/workflows/package.yml").read_text(encoding="utf-8")
    assert "build_license_bundle.py --check" in workflow
    assert "uv sync --locked --no-dev --extra desktop-build" in workflow
    assert "--managed-python --python 3.12.13" in workflow
    assert "UV_PYTHON_INSTALL_DIR: ${{ runner.temp }}/growwise-packaging-python" in workflow
    assert "--python-downloads-json-url https://raw.githubusercontent.com/astral-sh/uv/" in workflow
    assert (
        "901092ee11a89ba287f274e3c6e3a2e18ec2fba2/crates/uv-python/download-metadata.json"
        in workflow
    )


def test_generator_does_not_clear_an_unrelated_existing_output(tmp_path):
    output = tmp_path / "unrelated"
    (output / "python").mkdir(parents=True)
    original = output / "python/private.md"
    original.write_text("synthetic user-owned file", encoding="utf-8")
    with pytest.raises(RuntimeError, match="owned generated directory"):
        MODULE.generate(output, runtime=[], include_support=False, include_ecosystems=False)
    assert original.read_text(encoding="utf-8") == "synthetic user-owned file"


def test_native_interpreter_notices_are_pinned_and_verbatim(tmp_path, monkeypatch):
    metadata = json.loads((MODULE.INTERPRETER_NOTICES / "provenance.json").read_text())
    monkeypatch.setattr(MODULE.sys, "version", "3.12.13 (main, Jun 23 2026, 15:44:24)")
    row = MODULE.interpreter_components(tmp_path)
    assert row["category"] == "interpreter-native-components"
    assert len(row["files"]) >= 8
    assert {"LICENSE.openssl-3.txt", "LICENSE.libffi.txt", "LICENSE.liblzma.txt"} <= {
        Path(item["path"]).name for item in row["files"]
    }
    for item, provenance in zip(row["files"], metadata["files"], strict=True):
        assert (tmp_path / item["path"]).read_bytes() == (
            MODULE.INTERPRETER_NOTICES / provenance["file"]
        ).read_bytes()
        assert item["sha256"] == provenance["sha256"]
        assert f"/blob/{item['revision']}/" in item["source_url"]
    monkeypatch.setattr(MODULE.sys, "version", "3.12.13 (different distributor build)")
    with pytest.raises(RuntimeError, match="build 20260623"):
        MODULE.interpreter_components(tmp_path)


def test_native_interpreter_notice_tampering_fails(tmp_path, monkeypatch):
    source = tmp_path / "reviewed"
    source.mkdir()
    text = b"Verbatim synthetic official interpreter component notice"
    (source / "LICENSE").write_bytes(text)
    metadata = {
        "python_version": "3.12.13",
        "build_date": "Jun 23 2026",
        "files": [
            {
                "file": "LICENSE",
                "revision": "a" * 40,
                "source_url": "https://example.org/blob/" + "a" * 40 + "/LICENSE",
                "sha256": hashlib.sha256(text).hexdigest(),
            }
        ],
    }
    (source / "provenance.json").write_text(json.dumps(metadata))
    monkeypatch.setattr(MODULE, "INTERPRETER_NOTICES", source)
    monkeypatch.setattr(MODULE.sys, "version", "3.12.13 (Jun 23 2026)")
    (source / "LICENSE").write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="provenance mismatch"):
        MODULE.interpreter_components(tmp_path / "bundle")
