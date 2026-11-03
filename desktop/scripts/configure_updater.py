from __future__ import annotations

import argparse
import base64
import binascii
import json
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RELEASE_CONFIG = ROOT / "desktop/src-tauri/tauri.release.conf.json"
CARGO_TOML = ROOT / "desktop/src-tauri/Cargo.toml"


def _read_public_key(path: Path) -> str:
    key = path.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("updater public key file is empty")
    try:
        lines = base64.b64decode(key, validate=True).decode("utf-8").strip().splitlines()
        raw = base64.b64decode(lines[-1], validate=True)
        if len(lines) != 2 or not lines[0].startswith("untrusted comment:") or (
            len(raw) != 42 or raw[:2] != b"Ed"
        ):
            raise ValueError("invalid public key")
    except (ValueError, UnicodeError, IndexError, binascii.Error) as exc:
        raise RuntimeError(
            "provide the generated Tauri public key, not a path or private key"
        ) from exc
    return key


def _validate_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    parsed = urlparse(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or any(ord(char) < 32 for char in value)):
        raise RuntimeError("updater endpoint must be an absolute HTTPS URL")
    return value


def _release_config(public_key: str, endpoint: str) -> dict[str, object]:
    return {
        "build": {"features": ["updater"]},
        "bundle": {"createUpdaterArtifacts": True},
        "plugins": {
            "updater": {
                "pubkey": public_key,
                "requireSignedVersion": True,
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


def _cargo_check() -> None:
    subprocess.run(
        ["cargo", "check", "--locked", "--features", "updater", "--manifest-path", str(CARGO_TOML)],
        cwd=ROOT,
        check=True,
    )


def configure(public_key_file: Path, endpoint: str, *, run_cargo: bool = True) -> None:
    public_key = _read_public_key(public_key_file)
    with CARGO_TOML.open("rb") as handle:
        cargo = tomllib.load(handle)
    if "dep:tauri-plugin-updater" not in cargo.get("features", {}).get("updater", []):
        raise RuntimeError("the native updater feature must be present before activation")
    previous = RELEASE_CONFIG.read_bytes() if RELEASE_CONFIG.exists() else None
    _write_release_config(RELEASE_CONFIG, public_key, endpoint)
    try:
        if run_cargo:
            _cargo_check()
    except Exception:
        if previous is None:
            RELEASE_CONFIG.unlink(missing_ok=True)
        else:
            RELEASE_CONFIG.write_bytes(previous)
        raise

    print("GrowWise updater activation files prepared:")
    print("- desktop/src-tauri/tauri.release.conf.json")
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
