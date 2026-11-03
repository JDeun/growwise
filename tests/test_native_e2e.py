"""Harness boundary tests only; the Windows journey itself uses no business-response mocks."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/native_e2e.py"
spec = importlib.util.spec_from_file_location("native_e2e", SCRIPT)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class DriverResponse(io.BytesIO):
    status = 200


def test_native_harness_refuses_regular_application_storage(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="non-E2E"):
        native.isolated_data_dir(str(tmp_path / "io.github.jdeun.growwise"))
    assert native.isolated_data_dir(str(tmp_path / native.IDENTIFIER)).name == native.IDENTIFIER
    overlay = json.loads((SCRIPT.parent.parent / "src-tauri/tauri.e2e.conf.json").read_text())
    assert overlay["identifier"] == native.IDENTIFIER
    assert overlay["bundle"]["active"] is False


def test_webdriver_protocol_sets_real_application_capability_and_script_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    def wire(request, *, timeout):
        payload = json.loads(request.data)
        calls.append((request.full_url, request.method, payload, timeout))
        value = {"sessionId": "native-session", "capabilities": {}} if len(calls) == 1 else None
        return DriverResponse(json.dumps({"value": value}).encode())

    monkeypatch.setattr(native, "urlopen", wire)
    driver = native.WebDriver("http://127.0.0.1:4444")
    executable = tmp_path / "growwise-desktop.exe"
    driver.start(executable)
    assert calls[0][2] == {
        "capabilities": {"alwaysMatch": {"tauri:options": {"application": str(executable)}}}
    }
    assert calls[1][0].endswith("/session/native-session/timeouts")
    assert calls[1][2]["script"] == 30000


def test_webdriver_http_errors_keep_protocol_context(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed(request, *, timeout):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            io.BytesIO(b'{"value":{"error":"no such element","message":"missing button"}}'),
        )

    monkeypatch.setattr(native, "urlopen", failed)
    driver = native.WebDriver("http://127.0.0.1:4444")
    with pytest.raises(native.WebDriverError, match="no such element"):
        driver.request("POST", "/session/native/element", {"using": "css selector"})


def test_native_bridge_waits_through_initial_blank_navigation(monkeypatch: pytest.MonkeyPatch):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.session = "native-session"
    driver.execute = Mock(side_effect=[False, False, True])
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    driver.wait_for_native_bridge()
    assert driver.execute.call_count == 3
    assert all(
        call.args == ("return typeof window.__TAURI_INTERNALS__?.invoke === 'function'",)
        for call in driver.execute.call_args_list
    )


def test_native_bridge_never_appearing_fails_closed(monkeypatch: pytest.MonkeyPatch):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.execute = Mock(return_value=False)
    clock = iter([0.0, 0.0, 46.0])
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    with pytest.raises(AssertionError, match="original Tauri IPC bridge"):
        driver.wait_for_native_bridge()


def test_webdriver_response_size_is_bounded_before_json_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        native,
        "urlopen",
        lambda request, timeout: DriverResponse(b"x" * (native.MAX_DRIVER_RESPONSE + 1)),
    )
    with pytest.raises(native.WebDriverError, match="exceeded 16 MiB"):
        native.WebDriver("http://127.0.0.1:4444").request("GET", "/status")


def test_native_photo_fixture_is_real_multimegapixel_png(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    original = native.write_png(path)
    assert path.read_bytes() == original
    with Image.open(path) as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (2048, 1536)
        assert image.getpixel((1024, 768)) == (57, 116, 93)


def test_core_python_keeps_the_virtual_environment_entry_point(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = tmp_path / "base-python"
    base.write_bytes(b"synthetic interpreter")
    venv = tmp_path / "venv-python"
    try:
        venv.symlink_to(base)
    except OSError:
        pytest.skip("Creating a symlink requires OS support/Windows developer permission")
    monkeypatch.setattr(native.sys, "executable", str(venv))
    assert native.runtime_python() == str(venv.absolute())
    assert native.runtime_python() != str(base.resolve())


def test_native_integrity_check_requires_a_real_medium_integrity_sid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert native.is_medium_integrity("S-1-16-8192")
    assert native.is_medium_integrity("S-1-16-8208")
    assert native.is_medium_integrity("S-1-16-8448")
    for sid in ["S-1-16-4096", "S-1-16-12288", "S-1-16-16384", "8192"]:
        assert not native.is_medium_integrity(sid)


@pytest.mark.parametrize(
    ("sid", "elevated", "admin", "expected"),
    [
        ("S-1-16-8192", False, False, True),
        ("S-1-16-8448", False, False, True),
        ("S-1-16-8192", True, False, False),
        ("S-1-16-8192", False, True, False),
        ("S-1-16-8192", True, True, False),
        ("S-1-16-12288", False, False, False),
        ("S-1-16-4096", False, False, False),
    ],
)
def test_medium_integrity_alone_does_not_prove_a_non_admin_token(sid, elevated, admin, expected):
    assert (
        native.is_standard_medium_token(
            sid,
            {
                "token_is_elevated": elevated,
                "administrator_group_enabled": admin,
            },
        )
        is expected
    )


@pytest.mark.parametrize(("elevated", "admin"), [(0, 0), (1, 0), (0, 1)])
def test_elevation_inspects_this_process_and_enabled_admin_membership(
    monkeypatch: pytest.MonkeyPatch,
    elevated,
    admin,
) -> None:
    import ctypes

    kernel, security, shell = Mock(), Mock(), Mock()
    kernel.GetCurrentProcess.return_value = 123
    shell.IsUserAnAdmin.return_value = admin

    def open_token(process, access, token):
        assert process == 123 and access == 8
        ctypes.cast(token, ctypes.POINTER(ctypes.c_void_p))[0] = 456
        return 1

    def query_token(token, kind, data, size, needed):
        assert token.value == 456 and kind == 20
        ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[0] = elevated
        ctypes.cast(needed, ctypes.POINTER(ctypes.c_ulong))[0] = size
        return 1

    security.OpenProcessToken.side_effect = open_token
    security.GetTokenInformation.side_effect = query_token
    monkeypatch.setattr(native.sys, "platform", "win32")
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, **_kwargs: {
            "kernel32": kernel,
            "advapi32": security,
            "shell32": shell,
        }[name],
        raising=False,
    )
    assert native.elevation_state() == {
        "token_is_elevated": bool(elevated),
        "administrator_group_enabled": bool(admin),
    }
    shell.IsUserAnAdmin.assert_called_once()
    kernel.CloseHandle.assert_called_once()


def test_interactive_worker_uses_a_filtered_child_and_keeps_os_security_policies():
    source = (SCRIPT.parent / "run_native_e2e.ps1").read_text(encoding="utf-8")
    assert "windows_filtered_process.cs" in source
    assert "LaunchFiltered" in source and "-FilteredWorker" in source
    assert "-not $token.IsElevated -and -not $token.AdministratorsEnabled" in source
    assert "LowerToMedium" not in source
    assert "--no-sandbox" not in source
    assert "[switch]$ProbeOnly" in source
    assert "probe_only = [bool]$ProbeOnly" in source
    assert "if ($payload.probe_only)" in source
    workflow = (SCRIPT.parents[2] / ".github/workflows/native-e2e.yml").read_text(encoding="utf-8")
    assert workflow.index("Verify actual filtered process launch") < workflow.index(
        "Install pinned Rust"
    )
    assert "native-token-preflight" in workflow


def test_integrity_reads_this_process_token_and_releases_handles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes

    kernel, security = Mock(), Mock()
    kernel.GetCurrentProcess.return_value = 123
    sid_text = ctypes.create_unicode_buffer("S-1-16-8192")

    def open_token(process, access, token):
        assert process == 123 and access == 8
        ctypes.cast(token, ctypes.POINTER(ctypes.c_void_p))[0] = 456
        return 1

    def query_token(token, kind, data, size, needed):
        assert token.value == 456 and kind == 25
        ctypes.cast(needed, ctypes.POINTER(ctypes.c_ulong))[0] = 32
        if data is not None:
            ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0] = 789
            return 1
        return 0

    def stringify(sid, text):
        assert sid == 789
        ctypes.cast(text, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(sid_text)
        return 1

    security.OpenProcessToken.side_effect = open_token
    security.GetTokenInformation.side_effect = query_token
    security.ConvertSidToStringSidW.side_effect = stringify
    monkeypatch.setattr(native.sys, "platform", "win32")
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda name, **kwargs: kernel if name == "kernel32" else security,
        raising=False,
    )
    assert native.integrity_level() == "S-1-16-8192"
    kernel.CloseHandle.assert_called_once()
    kernel.LocalFree.assert_called_once()
