from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release_assets(assets_dir: Path, metadata_path: Path, tag: str) -> int:
    """Fail closed unless every local asset and its checksum matches the GitHub release."""
    if not assets_dir.is_dir():
        raise RuntimeError(f"missing release asset directory: {assets_dir}")
    files = list(assets_dir.iterdir())
    if not files or any(not path.is_file() for path in files):
        raise RuntimeError("release asset directory must contain only files")

    by_name = {path.name: path for path in files}
    checksum_path = by_name.get("SHA256SUMS")
    if checksum_path is None or len(by_name) < 2:
        raise RuntimeError("missing SHA256SUMS or release payload files")

    expected_manifest = [
        f"{_sha256(by_name[name])}  {name}"
        for name in sorted(by_name)
        if name != "SHA256SUMS"
    ]
    actual_manifest = checksum_path.read_text(encoding="utf-8").splitlines()
    if actual_manifest != expected_manifest:
        raise RuntimeError("SHA256SUMS does not match the prepared release files")

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("tag_name") != tag:
        raise RuntimeError("GitHub release metadata tag mismatch")
    remote_assets = payload.get("assets")
    if not isinstance(remote_assets, list):
        raise RuntimeError("GitHub release metadata has no asset list")
    remote: dict[str, dict] = {}
    for item in remote_assets:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise RuntimeError("GitHub release metadata contains an invalid asset")
        name = item["name"]
        if name in remote:
            raise RuntimeError(f"duplicate GitHub release asset: {name}")
        remote[name] = item

    if set(remote) != set(by_name):
        missing = sorted(set(by_name) - set(remote))
        unexpected = sorted(set(remote) - set(by_name))
        raise RuntimeError(
            f"release asset set mismatch; missing={missing}, unexpected={unexpected}"
        )

    for name, path in by_name.items():
        expected_digest = f"sha256:{_sha256(path)}"
        published_digest = remote[name].get("digest")
        if published_digest != expected_digest:
            raise RuntimeError(
                f"release asset SHA-256 mismatch for {name}: "
                f"published={published_digest!r}, expected={expected_digest}"
            )
    return len(by_name)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify complete GitHub release asset digests")
    parser.add_argument("--assets-dir", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    try:
        count = verify_release_assets(args.assets_dir, args.metadata, args.tag)
    except (OSError, ValueError, UnicodeError, RuntimeError) as error:
        print(f"release asset verification failed: {error}")
        return 1
    print(f"Verified GitHub SHA-256 digests for all {count} release assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
