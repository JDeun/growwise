"""Copy installed runtime LICENSE/NOTICE texts into Tauri resources without network access."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import sysconfig
from importlib.metadata import Distribution, distribution
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = ROOT / "assets/licenses/python-overrides"
INTERPRETER_NOTICES = ROOT / "assets/licenses/python-standalone"
OUTPUT = ROOT / "desktop/src-tauri/licenses"
DEVELOPMENT_TOOLS = {
    "pytest",
    "pytest-asyncio",
    "ruff",
    "mypy",
    "pre-commit",
    "pip-audit",
    "pip-licenses",
}


def runtime_distributions(lookup=distribution) -> list[Distribution]:
    """Follow active PEP508 requirements, including dependency extras such as uvicorn[standard]."""
    pending: list[tuple[str, set[str]]] = [("growwise", set())]
    active: dict[str, set[str]] = {}
    resolved = {}
    while pending:
        name, extras = pending.pop()
        name = canonicalize_name(name)
        if name in active and extras <= active[name]:
            continue
        active.setdefault(name, set()).update(extras)
        current = lookup(name)
        resolved[name] = current
        for raw in current.requires or []:
            requirement = Requirement(raw)
            if requirement.marker is None or any(
                requirement.marker.evaluate({"extra": extra}) for extra in {"", *active[name]}
            ):
                pending.append((requirement.name, set(requirement.extras)))
    return [resolved[name] for name in sorted(resolved) if name != "growwise"]


def assert_clean_build_environment() -> None:
    from importlib.metadata import distributions

    present = {
        canonicalize_name(dist.metadata["Name"])
        for dist in distributions()
        if dist.metadata["Name"]
    }
    unexpected = sorted(present & DEVELOPMENT_TOOLS)
    if unexpected:
        raise RuntimeError(
            "desktop builds require a clean runtime+desktop-build environment; found: "
            + ", ".join(unexpected)
        )


def _license_file(path: str) -> bool:
    item = PurePosixPath(path.replace("\\", "/"))
    name = item.name.upper()
    return bool(
        re.match(r"^(?:LICENSE|LICENCE|COPYING|COPYRIGHT|NOTICE|AUTHORS)(?:[.\-_]|$)", name)
    ) or any(
        part.endswith(".dist-info")
        and offset + 1 < len(item.parts)
        and item.parts[offset + 1] == "licenses"
        for offset, part in enumerate(item.parts)
    )


def _safe_relative(value: str) -> Path:
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts or ":" in value:
        raise RuntimeError("unsafe license metadata path")
    return Path(*path.parts)


def _copy(source: Path, output: Path, relative: Path, *, source_info: dict) -> dict:
    data = source.read_bytes()
    if not data.strip():
        raise RuntimeError(f"empty license text: {source.name}")
    target = output / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {
        "path": relative.as_posix(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        **source_info,
    }


def _package(dist: Distribution, output: Path, category: str, overrides: list[dict]) -> dict:
    name = canonicalize_name(dist.metadata["Name"])
    version = dist.version
    prefix = Path("python") / f"{name}-{version}"
    files = []
    for record in dist.files or []:
        if _license_file(str(record)):
            relative = _safe_relative(str(record))
            files.append(
                _copy(
                    Path(str(dist.locate_file(record))),
                    output,
                    prefix / relative,
                    source_info={"source": "installed-wheel", "wheel_path": str(record)},
                )
            )
    if not files:
        for entry in overrides:
            if entry["name"] == name and entry["version"] == version:
                relative = _safe_relative(entry["file"])
                source = OVERRIDES / relative
                if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
                    raise RuntimeError(f"reviewed license override hash mismatch: {name}")
                files.append(
                    _copy(
                        source,
                        output,
                        prefix / relative.name,
                        source_info={
                            "source": "reviewed-official-source",
                            "source_url": entry["source_url"],
                            "revision": entry["revision"],
                        },
                    )
                )
    if not files:
        raise RuntimeError(
            f"no full license text for {name}=={version}; review a pinned source override"
        )
    return {
        "name": name,
        "version": version,
        "category": category,
        "source_url": f"https://pypi.org/project/{name}/{version}/",
        "files": files,
    }


def interpreter_components(output: Path) -> dict:
    """Preserve the pinned distributor's native notices, including statically linked code."""
    metadata = json.loads((INTERPRETER_NOTICES / "provenance.json").read_text(encoding="utf-8"))
    build_description = " ".join(sys.version.split())
    if (
        sys.version.split()[0] != metadata["python_version"]
        or metadata["build_date"] not in build_description
    ):
        raise RuntimeError(
            f"interpreter notices require uv-managed Python {metadata['python_version']} "
            f"build {metadata['build_release']}; "
            "review native component notices before changing the packaging interpreter; "
            f"actual interpreter: {build_description}"
        )
    files = []
    for entry in metadata["files"]:
        relative = _safe_relative(entry["file"])
        source = INTERPRETER_NOTICES / relative
        revision = entry["revision"]
        if (
            re.fullmatch(r"[a-f0-9]{40}", revision) is None
            or f"/blob/{revision}/" not in entry["source_url"]
            or hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise RuntimeError("pinned interpreter component license provenance mismatch")
        files.append(
            _copy(
                source,
                output,
                Path("python-native") / relative,
                source_info={
                    "source": "pinned-interpreter-distributor",
                    "source_url": entry["source_url"],
                    "revision": revision,
                },
            )
        )
    if not files:
        raise RuntimeError("interpreter native component license texts are missing")
    return {
        "name": "python-build-standalone-native-components",
        "version": f"{metadata['python_version']}+{metadata['build_release']}",
        "category": "interpreter-native-components",
        "source_url": (
            "https://github.com/astral-sh/python-build-standalone/tree/" + metadata["revision"]
        ),
        "scope": metadata["scope"],
        "files": files,
    }


def generate(
    output: Path = OUTPUT,
    *,
    runtime: list[Distribution] | None = None,
    include_support: bool = True,
    include_ecosystems: bool = True,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    marker = output / ".growwise-license-bundle"
    existing = [item.name for item in output.iterdir() if item.name != "README.md"]
    previous_manifest = output / "manifest.json"
    owned = marker.is_file()
    if not owned and previous_manifest.is_file():
        try:
            owned = json.loads(previous_manifest.read_text(encoding="utf-8")).get("format") == (
                "growwise-runtime-license-bundle"
            )
        except (OSError, ValueError):
            owned = False
    if existing and not owned:
        raise RuntimeError(
            "license output is not an owned generated directory; choose an empty path"
        )
    marker.write_text("growwise-runtime-license-bundle\n", encoding="utf-8")
    # Publish a manifest only after every ecosystem is complete; a failed rebuild must not leave
    # an older valid-looking manifest that hides newly missing license files.
    previous_manifest.unlink(missing_ok=True)
    # Replace only our generated subtree; keep the tracked resource-directory README.
    for folder in ("python", "python-native", "node", "rust"):
        if (output / folder).exists():
            shutil.rmtree(output / folder)
    overrides = json.loads((OVERRIDES / "provenance.json").read_text(encoding="utf-8"))
    source = runtime_distributions() if runtime is None else runtime
    packages = [
        _package(dist, output, "python-runtime", overrides)
        for dist in source
        if canonicalize_name(dist.metadata["Name"]) != "growwise"
    ]
    if include_support:
        # The frozen executable contains PyInstaller bootloader/runtime hooks; preserve their
        # supplied full exception/notice texts without treating build dependencies as app imports.
        packages.extend(
            _package(distribution(name), output, "bootloader-runtime-support", overrides)
            for name in ("pyinstaller", "pyinstaller-hooks-contrib")
        )
        packages.append(interpreter_components(output))
    if include_ecosystems:
        from collect_bundled_dependency_licenses import collect_node_licenses, collect_rust_licenses

        packages.extend(collect_node_licenses(ROOT, output))
        packages.extend(collect_rust_licenses(ROOT, output))
    standard_library = Path(sysconfig.get_path("stdlib"))
    python_license = next(
        (
            path
            for path in (
                standard_library / "LICENSE.txt",
                Path(sys.base_prefix) / "LICENSE.txt",
                standard_library / "LICENSE",
                Path(sys.base_prefix) / "LICENSE",
            )
            if path.is_file()
        ),
        None,
    )
    if python_license is None:
        raise RuntimeError("installed Python interpreter license text is missing")
    extra_files = [
        _copy(
            python_license,
            output,
            Path("CPYTHON-LICENSE.txt"),
            source_info={"source": "installed-python-interpreter"},
        ),
        _copy(
            ROOT / "LICENSE",
            output,
            Path("GROWWISE-LICENSE.txt"),
            source_info={"source": "project-license"},
        ),
    ]
    manifest = {
        "format": "growwise-runtime-license-bundle",
        "format_version": 1,
        "python_version": sys.version.split()[0],
        "included_ecosystems": ["python", "node", "rust"] if include_ecosystems else ["python"],
        "packages": packages,
        "additional_files": extra_files,
    }
    index = [
        "# Bundled runtime license texts",
        "",
        "These are verbatim license/copyright/NOTICE texts, not legal interpretations.",
        "Runtime dependency extras and platform markers follow this build environment.",
        "The bootloader category is separate from application imports.",
        "",
        "[GrowWise license](GROWWISE-LICENSE.txt) · [Python license](CPYTHON-LICENSE.txt)",
        "",
    ]
    for package in packages:
        index.extend([f"## {package['name']} {package['version']} ({package['category']})", ""])
        if package.get("source_url"):
            index.extend([f"Source distribution: {package['source_url']}", ""])
        if package.get("scope"):
            index.extend([package["scope"], ""])
        index.extend(f"- [{Path(item['path']).name}]({item['path']})" for item in package["files"])
        index.append("")
    (output / "INDEX.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def check(output: Path = OUTPUT, *, require_ecosystems: bool = True) -> dict:
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("format") != "growwise-runtime-license-bundle"
        or manifest.get("format_version") != 1
    ):
        raise RuntimeError("unsupported license manifest")
    if any(not package.get("files") for package in manifest["packages"]):
        raise RuntimeError("a bundled dependency is missing full license text")
    if require_ecosystems and (
        set(manifest.get("included_ecosystems", [])) != {"python", "node", "rust"}
        or not {
            "python-runtime",
            "node-runtime",
            "rust-runtime",
            "rust-standard-library",
            "interpreter-native-components",
        }.issubset({package["category"] for package in manifest["packages"]})
    ):
        raise RuntimeError("runtime license bundle is missing an ecosystem")
    if {entry["path"] for entry in manifest["additional_files"]} != {
        "CPYTHON-LICENSE.txt",
        "GROWWISE-LICENSE.txt",
    }:
        raise RuntimeError("project or Python interpreter license is missing")
    for entry in [
        *manifest["additional_files"],
        *(item for package in manifest["packages"] for item in package["files"]),
    ]:
        path = output / _safe_relative(entry["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise RuntimeError(f"bundled license hash mismatch: {entry['path']}")
    current = {
        (canonicalize_name(dist.metadata["Name"]), dist.version) for dist in runtime_distributions()
    }
    bundled = {
        (row["name"], row["version"])
        for row in manifest["packages"]
        if row["category"] == "python-runtime"
    }
    if current != bundled:
        raise RuntimeError("bundled Python license inventory differs from current runtime graph")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = check(args.output) if args.check else generate(args.output)
    print(f"Python license texts verified: {len(manifest['packages'])} package distributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
