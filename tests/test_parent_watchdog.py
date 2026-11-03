from __future__ import annotations

import os
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace

import pytest

from growwise.api import parent_watchdog
from growwise.runtime_lock import DataDirectoryLock, DataDirectoryLockError


def test_standalone_core_does_not_start_a_parent_watchdog(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GROWWISE_PARENT_PID", raising=False)
    assert parent_watchdog.start_parent_watchdog() is None


@pytest.mark.parametrize("pid", ["", "invalid", "0", "-1", str(2**63), str(os.getpid())])
def test_parent_process_id_is_validated(pid: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROWWISE_PARENT_PID", pid)
    with pytest.raises(RuntimeError, match="GROWWISE_PARENT_PID"):
        parent_watchdog.start_parent_watchdog()


def test_posix_monitor_handles_bootloader_parent_and_reparenting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(parent_watchdog.os, "getppid", lambda: 222)
    calls = []
    monkeypatch.setattr(parent_watchdog.os, "kill", lambda pid, sig: calls.append((pid, sig)))
    alive = parent_watchdog._posix_parent_alive(111)
    assert alive()
    assert calls == [(111, 0)]
    monkeypatch.setattr(parent_watchdog.os, "getppid", lambda: 1)
    assert not alive()


class NativeCall:
    def __init__(self, result: int) -> None:
        self.result = result
        self.calls: list[tuple] = []

    def __call__(self, *args):
        self.calls.append(args)
        return self.result


def test_windows_retains_process_handle_without_sending_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = SimpleNamespace(OpenProcess=NativeCall(123), WaitForSingleObject=NativeCall(258),
                          CloseHandle=NativeCall(1))
    monkeypatch.setattr(parent_watchdog.ctypes, "WinDLL", lambda *_a, **_kw: api, raising=False)
    monkeypatch.setattr(parent_watchdog.os, "getppid", lambda: 321)
    alive, close = parent_watchdog._windows_parent_monitor(321)
    assert api.OpenProcess.calls == [(0x00100000, False, 321)]
    assert alive()
    assert api.WaitForSingleObject.calls == [(123, 0)]
    api.WaitForSingleObject.result = 0
    assert not alive()
    api.WaitForSingleObject.result = 0xFFFFFFFF
    assert not alive()
    close()
    assert api.CloseHandle.calls == [(123,)]
    assert api.OpenProcess.restype is parent_watchdog.ctypes.c_void_p


def test_windows_bootloader_death_exits_even_while_desktop_remains_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class OpenProcess(NativeCall):
        def __call__(self, *args):
            self.calls.append(args)
            return args[2] + 1000

    class WaitForSingleObject(NativeCall):
        def __call__(self, handle, timeout):
            self.calls.append((handle, timeout))
            return 0 if handle == 1222 and self.result == 0 else 258

    api = SimpleNamespace(OpenProcess=OpenProcess(0), WaitForSingleObject=WaitForSingleObject(258),
                          CloseHandle=NativeCall(1))
    monkeypatch.setattr(parent_watchdog.ctypes, "WinDLL", lambda *_a, **_kw: api, raising=False)
    monkeypatch.setattr(parent_watchdog.os, "getppid", lambda: 222)
    alive, close = parent_watchdog._windows_parent_monitor(111)
    assert api.OpenProcess.calls == [(0x00100000, False, 111), (0x00100000, False, 222)]
    assert alive()
    api.WaitForSingleObject.result = 0
    assert not alive()
    assert (1111, 0) in api.WaitForSingleObject.calls
    close()
    assert api.CloseHandle.calls == [(1111,), (1222,)]


def test_windows_monitor_handles_already_exited_parent_and_access_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = SimpleNamespace(OpenProcess=NativeCall(0), WaitForSingleObject=NativeCall(0),
                          CloseHandle=NativeCall(1))
    monkeypatch.setattr(parent_watchdog.ctypes, "WinDLL", lambda *_a, **_kw: api, raising=False)
    monkeypatch.setattr(parent_watchdog.ctypes, "get_last_error", lambda: 87, raising=False)
    alive, close = parent_watchdog._windows_parent_monitor(321)
    assert not alive()
    close()
    assert api.CloseHandle.calls == []
    monkeypatch.setattr(parent_watchdog.ctypes, "get_last_error", lambda: 5)
    with pytest.raises(RuntimeError, match="cannot monitor"):
        parent_watchdog._windows_parent_monitor(321)


def test_orphaned_secure_core_exits_and_releases_data_directory_lock(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    data = tmp_path / "data"
    core_code = """
import os, threading
from pathlib import Path
from growwise.api import secure_entry
def serve(*args, **kwargs):
    Path(os.environ['WATCHDOG_TEST_READY']).write_text(str(os.getpid()))
    threading.Event().wait(60)
secure_entry.uvicorn.run = serve
secure_entry.run()
"""
    wrapper_code = """
import os, subprocess, sys, time
from pathlib import Path
env = {**os.environ, 'GROWWISE_PARENT_PID': str(os.getpid())}
core = subprocess.Popen([sys.executable, '-c', sys.argv[1]], env=env, stdin=subprocess.DEVNULL)
deadline = time.monotonic() + 15
while not Path(env['WATCHDOG_TEST_READY']).exists():
    if core.poll() is not None or time.monotonic() > deadline:
        core.terminate()
        core.wait(timeout=5)
        raise RuntimeError('test Core did not acquire its data lock')
    time.sleep(0.02)
print(core.pid, flush=True)
sys.stdin.readline()
os._exit(0)
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        "GROWWISE_DATA_DIR": str(data),
        "GROWWISE_SESSION_TOKEN": "synthetic-watchdog-token-" * 3,
        "GROWWISE_LLM_FEATURES_ENABLED": "false",
        "GROWWISE_EMBEDDING_FEATURES_ENABLED": "false",
        "GROWWISE_VISION_FEATURES_ENABLED": "false",
        "WATCHDOG_TEST_READY": str(ready),
    }
    with (tmp_path / "core-errors.log").open("w") as errors:
        wrapper = subprocess.Popen([sys.executable, "-c", wrapper_code, core_code], env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, text=True)
        core_pid: int | None = None
        completed = False
        try:
            assert wrapper.stdout is not None
            line = wrapper.stdout.readline()
            assert line.strip(), (tmp_path / "core-errors.log").read_text()
            core_pid = int(line)
            with pytest.raises(DataDirectoryLockError):
                DataDirectoryLock(data).acquire()
            # Core inherits stdout, so EOF proves both the wrapper and its Core have exited.
            wrapper.communicate("\n", timeout=8)
            completed = True
            assert wrapper.returncode == 0
            with DataDirectoryLock(data):
                pass
        finally:
            if wrapper.poll() is None:
                wrapper.kill()
                wrapper.wait(timeout=5)
            if not completed and core_pid is not None:
                with suppress(ProcessLookupError):
                    os.kill(core_pid, signal.SIGTERM)
