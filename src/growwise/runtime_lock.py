from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import BinaryIO, Self


class DataDirectoryLockError(RuntimeError):
    """Raised when another GrowWise Core already owns a data directory."""


class DataDirectoryLock:
    """Hold an OS-backed exclusive lock for one GrowWise data directory.

    The lock is advisory, process-scoped, and released automatically by the OS if the
    process exits unexpectedly. The lock file itself is intentionally persistent; only
    the kernel lock determines ownership.
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._path = self._data_dir / ".core.lock"
        self._file: BinaryIO | None = None

    @property
    def path(self) -> Path:
        return self._path

    def acquire(self) -> Self:
        if self._file is not None:
            return self

        self._data_dir.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+b")
        try:
            if os.name == "nt":
                self._acquire_windows(handle)
            else:
                self._acquire_posix(handle)
            self._write_owner_metadata(handle)
        except BaseException:
            handle.close()
            raise
        self._file = handle
        return self

    def release(self) -> None:
        handle = self._file
        if handle is None:
            return
        try:
            if os.name == "nt":
                self._release_windows(handle)
            else:
                self._release_posix(handle)
        finally:
            handle.close()
            self._file = None

    def __enter__(self) -> Self:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()

    def _write_owner_metadata(self, handle: BinaryIO) -> None:
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n".encode())
        handle.flush()
        os.fsync(handle.fileno())
        handle.seek(0)

    @staticmethod
    def _acquire_posix(handle: BinaryIO) -> None:
        import fcntl

        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise DataDirectoryLockError(
                "another GrowWise Core is already using this data directory"
            ) from exc

    @staticmethod
    def _release_posix(handle: BinaryIO) -> None:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _acquire_windows(handle: BinaryIO) -> None:
        import msvcrt

        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise DataDirectoryLockError(
                "another GrowWise Core is already using this data directory"
            ) from exc

    @staticmethod
    def _release_windows(handle: BinaryIO) -> None:
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
