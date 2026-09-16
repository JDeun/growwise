from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CONFIG = ROOT / "desktop/src-tauri/tauri.release.conf.json"
CARGO_TOML = ROOT / "desktop/src-tauri/Cargo.toml"
LIB_RS = ROOT / "desktop/src-tauri/src/lib.rs"


def _read_public_key(path: Path) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("updater public key file is empty")
    return key


def _validate_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("updater endpoint must be an absolute HTTPS URL")
    return value


def _release_config(public_key: str, endpoint: str) -> dict[str, object]:
    return {
        "bundle": {"createUpdaterArtifacts": True},
        "plugins": {
            "updater": {
                "pubkey": public_key,
                "endpoints": [endpoint],
                "windows": {"installMode": "passive"},
            }
        },
    }


def _write_release_config(path: Path, public_key: str, endpoint: str) -> None:
    path.write_text(
        json.dumps(_release_config(public_key, _validate_endpoint(endpoint)), indent=2) + "\n",
        encoding="utf-8",
    )


def _patch_cargo(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "tauri-plugin-updater" in text:
        return False

    marker = 'tauri-plugin-dialog = "2"\n'
    if marker in text:
        updated = text.replace(marker, marker + 'tauri-plugin-updater = "2"\n', 1)
    else:
        dependencies = "[dependencies]\n"
        if dependencies not in text:
            raise RuntimeError("Cargo.toml does not contain a [dependencies] section")
        updated = text.replace(
            dependencies,
            dependencies + 'tauri-plugin-updater = "2"\n',
            1,
        )
    path.write_text(updated, encoding="utf-8")
    return True


def _patch_lib(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    updater = ".plugin(tauri_plugin_updater::Builder::new().build())"
    if updater in text:
        return False

    marker = "        .plugin(tauri_plugin_dialog::init())\n"
    if marker not in text:
        raise RuntimeError("lib.rs Tauri builder marker was not found")
    updated = text.replace(marker, marker + f"        {updater}\n", 1)
    path.write_text(updated, encoding="utf-8")
    return True


def _cargo_check() -> None:
    subprocess.run(
        ["cargo", "check", "--manifest-path", str(CARGO_TOML)],
        cwd=ROOT,
        check=True,
    )


def configure(public_key_file: Path, endpoint: str, *, run_cargo: bool = True) -> None:
    public_key = _read_public_key(public_key_file)
    _write_release_config(RELEASE_CONFIG, public_key, endpoint)
    cargo_changed = _patch_cargo(CARGO_TOML)
    lib_changed = _patch_lib(LIB_RS)

    if run_cargo:
        _cargo_check()

    changed = ["desktop/src-tauri/tauri.release.conf.json"]
    if cargo_changed:
        changed.append("desktop/src-tauri/Cargo.toml")
        if run_cargo:
            changed.append("desktop/src-tauri/Cargo.lock")
    if lib_changed:
        changed.append("desktop/src-tauri/src/lib.rs")

    print("GrowWise updater activation files prepared:")
    for item in changed:
        print(f"- {item}")
    print("Next operator-only step: store TAURI_SIGNING_PRIVATE_KEY in GitHub Actions secrets.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Activate GrowWise's Tauri updater after the long-lived signing key is backed up."
        )
    )
    parser.add_argument("--public-key-file", type=Path, required=True)
    parser.add_argument(
        "--endpoint",
        default="https://github.com/JDeun/growwise/releases/latest/download/latest.json",
    )
    parser.add_argument(
        "--skip-cargo",
        action="store_true",
        help="Patch files without running cargo check; intended for tests only.",
    )
    args = parser.parse_args()

    try:
        configure(
            args.public_key_file,
            args.endpoint,
            run_cargo=not args.skip_cargo,
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"updater activation failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
