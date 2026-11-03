"""Preserve verbatim Node/Cargo attribution files from this locked production build.

This is a file/provenance collector, not a legal interpretation. Cargo build-support
dependencies are conservatively retained; dev-only edges and unrelated platforms are excluded.
Reviewed upstream overrides are offline, exact-version/commit/hash checked inputs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ATTRIBUTION_NAME = re.compile(
    r"^(LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE|AUTHORS)([.\-_]|$)", re.I
)
MAX_FILE_BYTES = 4 * 1024 * 1024
SOURCE_EXTENSIONS = {".rs", ".py", ".js", ".ts", ".tsx", ".c", ".h", ".cpp", ".hpp", ".go"}


def _relative(value: str) -> Path:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts or ":" in value:
        raise RuntimeError("unsafe attribution path")
    return Path(*path.parts)


def _component(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9@_.+/-]+", value) or ".." in value:
        raise RuntimeError("unsafe package name/version")
    return value.replace("@", "").replace("/", "__")


def _https(value: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or any(ord(character) < 32 for character in value)
    ):
        raise RuntimeError("attribution source must be a public HTTPS URL")
    return value


def _read(path: Path) -> bytes:
    with path.open("rb") as handle:
        data = handle.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES or not data.strip():
        raise RuntimeError(f"empty/oversized attribution file: {path.name}")
    return data


def _full_terms(data: bytes) -> bool:
    """Reject identifiers/referral-only notices; do not treat SPDX metadata as permission text."""
    text = data.decode("utf-8", errors="replace").casefold()
    return len(data.strip()) >= 200 and any(
        marker in text
        for marker in (
            "permission is hereby granted",
            "redistribution and use",
            "terms and conditions for",
            "permission to use, copy",
            "permission is granted",
            "free and unencumbered",
            "this software is provided",
            "mozilla public license version",
            "creative commons",
            "boost software license",
            "unicode license",
            "community data license agreement",
        )
    )


def _files(root: Path, license_file: str | None = None) -> list[Path]:
    root = root.resolve()
    found = set()
    for directory, children, names in os.walk(root, followlinks=False):
        children[:] = sorted(
            child for child in children if child not in {".git", "target", "node_modules"}
        )
        for name in names:
            if ATTRIBUTION_NAME.match(name) and Path(name).suffix.lower() not in SOURCE_EXTENSIONS:
                path = Path(directory) / name
                if not path.resolve().is_relative_to(root):
                    raise RuntimeError("attribution symlink escapes its package")
                found.add(path)
    if license_file:
        path = root / _relative(license_file)
        if not path.resolve().is_relative_to(root):
            raise RuntimeError("declared license file escapes its package")
        if not path.is_file():
            raise RuntimeError("declared license file is missing")
        found.add(path)
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def _copy(data: bytes, output: Path, relative: Path, **provenance: str) -> dict:
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {
        "path": relative.as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        **provenance,
    }


def _reset(output: Path, category: str) -> None:
    subtree = output / category
    if subtree.exists():
        shutil.rmtree(subtree)
    subtree.mkdir(parents=True)


def _node_package(desktop: Path, name: str, parent: Path) -> Path | None:
    _component(name)
    current = parent
    while current.is_relative_to(desktop):
        candidate = current / "node_modules" / _relative(name) / "package.json"
        if candidate.is_file():
            if not candidate.resolve().is_relative_to((desktop / "node_modules").resolve()):
                raise RuntimeError("production Node package resolves outside node_modules")
            return candidate.parent
        if current == desktop:
            break
        current = current.parent
    return None


def collect_node_licenses(root: Path, output: Path) -> list[dict]:
    desktop = (root / "desktop").resolve()
    package = json.loads((desktop / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((desktop / "package-lock.json").read_text(encoding="utf-8"))["packages"]
    optional_root = package.get("optionalDependencies", {})
    pending = [
        (name, desktop, False)
        for name in package.get("dependencies", {})
        if name not in optional_root
    ]
    pending.extend((name, desktop, True) for name in optional_root)
    seen: set[Path] = set()
    packages = []
    _reset(output, "node")
    while pending:
        name, parent, optional = pending.pop()
        directory = _node_package(desktop, name, parent)
        if directory is None:
            if optional:
                continue
            raise RuntimeError(f"missing installed production Node dependency: {name}")
        if directory in seen:
            continue
        seen.add(directory)
        installed = json.loads((directory / "package.json").read_text(encoding="utf-8"))
        version = installed["version"]
        locked = lock.get(directory.relative_to(desktop).as_posix())
        if (
            not locked
            or locked.get("version") != version
            or installed["name"] != name
            or locked.get("dev") is True
        ):
            raise RuntimeError(f"installed Node package differs from production lock: {name}")
        source_url = _https(locked["resolved"])
        prefix = Path("node") / f"{_component(name)}-{_component(version)}"
        files = []
        full = False
        for source in _files(directory):
            data = _read(source)
            full = full or source.suffix.lower() != ".spdx" and _full_terms(data)
            files.append(
                _copy(
                    data,
                    output,
                    prefix / source.relative_to(directory),
                    source="installed-node-package",
                    source_url=source_url,
                )
            )
        if not full:
            raise RuntimeError(f"no full license text for Node {name}@{version}")
        license_id = installed.get("license", "UNKNOWN")
        packages.append(
            {
                "name": name,
                "version": version,
                "license": license_id,
                "category": "node-runtime",
                "source_url": source_url,
                "files": files,
            }
        )
        optional_dependencies = installed.get("optionalDependencies", {})
        pending.extend(
            (dependency, directory, False)
            for dependency in installed.get("dependencies", {})
            if dependency not in optional_dependencies
        )
        pending.extend((dependency, directory, True) for dependency in optional_dependencies)
        for dependency in installed.get("peerDependencies", {}):
            optional_peer = (
                installed.get("peerDependenciesMeta", {}).get(dependency, {}).get("optional", False)
            )
            pending.append((dependency, directory, optional_peer))
    return sorted(packages, key=lambda row: (row["name"], row["version"]))


def _tool(name: str) -> str:
    executable = shutil.which(name)
    if executable:
        return executable
    fallback = Path.home() / ".cargo" / "bin" / (name + (".exe" if os.name == "nt" else ""))
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError(f"required Rust tool is unavailable: {name}")


def host_target() -> str:
    info = subprocess.check_output([_tool("rustc"), "-vV"], text=True, timeout=30)
    target = os.environ.get("CARGO_BUILD_TARGET") or next(
        (line.removeprefix("host: ") for line in info.splitlines() if line.startswith("host: ")), ""
    )
    if not re.fullmatch(r"[A-Za-z0-9_-]+", target):
        raise RuntimeError("cannot determine a valid native Cargo target")
    return target


def _rust_packages(metadata: dict) -> list[dict]:
    resolve = metadata["resolve"]
    nodes = {node["id"]: node for node in resolve["nodes"]}
    pending = [resolve["root"]]
    seen = set()
    while pending:
        package_id = pending.pop()
        if package_id in seen:
            continue
        seen.add(package_id)
        for dependency in nodes[package_id]["deps"]:
            if any(kind["kind"] != "dev" for kind in dependency["dep_kinds"]):
                pending.append(dependency["pkg"])
    return sorted(
        (
            package
            for package in metadata["packages"]
            if package["id"] in seen and package["id"] != resolve["root"]
        ),
        key=lambda package: (package["name"], package["version"]),
    )


def collect_rust_standard_library(root: Path, output: Path) -> dict:
    compiler = _tool("rustc")
    info = subprocess.check_output([compiler, "-vV"], text=True, cwd=root, timeout=30)
    fields = dict(line.split(": ", 1) for line in info.splitlines() if ": " in line)
    version, revision, host = (fields.get(key, "") for key in ("release", "commit-hash", "host"))
    if (
        not re.fullmatch(r"\d+\.\d+\.\d+", version)
        or not re.fullmatch(r"[0-9a-f]{40}", revision)
        or not re.fullmatch(r"[A-Za-z0-9_-]+", host)
    ):
        raise RuntimeError("cannot identify the exact stable Rust standard-library toolchain")
    sysroot = Path(
        subprocess.check_output(
            [compiler, "--print", "sysroot"], text=True, cwd=root, timeout=30
        ).strip()
    )
    source = sysroot / "share/doc/rust/COPYRIGHT-library.html"
    if not source.is_file():
        raise RuntimeError("installed Rust standard-library COPYRIGHT-library.html is missing")
    data = _read(source)
    if b"Copyright notices for The Rust Standard Library" not in data:
        raise RuntimeError("installed Rust library credits are not the standard-library notice")
    _reset(output, "rust-standard-library")
    # rustc supplies library-only credits separately from the larger compiler COPYRIGHT.html.
    file = _copy(
        data,
        output,
        Path("rust-standard-library") / version / source.name,
        source="installed-rust-standard-library-credits",
        revision=revision,
        source_url=f"https://static.rust-lang.org/dist/rustc-{version}-{host}.tar.xz",
    )
    return {
        "name": "rust-standard-library",
        "version": version,
        "category": "rust-standard-library",
        "revision": revision,
        "source_url": f"https://github.com/rust-lang/rust/tree/{revision}/library",
        "files": [file],
    }


def collect_rust_licenses(
    root: Path,
    output: Path,
    *,
    metadata: dict | None = None,
    target: str | None = None,
    include_standard_library: bool = True,
) -> list[dict]:
    target = target or host_target()
    if metadata is None:
        metadata = json.loads(
            subprocess.check_output(
                [
                    _tool("cargo"),
                    "metadata",
                    "--offline",
                    "--locked",
                    "--format-version",
                    "1",
                    "--filter-platform",
                    target,
                    "--features",
                    "updater",
                    "--manifest-path",
                    str(root / "desktop/src-tauri/Cargo.toml"),
                ],
                text=True,
                timeout=120,
            )
        )
    overrides = root / "assets/licenses/rust-overrides"
    provenance = json.loads((overrides / "provenance.json").read_text(encoding="utf-8"))
    _reset(output, "rust")
    packages = []
    for package in _rust_packages(metadata):
        name, version = package["name"], package["version"]
        directory = Path(package["manifest_path"]).parent.resolve()
        source_url = f"https://crates.io/crates/{_component(name)}/{_component(version)}"
        if package.get("source") not in {
            "registry+https://github.com/rust-lang/crates.io-index",
            "sparse+https://index.crates.io/",
        }:
            raise RuntimeError(
                f"review a pinned source URL for non-registry Rust dependency: {name}"
            )
        prefix = Path("rust") / f"{_component(name)}-{_component(version)}"
        files = []
        full = False
        for source in _files(directory, package.get("license_file")):
            data = _read(source)
            full = full or source.suffix.lower() != ".spdx" and _full_terms(data)
            files.append(
                _copy(
                    data,
                    output,
                    prefix / source.relative_to(directory),
                    source="cargo-source",
                    source_url=source_url,
                )
            )
        entries = [
            entry for entry in provenance if entry["name"] == name and entry["version"] == version
        ]
        if entries:
            vcs = json.loads((directory / ".cargo_vcs_info.json").read_text(encoding="utf-8"))
            for entry in entries:
                if entry["crate_revision"] != vcs["git"]["sha1"]:
                    raise RuntimeError(f"reviewed Rust attribution commit mismatch: {name}")
                if not re.fullmatch(r"[0-9a-f]{40}", entry["revision"]) or (
                    f"/{entry['revision']}/" not in urlparse(entry["source_url"]).path
                ):
                    raise RuntimeError(
                        f"Rust attribution source is not pinned to a full commit: {name}"
                    )
                relative = _relative(entry["file"])
                source = overrides / relative
                if not source.resolve().is_relative_to(overrides.resolve()):
                    raise RuntimeError("Rust attribution override escapes its directory")
                data = _read(source)
                if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    raise RuntimeError(f"reviewed Rust attribution hash mismatch: {name}")
                full = full or _full_terms(data)
                files.append(
                    _copy(
                        data,
                        output,
                        prefix / "upstream" / relative.name,
                        source=entry["kind"],
                        source_url=_https(entry["source_url"]),
                        revision=entry["revision"],
                    )
                )
        if not full:
            raise RuntimeError(
                f"no full license text for Rust {name}@{version}; review a pinned upstream override"
            )
        packages.append(
            {
                "name": name,
                "version": version,
                "license": package.get("license") or "UNKNOWN",
                "category": "rust-runtime",
                "target": target,
                "source_url": source_url,
                "files": files,
            }
        )
    if include_standard_library:
        packages.append(collect_rust_standard_library(root, output))
    return packages
