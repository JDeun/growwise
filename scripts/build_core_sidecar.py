from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "scripts" / "growwise_core_entry.py"
DIST = ROOT / "build" / "core-sidecar"
WORK = ROOT / "build" / "pyinstaller"
TARGET_DIR = ROOT / "desktop" / "src-tauri" / "binaries"
BINARY_NAME = "growwise-core.exe" if os.name == "nt" else "growwise-core"


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

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
        str(DIST),
        "--workpath",
        str(WORK),
        "--specpath",
        str(WORK),
        "--collect-submodules",
        "langchain_ollama",
        "--collect-submodules",
        "langgraph",
        "--collect-submodules",
        "langgraph_checkpoint_sqlite",
        "--collect-submodules",
        "uvicorn",
        str(ENTRY),
    ]
    subprocess.run(command, cwd=ROOT, check=True)

    source = DIST / BINARY_NAME
    if not source.is_file():
        raise FileNotFoundError(f"PyInstaller output not found: {source}")

    target = TARGET_DIR / BINARY_NAME
    shutil.copy2(source, target)
    if os.name != "nt":
        target.chmod(0o755)

    print(target)


if __name__ == "__main__":
    main()
