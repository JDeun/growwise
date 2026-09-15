from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_MANIFEST_NAME = "manifest.json"
_CHUNK_SIZE = 1 << 20

Fetcher = Callable[[], bytes]


class ModelIntegrityError(RuntimeError):
    """Raised when an artifact's contents do not match its expected sha256."""


@dataclass(frozen=True, slots=True)
class ModelArtifact:
    """A downloaded local model file tracked by the registry.

    ``sha256`` is the expected digest recorded at download time; ``verify`` recomputes the
    on-disk digest and compares against it to detect corruption or tampering.
    """

    name: str
    tag: str
    sha256: str
    size: int
    path: Path

    @property
    def key(self) -> str:
        return _artifact_key(self.name, self.tag)


def _artifact_key(name: str, tag: str) -> str:
    return f"{name}@{tag}"


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-._" else "_" for ch in value)


def _sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    """Offline-first registry of downloaded model artifacts with integrity verification.

    The registry owns a ``models_dir`` containing artifact files plus a small JSON manifest.
    Downloads are pluggable: a ``fetcher`` callable supplies the bytes, so tests (and offline
    runs) never touch the network. Every write is atomic (temp file + ``os.replace``) and every
    download is verified against an expected sha256 before it is committed to the manifest.
    """

    def __init__(self, models_dir: Path | str) -> None:
        self._dir = Path(models_dir)
        self._manifest_path = self._dir / _MANIFEST_NAME

    @property
    def models_dir(self) -> Path:
        return self._dir

    def list_artifacts(self) -> list[ModelArtifact]:
        manifest = self._read_manifest()
        return [self._to_artifact(entry) for entry in manifest.values()]

    def get(self, name: str, tag: str) -> ModelArtifact | None:
        entry = self._read_manifest().get(_artifact_key(name, tag))
        return self._to_artifact(entry) if entry is not None else None

    def download(
        self,
        *,
        name: str,
        tag: str,
        sha256: str,
        fetcher: Fetcher,
    ) -> ModelArtifact:
        """Fetch bytes via ``fetcher``, verify sha256, then atomically commit the artifact.

        On a digest mismatch (corruption or tampering) the partial file is deleted and
        ``ModelIntegrityError`` is raised, leaving the registry unchanged. A failure inside
        ``fetcher`` propagates without writing any file.
        """
        expected = sha256.lower()
        data = fetcher()
        actual = _sha256_of_bytes(data)
        if actual != expected:
            raise ModelIntegrityError(
                f"sha256 mismatch for {name}@{tag}: expected {expected}, got {actual}"
            )

        self._dir.mkdir(parents=True, exist_ok=True)
        target = self._artifact_path(name, tag)
        self._atomic_write(target, data)

        artifact = ModelArtifact(
            name=name,
            tag=tag,
            sha256=expected,
            size=len(data),
            path=target,
        )
        self._record(artifact)
        return artifact

    def verify(self, name: str, tag: str) -> bool:
        """Recompute the on-disk sha256 and compare it to the recorded expected digest."""
        artifact = self.get(name, tag)
        if artifact is None:
            raise KeyError(f"unknown artifact {name}@{tag}")
        if not artifact.path.exists():
            raise FileNotFoundError(f"missing artifact file {artifact.path}")
        return _sha256_of_file(artifact.path) == artifact.sha256

    def remove(self, name: str, tag: str) -> bool:
        """Delete the artifact file and its manifest entry. Returns True if it existed."""
        manifest = self._read_manifest()
        entry = manifest.pop(_artifact_key(name, tag), None)
        if entry is None:
            return False
        path = self._dir / str(entry["filename"])
        path.unlink(missing_ok=True)
        self._write_manifest(manifest)
        return True

    def _artifact_path(self, name: str, tag: str) -> Path:
        return self._dir / f"{_slug(name)}-{_slug(tag)}.bin"

    def _to_artifact(self, entry: dict[str, object]) -> ModelArtifact:
        return ModelArtifact(
            name=str(entry["name"]),
            tag=str(entry["tag"]),
            sha256=str(entry["sha256"]),
            size=int(str(entry["size"])),
            path=self._dir / str(entry["filename"]),
        )

    def _record(self, artifact: ModelArtifact) -> None:
        manifest = self._read_manifest()
        manifest[artifact.key] = {
            "name": artifact.name,
            "tag": artifact.tag,
            "sha256": artifact.sha256,
            "size": artifact.size,
            "filename": artifact.path.name,
        }
        self._write_manifest(manifest)

    def _read_manifest(self) -> dict[str, dict[str, object]]:
        if not self._manifest_path.exists():
            return {}
        with self._manifest_path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            return {}
        return loaded

    def _write_manifest(self, manifest: dict[str, dict[str, object]]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
        self._atomic_write(self._manifest_path, payload.encode("utf-8"))

    def _atomic_write(self, target: Path, data: bytes) -> None:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
