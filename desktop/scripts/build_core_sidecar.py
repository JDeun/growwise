from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "desktop"
ENTRY = DESKTOP / "scripts" / "core_entry.py"
BINARIES = DESKTOP / "src-tauri" / "binaries"


def binary_name() -> str:
    return "growwise-core.exe" if os.name == "nt" else "growwise-core"


def build(*, clean: bool) -> Path:
    BINARIES.mkdir(parents=True, exist_ok=True)
    target = BINARIES / binary_name()
    if clean and target.exists():
        target.unlink()

    with tempfile.TemporaryDirectory(prefix="growwise-pyinstaller-") as temp_dir:
        temp = Path(temp_dir)
        dist = temp / "dist"
        work = temp / "work"
        spec = temp / "spec"
        command = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--name",
            "growwise-core",
            "--distpath",
            str(dist),
            "--workpath",
            str(work),
            "--specpath",
            str(spec),
            "--collect-all",
            "sqlite_vec",
            str(ENTRY),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        built = dist / binary_name()
        if not built.is_file():
            raise FileNotFoundError(f"PyInstaller output missing: {built}")
        shutil.copy2(built, target)

    if os.name != "nt":
        target.chmod(target.stat().st_mode | 0o111)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the platform-local GrowWise Core executable for Tauri packaging."
    )
    parser.add_argument("--no-clean", action="store_true", help="Keep any existing target first")
    args = parser.parse_args()
    target = build(clean=not args.no_clean)
    print(target)


if __name__ == "__main__":
    main()
