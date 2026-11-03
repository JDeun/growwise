"""Stop an authenticated desktop Core when its owning desktop process disappears."""

from __future__ import annotations

import ctypes
import os
import threading
from collections.abc import Callable

_PARENT_ENV = "GROWWISE_PARENT_PID"
_POLL_SECONDS = 0.25


def _posix_parent_alive(parent_pid: int) -> Callable[[], bool]:
    # A PyInstaller one-file bootloader can be the immediate parent instead of the Rust host.
    original_parent = os.getppid()

    def alive() -> bool:
        if os.getppid() != original_parent:
            return False
        try:
            os.kill(parent_pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    return alive


def _windows_parent_monitor(parent_pid: int) -> tuple[Callable[[], bool], Callable[[], None]]:
    # Windows os.kill(pid, 0) can terminate a process; retain a synchronization handle instead.
    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        raise RuntimeError("Windows process monitoring is unavailable")
    kernel32 = loader("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    handles: list[int] = []
    # A one-file bootloader can die during a Core restart while the Rust host remains alive.
    # Retain both original process handles so PID reuse and bootloader death cannot hide an orphan.
    for pid in dict.fromkeys((parent_pid, os.getppid())):
        handle = kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
        if not handle:
            last_error = getattr(ctypes, "get_last_error", None)
            already_exited = last_error is not None and last_error() == 87
            for opened in handles:
                kernel32.CloseHandle(opened)
            if already_exited:
                return lambda: False, lambda: None
            raise RuntimeError("cannot monitor the desktop parent process")
        handles.append(handle)

    def alive() -> bool:
        return all(kernel32.WaitForSingleObject(handle, 0) == 258 for handle in handles)

    def close() -> None:
        for handle in handles:
            kernel32.CloseHandle(handle)

    return alive, close


def _monitor(
    stop: threading.Event,
    alive: Callable[[], bool],
    close: Callable[[], None],
) -> None:
    try:
        while not stop.wait(_POLL_SECONDS):
            if not alive():
                # Shutdown hooks cannot be relied on after an abrupt desktop exit. Existing atomic
                # writes/journals recover interrupted work; the OS releases this Core's data lock.
                os._exit(0)
    finally:
        close()


def start_parent_watchdog() -> threading.Event | None:
    raw = os.environ.get(_PARENT_ENV)
    if raw is None:
        return None
    try:
        parent_pid = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{_PARENT_ENV} must be a positive process ID") from exc
    if not 0 < parent_pid <= 0x7FFFFFFF or parent_pid == os.getpid():
        raise RuntimeError(f"{_PARENT_ENV} must identify the launching desktop process")

    if os.name == "nt":
        alive, close = _windows_parent_monitor(parent_pid)
    else:
        alive, close = _posix_parent_alive(parent_pid), lambda: None
    stop = threading.Event()
    worker = threading.Thread(
        target=_monitor,
        args=(stop, alive, close),
        name="growwise-parent-watchdog",
        daemon=True,
    )
    try:
        worker.start()
    except BaseException:
        close()
        raise
    return stop
