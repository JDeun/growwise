"""Diagnose native PE loader exports after a failing Windows updater-feature test.

Read the official dumpbin /IMPORTS output; never execute imported functions or change
test results. DLL resolution is explicitly labelled as belonging to this probe process.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import re
import sys
from pathlib import Path


def parse_imports(text: str) -> dict[str, list[str]]:
    imports: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        dll = re.fullmatch(r"\s+([A-Za-z0-9_.-]+\.dll)\s*", line, re.I)
        if dll:
            current = dll[1]
            imports.setdefault(current, [])
            continue
        symbol = re.fullmatch(r"\s+[0-9A-Fa-f]+\s+([A-Za-z_?][^\s]*)\s*", line)
        if current and symbol and symbol[1] not in {"time", "Index", "Import"}:
            imports[current].append(symbol[1])
    if not imports:
        raise RuntimeError("No DLL imports were parsed from dumpbin output")
    return imports


def probe(imports: dict[str, list[str]]) -> list[dict]:
    if sys.platform != "win32":
        raise RuntimeError("Native export probing requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
    kernel.LoadLibraryExW.restype = ctypes.c_void_p
    kernel.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    kernel.GetProcAddress.restype = ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
    kernel.FreeLibrary.argtypes = [ctypes.c_void_p]
    results = []
    for dll, symbols in imports.items():
        module = kernel.LoadLibraryExW(dll, None, 0x1000)  # Default safe search directories.
        if not module:
            results.append(
                {"dll": dll, "load_error": ctypes.get_last_error(), "imported_symbols": symbols}
            )
            continue
        try:
            path = ctypes.create_unicode_buffer(32768)
            if not kernel.GetModuleFileNameW(module, path, len(path)):
                raise ctypes.WinError()
            missing = [
                symbol
                for symbol in symbols
                if not kernel.GetProcAddress(module, symbol.encode("ascii"))
            ]
            results.append(
                {
                    "dll": dll,
                    "probe_process_resolved_path": path.value,
                    "checked_symbol_count": len(symbols),
                    "missing_exports": missing,
                }
            )
        finally:
            kernel.FreeLibrary(module)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    imports = parse_imports(args.imports.read_text(encoding="utf-8-sig", errors="replace"))
    result = {
        "scope": "diagnostic probe process; original cargo test failure remains authoritative",
        "dlls": probe(imports),
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
