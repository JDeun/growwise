from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "desktop/scripts/collect_bundled_dependency_licenses.py"
)
spec = importlib.util.spec_from_file_location("bundled_dependency_licenses", SCRIPT)
assert spec and spec.loader
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

# Synthetic terms exercise byte preservation and fail-closed collection, not legal interpretation.
TERMS = (
    b"Copyright synthetic contributor.\r\nPermission is hereby granted to use this synthetic "
    b"fixture. Preserve this notice. This software is provided without warranty.\r\n"
) * 3


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def node_project(root: Path) -> None:
    desktop = root / "desktop"
    write_json(
        desktop / "package.json",
        {"dependencies": {"renderer": "1.0.0"}, "devDependencies": {"test-only": "1.0.0"}},
    )
    lock = {}
    for name in ("renderer", "scheduler", "react", "test-only"):
        package: dict[str, Any] = {"name": name, "version": "1.0.0", "license": "MIT"}
        if name == "renderer":
            package.update(
                dependencies={"scheduler": "1.0.0", "missing-optional": "1"},
                peerDependencies={"react": "1.0.0"},
                optionalDependencies={"missing-optional": "1"},
            )
        directory = desktop / "node_modules" / name
        write_json(directory / "package.json", package)
        (directory / "LICENSE").write_bytes(TERMS)
        lock[f"node_modules/{name}"] = {
            "version": "1.0.0",
            "dev": name == "test-only",
            "resolved": f"https://registry.npmjs.org/{name}/-/{name}-1.0.0.tgz",
        }
    write_json(desktop / "package-lock.json", {"packages": lock})


def rust_graph(root: Path) -> dict:
    packages = []
    nodes: list[dict[str, Any]] = []
    for name in ("app", "runtime", "build-support", "dev-only", "unrelated-target"):
        directory = root / "sources" / name
        directory.mkdir(parents=True)
        (directory / "Cargo.toml").write_text("# synthetic Cargo source", encoding="utf-8")
        if name in {"runtime", "build-support"}:
            (directory / "LICENSE").write_bytes(TERMS)
        packages.append(
            {
                "id": name,
                "name": name,
                "version": "1.0.0",
                "license": "MIT",
                "source": "registry+https://github.com/rust-lang/crates.io-index",
                "manifest_path": str(directory / "Cargo.toml"),
                "license_file": None,
            }
        )
        nodes.append({"id": name, "deps": []})
    nodes[0]["deps"] = [
        {"pkg": "runtime", "dep_kinds": [{"kind": None}, {"kind": "dev"}]},
        {"pkg": "build-support", "dep_kinds": [{"kind": "build"}]},
        {"pkg": "dev-only", "dep_kinds": [{"kind": "dev"}]},
    ]
    write_json(root / "assets/licenses/rust-overrides/provenance.json", [])
    return {"packages": packages, "resolve": {"root": "app", "nodes": nodes}}


def test_node_production_closure_includes_peers_preserves_raw_bytes_and_omits_private_paths(
    tmp_path: Path,
) -> None:
    node_project(tmp_path)
    output = tmp_path / "bundle"
    rows = collector.collect_node_licenses(tmp_path, output)
    assert [row["name"] for row in rows] == ["react", "renderer", "scheduler"]
    assert str(tmp_path) not in json.dumps(rows)
    for row in rows:
        file = row["files"][0]
        assert (output / file["path"]).read_bytes() == TERMS
        assert file["sha256"] == hashlib.sha256(TERMS).hexdigest()
        assert file["source"] == "installed-node-package"


def test_spdx_identifier_document_alone_cannot_satisfy_full_license_requirement(
    tmp_path: Path,
) -> None:
    node_project(tmp_path)
    directory = tmp_path / "desktop/node_modules/scheduler"
    (directory / "LICENSE").unlink()
    (directory / "LICENSE.spdx").write_text("SPDX-License-Identifier: MIT\n" * 20)
    with pytest.raises(RuntimeError, match="no full license text"):
        collector.collect_node_licenses(tmp_path, tmp_path / "bundle")


def test_installed_node_version_must_equal_lock(tmp_path: Path) -> None:
    node_project(tmp_path)
    path = tmp_path / "desktop/node_modules/scheduler/package.json"
    package = json.loads(path.read_text())
    package["version"] = "9.0.0"
    write_json(path, package)
    with pytest.raises(RuntimeError, match="differs from production lock"):
        collector.collect_node_licenses(tmp_path, tmp_path / "bundle")


def test_rust_nondev_reachable_graph_is_deterministic_and_preserves_real_notices(
    tmp_path: Path,
) -> None:
    metadata = rust_graph(tmp_path)
    output = tmp_path / "bundle"
    rows = collector.collect_rust_licenses(
        tmp_path, output, metadata=metadata, target="synthetic-host", include_standard_library=False
    )
    assert [row["name"] for row in rows] == ["build-support", "runtime"]
    assert str(tmp_path) not in json.dumps(rows)
    assert rows == collector.collect_rust_licenses(
        tmp_path, output, metadata=metadata, target="synthetic-host", include_standard_library=False
    )
    assert all((output / row["files"][0]["path"]).read_bytes() == TERMS for row in rows)


def test_cargo_metadata_uses_utf8_under_a_legacy_windows_locale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata = rust_graph(tmp_path)
    metadata["packages"][1]["description"] = "ひらがな와 공개 라이선스"
    raw = json.dumps(metadata, ensure_ascii=False).encode("utf-8")

    def cargo_output(args: list[str], **kwargs: object) -> str:
        # Reproduce Windows cp1252 failure unless the collector specifies Cargo's UTF-8 output.
        return raw.decode(str(kwargs.get("encoding", "cp1252")))

    monkeypatch.setattr(collector, "_tool", lambda name: name)
    monkeypatch.setattr(collector.subprocess, "check_output", cargo_output)
    rows = collector.collect_rust_licenses(
        tmp_path, tmp_path / "bundle", target="synthetic-host", include_standard_library=False
    )
    assert [row["name"] for row in rows] == ["build-support", "runtime"]


def test_rust_reviewed_override_requires_matching_version_commit_and_hash(tmp_path: Path) -> None:
    metadata = rust_graph(tmp_path)
    directory = tmp_path / "sources/runtime"
    (directory / "LICENSE").unlink()
    revision = "a" * 40
    write_json(directory / ".cargo_vcs_info.json", {"git": {"sha1": revision}})
    override = tmp_path / "assets/licenses/rust-overrides"
    file = override / "runtime-1.0.0/LICENSE"
    file.parent.mkdir()
    file.write_bytes(TERMS)
    entry = {
        "name": "runtime",
        "version": "1.0.0",
        "file": "runtime-1.0.0/LICENSE",
        "crate_revision": revision,
        "revision": revision,
        "kind": "upstream-attribution",
        "source_url": f"https://raw.githubusercontent.com/example/runtime/{revision}/LICENSE",
        "sha256": hashlib.sha256(TERMS).hexdigest(),
    }
    provenance = override / "provenance.json"
    write_json(provenance, [entry])
    rows = collector.collect_rust_licenses(
        tmp_path,
        tmp_path / "bundle",
        metadata=metadata,
        target="synthetic-host",
        include_standard_library=False,
    )
    assert rows[1]["files"][0]["revision"] == revision
    file.write_bytes(TERMS + b"tampered")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        collector.collect_rust_licenses(
            tmp_path,
            tmp_path / "bundle",
            metadata=metadata,
            target="synthetic-host",
            include_standard_library=False,
        )
    file.write_bytes(TERMS)
    entry["crate_revision"] = "b" * 40
    write_json(provenance, [entry])
    with pytest.raises(RuntimeError, match="commit mismatch"):
        collector.collect_rust_licenses(
            tmp_path,
            tmp_path / "bundle",
            metadata=metadata,
            target="synthetic-host",
            include_standard_library=False,
        )


def test_attribution_symlink_cannot_read_outside_package(tmp_path: Path) -> None:
    directory = tmp_path / "package"
    directory.mkdir()
    private = tmp_path / "private.txt"
    private.write_bytes(TERMS)
    try:
        (directory / "LICENSE").symlink_to(private)
    except OSError:
        pytest.skip("Creating a symlink requires OS support/Windows developer permission")
    with pytest.raises(RuntimeError, match="symlink escapes"):
        collector._files(directory)


def test_source_code_named_copying_is_not_mistaken_for_a_permission_file(tmp_path: Path) -> None:
    directory = tmp_path / "package"
    directory.mkdir()
    (directory / "copying.rs").write_bytes(TERMS)
    assert collector._files(directory) == []


def test_rust_standard_library_credit_bytes_version_and_public_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sysroot = tmp_path / "private-toolchain"
    source = sysroot / "share/doc/rust/COPYRIGHT-library.html"
    source.parent.mkdir(parents=True)
    original = b"<title>Copyright notices for The Rust Standard Library</title>\r\n" + TERMS
    source.write_bytes(original)
    revision = "a" * 40
    monkeypatch.setattr(collector, "_tool", lambda name: "rustc")
    monkeypatch.setattr(
        collector.subprocess,
        "check_output",
        lambda args, **kwargs: (
            f"release: 1.98.1\ncommit-hash: {revision}\nhost: synthetic-host\n"
            if "-vV" in args
            else str(sysroot)
        ),
    )
    output = tmp_path / "bundle"
    row = collector.collect_rust_standard_library(tmp_path, output)
    assert row["version"] == "1.98.1" and row["revision"] == revision
    assert row["category"] == "rust-standard-library"
    assert len(row["files"]) == 1
    assert (output / row["files"][0]["path"]).read_bytes() == original
    assert row["files"][0]["sha256"] == hashlib.sha256(original).hexdigest()
    assert str(tmp_path) not in json.dumps(row)
    source.unlink()
    with pytest.raises(RuntimeError, match="COPYRIGHT-library.html is missing"):
        collector.collect_rust_standard_library(tmp_path, output)
