from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/verify_release_asset_digests.py"
SPEC = importlib.util.spec_from_file_location("verify_release_asset_digests", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TAG = "v0.1.0-alpha.1"


def _release(tmp_path: Path) -> tuple[Path, Path, dict]:
    root = tmp_path / "release-assets"
    root.mkdir()
    (root / "GrowWise.exe").write_bytes(b"windows installer content")
    (root / "GrowWise.dmg").write_bytes(b"macOS installer content")
    (root / "sbom.spdx.json").write_text('{"spdxVersion":"SPDX-2.3"}', encoding="utf-8")
    filenames = sorted(path.name for path in root.iterdir())
    checksums = "\n".join(
        f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}"
        for name in filenames
    ) + "\n"
    (root / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    payload = {
        "tag_name": TAG,
        "draft": True,
        "assets": [
            {
                "name": path.name,
                "state": "uploaded",
                "digest": f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
            }
            for path in sorted(root.iterdir())
        ],
    }
    metadata = tmp_path / "release-metadata.json"
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    return root, metadata, payload


@pytest.mark.parametrize("draft", [True, False])
def test_verifier_accepts_complete_draft_or_published_release(tmp_path: Path, draft: bool):
    root, metadata, payload = _release(tmp_path)
    payload["draft"] = draft
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    assert MODULE.verify_release_assets(root, metadata, TAG) == 4


def test_verifier_rejects_corrupted_installer(tmp_path: Path):
    root, metadata, _ = _release(tmp_path)
    (root / "GrowWise.exe").write_bytes(b"unexpected build")
    with pytest.raises(RuntimeError, match="SHA256SUMS"):
        MODULE.verify_release_assets(root, metadata, TAG)


def test_verifier_rejects_remote_digest_mismatch(tmp_path: Path):
    root, metadata, payload = _release(tmp_path)
    payload["assets"][0]["digest"] = "sha256:" + "0" * 64
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        MODULE.verify_release_assets(root, metadata, TAG)


@pytest.mark.parametrize("value", [None, "sha256:", "sha256:" + "a" * 64])
def test_verifier_requires_exact_remote_digest(tmp_path: Path, value: str | None):
    root, metadata, payload = _release(tmp_path)
    payload["assets"][1]["digest"] = value
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        MODULE.verify_release_assets(root, metadata, TAG)


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate"])
def test_verifier_rejects_incomplete_or_unexpected_asset_set(tmp_path: Path, mutation: str):
    root, metadata, payload = _release(tmp_path)
    if mutation == "missing":
        payload["assets"].pop()
    elif mutation == "extra":
        payload["assets"].append({"name": "untrusted.exe", "digest": "sha256:deadbeef"})
    else:
        payload["assets"].append(payload["assets"][0].copy())
    metadata.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RuntimeError, match="asset set mismatch|duplicate"):
        MODULE.verify_release_assets(root, metadata, TAG)


def test_verifier_rejects_wrong_tag(tmp_path: Path):
    root, metadata, _ = _release(tmp_path)
    with pytest.raises(RuntimeError, match="tag mismatch"):
        MODULE.verify_release_assets(root, metadata, "v9.9.9")


def test_verifier_rejects_checksum_manifest_tampering(tmp_path: Path):
    root, metadata, _ = _release(tmp_path)
    with (root / "SHA256SUMS").open("a", encoding="utf-8") as handle:
        handle.write("0" * 64 + "  bogus.bin\n")
    with pytest.raises(RuntimeError, match="SHA256SUMS"):
        MODULE.verify_release_assets(root, metadata, TAG)


def test_verifier_rejects_missing_checksum_manifest(tmp_path: Path):
    root, metadata, _ = _release(tmp_path)
    (root / "SHA256SUMS").unlink()
    with pytest.raises(RuntimeError, match="missing SHA256SUMS"):
        MODULE.verify_release_assets(root, metadata, TAG)


def test_workflow_stages_and_verifies_before_publishing():
    workflow = (
        Path(__file__).resolve().parents[1] / ".github/workflows/package.yml"
    ).read_text(encoding="utf-8")
    stage = workflow.index("--generate-notes --draft --verify-tag")
    check = workflow.index("verify_release_asset_digests.py")
    publish = workflow.index('gh release edit "$GITHUB_REF_NAME" --draft=false')
    assert stage < check < publish
    assert 'gh release upload "$GITHUB_REF_NAME" "$file" --clobber' not in workflow
