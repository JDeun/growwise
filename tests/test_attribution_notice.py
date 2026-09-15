from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_notice.py"


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_notice", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve annotations by module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator() -> ModuleType:
    return _load_generator()


def test_notice_is_non_empty(generator: ModuleType) -> None:
    output = generator.generate()
    assert output.strip()
    assert output.startswith("# Third-Party Notices")


def test_includes_known_dependencies(generator: ModuleType) -> None:
    names = {pkg.name.casefold() for pkg in generator.collect_packages()}
    for expected in ("pydantic", "fastapi", "langgraph"):
        assert expected in names


def test_project_itself_is_excluded(generator: ModuleType) -> None:
    names = {pkg.name.casefold() for pkg in generator.collect_packages()}
    assert "growwise" not in names


def test_every_entry_has_license_and_version(generator: ModuleType) -> None:
    packages = generator.collect_packages()
    assert packages
    for pkg in packages:
        assert pkg.license
        assert pkg.version


def test_output_is_sorted(generator: ModuleType) -> None:
    packages = generator.collect_packages()
    keys = [pkg.sort_key for pkg in packages]
    assert keys == sorted(keys)


def test_output_is_deterministic(generator: ModuleType) -> None:
    assert generator.generate() == generator.generate()


class _DictMeta(dict):
    """Minimal stand-in for distribution metadata (dict + get_all)."""

    def get_all(self, _key: str) -> list[str] | None:
        return None


class _FakeDist:
    version = "1.2.3"
    metadata = _DictMeta({"Name": "fakepkg"})


def test_license_falls_back_to_unknown_on_empty_metadata(
    generator: ModuleType,
) -> None:
    packages = generator.collect_packages([_FakeDist()])
    assert len(packages) == 1
    assert packages[0].license == "UNKNOWN"
    assert packages[0].homepage == ""
