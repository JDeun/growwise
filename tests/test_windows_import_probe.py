from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/probe_windows_imports.py"
spec = importlib.util.spec_from_file_location("windows_import_probe", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_dumpbin_imports_preserve_exact_dll_and_entrypoint_names() -> None:
    output = """
  Section contains the following imports:
    KERNEL32.dll
             140008000 Import Address Table
             140009000 Import Name Table
                     0 time date stamp
                     0 Index of first forwarder reference
                         31C GetModuleHandleW
                         123 GetProcAddress
    api-ms-win-crt-runtime-l1-1-0.dll
                         17 _initterm
                         A0 _CxxThrowException
  Summary
        1000 .data
    """
    assert probe.parse_imports(output) == {
        "KERNEL32.dll": ["GetModuleHandleW", "GetProcAddress"],
        "api-ms-win-crt-runtime-l1-1-0.dll": ["_initterm", "_CxxThrowException"],
    }


def test_unrecognized_dumpbin_output_fails_instead_of_claiming_no_missing_exports() -> None:
    with pytest.raises(RuntimeError, match="No DLL imports"):
        probe.parse_imports("fatal error LNK1107: invalid or corrupt file")
