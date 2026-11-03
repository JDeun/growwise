"""Harness boundary tests only; the Windows journey itself uses no business-response mocks."""

from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest
from PIL import Image

from growwise.runtime_lock import DataDirectoryLock

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


def test_native_navigation_reads_the_canonical_shell_panel(monkeypatch: pytest.MonkeyPatch):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.execute = Mock(side_effect=[False, True])
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    driver.workspace("profile")
    assert driver.execute.call_count == 2
    query, view = driver.execute.call_args.args
    assert "#workspace-panel" in query and "data-active-workspace" in query
    assert view == "profile"


def test_native_select_waits_for_the_new_child_option_before_one_change(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.execute = Mock(side_effect=[False, False, True, None])
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    driver.select(".profile-child-switcher select", "second-child")
    assert driver.execute.call_count == 4
    for call in driver.execute.call_args_list[:3]:
        assert "field.options" in call.args[0]
        assert call.args[1:] == (".profile-child-switcher select", "second-child")
    assert "dispatchEvent" in driver.execute.call_args_list[-1].args[0]


def test_native_reveals_lazy_preview_after_its_container_is_rendered(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.execute = Mock(side_effect=[False, True])
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    driver.reveal(".photo-gallery-thumb")
    assert driver.execute.call_count == 2
    assert "scrollIntoView" in driver.execute.call_args.args[0]
    assert driver.execute.call_args.args[1] == ".photo-gallery-thumb"


def test_native_click_waits_for_a_pointer_hit_then_uses_original_webdriver(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.command = Mock()
    calls = 0

    def geometry_ready(*_args):
        nonlocal calls
        calls += 1
        driver.command.assert_not_called()
        return calls == 3

    driver.execute = Mock(side_effect=geometry_ready)
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    driver.click_element("actual-target")
    assert calls == 3
    driver.command.assert_called_once_with("POST", "/element/actual-target/click", {})


def test_native_result_wait_ignores_preexisting_use_until_exact_observation_is_saved(
    monkeypatch: pytest.MonkeyPatch,
):
    driver = native.WebDriver("http://127.0.0.1:4444")
    prior = [{"learning_logs": []}]
    unrelated = [{"learning_logs": [{"parent_observation": "earlier observation"}]}]
    saved = [{"learning_logs": [{"parent_observation": "민들레를 관찰했다."}]}]
    driver.invoke = Mock(side_effect=[prior, unrelated, saved])
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    assert native.wait_for_material_observation(driver, "material", "민들레를 관찰했다.") == saved
    assert driver.invoke.call_count == 3
    driver.invoke.assert_called_with("list_material_results", materialId="material")


def test_native_navigation_uses_the_same_unobstructed_pointer_path():
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.element = Mock(return_value="nav-target")
    driver.click_element = Mock()
    driver.workspace = Mock()
    driver.navigate("photos")
    driver.click_element.assert_called_once_with("nav-target")
    driver.workspace.assert_called_once_with("photos")


def test_native_bridge_never_appearing_fails_closed(monkeypatch: pytest.MonkeyPatch):
    driver = native.WebDriver("http://127.0.0.1:4444")
    driver.execute = Mock(return_value=False)
    clock = iter([0.0, 0.0, 46.0])
    monkeypatch.setattr(native.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(native.time, "sleep", lambda _seconds: None)
    with pytest.raises(AssertionError, match="original Tauri IPC bridge"):
        driver.wait_for_native_bridge()


def test_native_reads_actual_server_pid_while_writer_lock_is_held(tmp_path: Path):
    with DataDirectoryLock(tmp_path):
        assert native.core_lock_pid(tmp_path) == os.getpid()


@pytest.mark.parametrize("metadata", [b"pid=0\n", b"pid=4294967296\n", b"pid=4\nextra", b"bad"])
def test_native_rejects_invalid_core_owner_metadata(tmp_path: Path, metadata: bytes):
    (tmp_path / ".core.lock").write_bytes(metadata)
    with pytest.raises(AssertionError, match="Invalid Core lock owner"):
        native.core_lock_pid(tmp_path)


@pytest.mark.parametrize(("status", "stdout"), [(0, "owned"), (0, "unowned"), (4, "")])
def test_native_verifies_exact_lock_owner_ancestry_without_commandline_enumeration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: int, stdout: str
):
    (tmp_path / ".core.lock").write_bytes(b"pid=1234\n")

    def run(command, **options):
        query = command[-1]
        assert "CommandLine" not in query
        assert "-Filter ('ProcessId = '+$current)" in query
        assert options["env"]["GROWWISE_E2E_CORE_PID"] == "1234"
        assert options["env"]["GROWWISE_E2E_DRIVER_PID"] == "5678"
        return native.subprocess.CompletedProcess(command, status, stdout, "owned-tree check")

    monkeypatch.setattr(native.subprocess, "run", run)
    if status == 0 and stdout == "owned":
        assert native.owned_core_pid(5678, tmp_path) == 1234
    else:
        with pytest.raises(AssertionError, match="not verified in the owned driver tree"):
            native.owned_core_pid(5678, tmp_path)


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
