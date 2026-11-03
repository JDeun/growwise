"""Install the reviewed interpreter from the same provenance used for bundled native notices."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.request import urlopen

SPEC = Path(__file__).resolve().parents[2] / "assets/licenses/python-standalone/provenance.json"
MAX_CATALOG_BYTES = 8 * 1024 * 1024


def reviewed_runtime() -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    revision = spec["download_metadata_revision"]
    expected = (
        f"https://raw.githubusercontent.com/astral-sh/uv/{revision}/"
        "crates/uv-python-managed/download-metadata.json"
    )
    if (
        re.fullmatch(r"[a-f0-9]{40}", revision) is None
        or spec["download_metadata_url"] != expected
        or re.fullmatch(r"[a-f0-9]{64}", spec["download_metadata_sha256"]) is None
        or re.fullmatch(r"3\.\d+\.\d+", spec["python_version"]) is None
    ):
        raise RuntimeError("invalid reviewed interpreter provenance")
    return spec


def install(spec: dict) -> None:
    if not os.environ.get("UV_PYTHON_INSTALL_DIR"):
        raise RuntimeError("set UV_PYTHON_INSTALL_DIR to a private packaging directory first")
    # Verify the immutable catalog bytes even when bootstrapping from an older system Python.
    # uv then verifies the platform archive against the SHA-256 in that official catalog.
    with urlopen(spec["download_metadata_url"], timeout=30) as response:
        data = response.read(MAX_CATALOG_BYTES + 1)
    if (
        len(data) > MAX_CATALOG_BYTES
        or hashlib.sha256(data).hexdigest() != spec["download_metadata_sha256"]
    ):
        raise RuntimeError("reviewed interpreter download catalog hash mismatch")
    with tempfile.TemporaryDirectory(prefix="growwise-reviewed-python-") as directory:
        catalog = Path(directory) / "download-metadata.json"
        catalog.write_bytes(data)
        subprocess.run(
            [
                "uv",
                "python",
                "install",
                "--no-bin",
                "--no-registry",
                "--python-downloads-json-url",
                catalog.as_uri(),
                spec["python_version"],
            ],
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-version", action="store_true")
    parser.add_argument("--github-env", type=Path)
    args = parser.parse_args()
    spec = reviewed_runtime()
    if args.print_version:
        print(spec["python_version"])
        return
    if args.github_env and not os.environ.get("UV_PYTHON_INSTALL_DIR"):
        temporary = Path(os.environ.get("RUNNER_TEMP", ""))
        if not temporary.is_absolute() or not temporary.is_dir():
            raise RuntimeError("GitHub runtime installation requires an absolute RUNNER_TEMP")
        os.environ["UV_PYTHON_INSTALL_DIR"] = str(temporary / "growwise-reviewed-python")
    install(spec)
    if args.github_env:
        directory = os.environ["UV_PYTHON_INSTALL_DIR"]
        if "\n" in directory or "\r" in directory:
            raise RuntimeError("invalid private interpreter directory")
        with args.github_env.open("a", encoding="utf-8") as output:
            output.write(f"UV_PYTHON_INSTALL_DIR={directory}\n")
            output.write(f"GROWWISE_PACKAGING_PYTHON={spec['python_version']}\n")
    print(f"Reviewed Python {spec['python_version']} / {spec['build_release']} installed")


if __name__ == "__main__":
    main()
