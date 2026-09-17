from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

TARGETS = {
    "growwise-windows-x64": ("windows-x86_64", ".exe"),
    "growwise-macos-arm64": ("darwin-aarch64", ".app.tar.gz"),
    "growwise-macos-x64": ("darwin-x86_64", ".app.tar.gz"),
}


def _all_files(input_dir: Path) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for artifact_dir in sorted(path for path in input_dir.iterdir() if path.is_dir()):
        for source in sorted(path for path in artifact_dir.rglob("*") if path.is_file()):
            items.append((artifact_dir.name, source))
    return items


def _destination_names(items: list[tuple[str, Path]]) -> dict[Path, str]:
    counts = Counter(source.name for _, source in items)
    names: dict[Path, str] = {}
    for artifact_name, source in items:
        if counts[source.name] == 1:
            names[source] = source.name
        else:
            names[source] = f"{artifact_name}-{source.name}"
    return names


def _updater_pair(artifact_dir: Path, suffix: str) -> tuple[Path, Path] | None:
    candidates = [
        path
        for path in artifact_dir.rglob("*")
        if path.is_file() and path.name.endswith(suffix)
    ]
    pairs = [(path, Path(f"{path}.sig")) for path in candidates if Path(f"{path}.sig").is_file()]
    if not pairs:
        return None
    if len(pairs) != 1:
        raise RuntimeError(
            f"{artifact_dir.name}: expected exactly one updater bundle, found {len(pairs)}"
        )
    return pairs[0]



def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(output_dir: Path) -> Path:
    output = output_dir / "SHA256SUMS"
    lines = [
        f"{_sha256(path)}  {path.name}"
        for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != output.name
    ]
    if not lines:
        raise RuntimeError("no release assets are available for checksum generation")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output

def prepare(input_dir: Path, output_dir: Path, tag: str, repository: str) -> Path | None:
    if not input_dir.is_dir():
        raise RuntimeError(f"artifact input directory does not exist: {input_dir}")
    if not tag.startswith("v") or not tag[1:]:
        raise RuntimeError("release tag must start with v")
    if repository.count("/") != 1:
        raise RuntimeError("repository must be in owner/name form")

    output_dir.mkdir(parents=True, exist_ok=True)
    items = _all_files(input_dir)
    if not items:
        raise RuntimeError("no package artifacts were downloaded")

    destination_names = _destination_names(items)
    for _, source in items:
        shutil.copy2(source, output_dir / destination_names[source])

    platforms: dict[str, dict[str, str]] = {}
    updater_artifacts_present = False
    missing: list[str] = []

    for artifact_name, (target, suffix) in TARGETS.items():
        artifact_dir = input_dir / artifact_name
        if not artifact_dir.is_dir():
            raise RuntimeError(f"missing package artifact directory: {artifact_name}")
        pair = _updater_pair(artifact_dir, suffix)
        if pair is None:
            missing.append(artifact_name)
            continue

        updater_artifacts_present = True
        bundle, signature_file = pair
        signature = signature_file.read_text(encoding="utf-8").strip()
        if not signature:
            raise RuntimeError(f"{signature_file}: updater signature is empty")
        asset_name = destination_names[bundle]
        platforms[target] = {
            "signature": signature,
            "url": f"https://github.com/{repository}/releases/download/{tag}/{asset_name}",
        }

    if updater_artifacts_present and missing:
        raise RuntimeError(
            "partial updater artifact set; missing signed bundles for: " + ", ".join(missing)
        )

    if not updater_artifacts_present:
        _write_checksums(output_dir)
        return None

    manifest = {
        "version": tag.removeprefix("v"),
        "notes": "",
        "platforms": platforms,
    }
    output = output_dir / "latest.json"
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_checksums(output_dir)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize GrowWise release assets and generate Tauri latest.json when signed "
            "updater bundles exist."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repository", required=True)
    args = parser.parse_args()

    try:
        manifest = prepare(args.input_dir, args.output_dir, args.tag, args.repository)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"release asset preparation failed: {error}")
        return 1

    if manifest:
        print(f"prepared release assets with updater manifest: {manifest}")
    else:
        print("prepared release assets without updater manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
