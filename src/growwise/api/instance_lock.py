from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class DataDirInUse(RuntimeError):
    """Raised when another GrowWise Core already owns the same data directory."""


class DataDirInstanceLock:
    """Cross-process lock that prevents concurrent Core writers for one data directory.

    The lock file is intentionally persistent; ownership is provided by the operating-system lock,
    not by file existence. This avoids stale-lock failures after crashes while still protecting the
    Markdown source of truth and the SQLite projections from multiple desktop/Core processes.
    """

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / ".growwise-core.lock"
        self._handle: BinaryIO | None = None

    def acquire(self) -> DataDirInstanceLock:
        if self._handle is not None:
            return self

        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                self._acquire_windows(handle)
            else:
                self._acquire_posix(handle)
        except Exception:
            handle.close()
            raise

        self._handle = handle
        return self

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return

        try:
            if os.name == "nt":
                self._release_windows(handle)
            else:
                self._release_posix(handle)
        finally:
            handle.close()
            self._handle = None

    def __enter__(self) -> DataDirInstanceLock:
        return self.acquire()

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.release()

    @staticmethod
    def _acquire_windows(handle: BinaryIO) -> None:
        import msvcrt

        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        try:
            # The runtime module exposes these APIs on Windows; non-Windows typeshed stubs do not.
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
        except OSError as exc:
            raise DataDirInUse(
                "another GrowWise Core is already using this data directory"
            ) from exc

    @staticmethod
    def _release_windows(handle: BinaryIO) -> None:
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]

    @staticmethod
    def _acquire_posix(handle: BinaryIO) -> None:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise DataDirInUse(
                "another GrowWise Core is already using this data directory"
            ) from exc

    @staticmethod
    def _release_posix(handle: BinaryIO) -> None:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
