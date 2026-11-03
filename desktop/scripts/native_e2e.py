"""Real Windows WebView -> Rust IPC -> managed authenticated Core. No IPC/API shim.

Only the Python standard library is used. Build with tauri.e2e.conf.json first; never run
this destructive synthetic journey against the normal application identifier/data directory.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import traceback
import zlib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER = "io.github.jdeun.growwise.e2e"
ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"
MAX_DRIVER_RESPONSE = 16 * 1024 * 1024


class WebDriverError(RuntimeError):
    pass


class WebDriver:
    def __init__(self, address: str) -> None:
        self.address = address
        self.session = ""

    def request(self, method: str, path: str, payload: Any = None, *, timeout: int = 60) -> Any:
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(
            self.address + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            response = urlopen(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_DRIVER_RESPONSE + 1)
            if len(raw) > MAX_DRIVER_RESPONSE:
                raise WebDriverError("WebDriver response exceeded 16 MiB")
            result = json.loads(raw).get("value")
            if response.status >= 400:
                raise WebDriverError(f"{method} {path}: {str(result)[:4000]}")
            return result

    def command(self, method: str, path: str, payload: Any = None) -> Any:
        if not self.session:
            raise WebDriverError("WebDriver session has not started")
        return self.request(method, f"/session/{self.session}{path}", payload)

    def start(self, application: Path) -> None:
        result = self.request(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "tauri:options": {"application": str(application)},
                    }
                }
            },
        )
        self.session = result["sessionId"]
        self.command("POST", "/timeouts", {"script": 30000, "pageLoad": 60000, "implicit": 0})

    def execute(self, script: str, *args: Any) -> Any:
        return self.command("POST", "/execute/sync", {"script": script, "args": list(args)})

    def invoke(self, command: str, **args: Any) -> Any:
        # Call the original production bridge. Never assign, intercept or replace invoke/fetch.
        result = self.command(
            "POST",
            "/execute/async",
            {
                "script": """
            const done = arguments[arguments.length - 1];
            window.__TAURI_INTERNALS__.invoke(arguments[0], arguments[1])
              .then(value => done({ok:true,value}))
              .catch(error => done({ok:false,error:String(error)}));
        """,
                "args": [command, args],
            },
        )
        if not result["ok"]:
            raise WebDriverError(f"Native {command}: {result['error']}")
        return result["value"]

    def element(self, selector: str) -> str:
        result = self.command("POST", "/element", {"using": "css selector", "value": selector})
        return result[ELEMENT_KEY]

    def click(self, text: str, selector: str = "button") -> None:
        element = wait_for(
            lambda: self.execute(
                """
            return [...document.querySelectorAll(arguments[0])].find(node =>
              (node.textContent.trim() === arguments[1]
                || node.querySelector('strong')?.textContent.trim() === arguments[1])
              && !node.disabled && node.getBoundingClientRect().height > 0) ?? null;
        """,
                selector,
                text,
            ),
            f"click {text}",
        )
        self.command("POST", f"/element/{element[ELEMENT_KEY]}/click", {})

    def fill(self, selector: str, value: str) -> None:
        wait_for(
            lambda: self.execute(
                """
            const node=document.querySelector(arguments[0]);
            return !!node && !node.disabled && node.getBoundingClientRect().height > 0;
        """,
                selector,
            ),
            f"enabled field {selector}",
        )
        element = self.element(selector)
        self.command("POST", f"/element/{element}/clear", {})
        self.command("POST", f"/element/{element}/value", {"text": value})

    def select(self, selector: str, value: str) -> None:
        # React receives the same DOM input/change events as a native select interaction.
        self.execute(
            """
            const field=document.querySelector(arguments[0]);
            if (!field || field.disabled) throw new Error('select unavailable');
            Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(field,arguments[1]);
            field.dispatchEvent(new Event('input',{bubbles:true}));
            field.dispatchEvent(new Event('change',{bubbles:true}));
        """,
            selector,
            value,
        )

    def navigate(self, view: str) -> None:
        element = self.element(f"#workspace-nav-{view}")
        self.command("POST", f"/element/{element}/click", {})
        self.workspace(view)

    def workspace(self, view: str) -> None:
        wait_for(
            lambda: self.execute(
                """
            return [...document.querySelectorAll('[data-workspace-view]')].some(node =>
              node.getAttribute('data-workspace-view') === arguments[0]
              && node.getBoundingClientRect().height > 0);
        """,
                view,
            ),
            f"workspace {view}",
        )

    def screenshot(self, destination: Path) -> None:
        image = self.command("GET", "/screenshot")
        destination.write_bytes(base64.b64decode(image, validate=True))

    def close(self) -> None:
        if self.session:
            self.request("DELETE", f"/session/{self.session}", timeout=10)
            self.session = ""


def wait_for(check: Callable[[], Any], label: str, timeout: float = 45) -> Any:
    deadline = time.monotonic() + timeout
    last_error = ""
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except (WebDriverError, URLError, ConnectionError, TimeoutError) as error:
            last_error = str(error)
        time.sleep(0.2)
    raise AssertionError(f"Timed out: {label}. {last_error}")


def isolated_data_dir(value: str) -> Path:
    path = Path(value).resolve()
    if path.name != IDENTIFIER:
        raise AssertionError(f"Refusing to write to a non-E2E application data directory: {path}")
    return path


def free_port() -> int:
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        return int(reservation.getsockname()[1])


def runtime_python() -> str:
    # Resolving a venv symlink can launch the base interpreter without the installed Core.
    return str(Path(sys.executable).absolute())


def integrity_level() -> str:
    if sys.platform != "win32":
        raise RuntimeError("Token integrity inspection requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    security = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    security.OpenProcessToken.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    security.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    security.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    token, text = ctypes.c_void_p(), ctypes.c_void_p()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError()
    try:
        size = ctypes.c_ulong()
        security.GetTokenInformation(token, 25, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError()
        data = ctypes.create_string_buffer(size.value)
        if not security.GetTokenInformation(token, 25, data, size, ctypes.byref(size)):
            raise ctypes.WinError()
        sid = ctypes.cast(data, ctypes.POINTER(ctypes.c_void_p))[0]
        if not security.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError()
        return ctypes.wstring_at(text)
    finally:
        if text.value:
            kernel.LocalFree(text)
        kernel.CloseHandle(token)


def is_medium_integrity(sid: str) -> bool:
    # Microsoft defines the entire [Medium, High) range, including Medium+ and UIAccess.
    match = re.fullmatch(r"S-1-16-(\d+)", sid)
    return bool(match and 8192 <= int(match[1]) < 12288)


def write_png(path: Path) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        )

    width, height = 2048, 1536
    rows = (b"\0" + b"\x39\x74\x5d" * width) * height
    encoded = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(encoded)
    return encoded


def stop_owned_driver(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        # tauri-driver also places its descendants in a kill-on-close Windows Job.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
            timeout=15,
        )
        process.wait(timeout=10)


def process_alive(pid: int) -> bool:
    if sys.platform != "win32":
        raise RuntimeError("Owned process inspection requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in (87, 1168):  # Process does not exist.
            return False
        raise OSError(error, "Cannot inspect the owned Core process")
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259)
    finally:
        kernel.CloseHandle(handle)


def owned_core_pid(driver_pid: int) -> int:
    # Windows byte-range locks can prevent reading .core.lock while the writer owns it.
    # Inspect only the driver descendant tree and return a PID, never other process details.
    query = r"""
        $ErrorActionPreference='Stop'
        $root=[uint32]$env:GROWWISE_E2E_DRIVER_PID
        $processes=@(Get-CimInstance Win32_Process)
        $parents=@{}
        foreach($process in $processes){$parents[[uint32]$process.ProcessId]=$process}
        $found=@(foreach($process in $processes){
          if($process.CommandLine -match '(^|\s)-m\s+growwise\.api\.secure_entry(\s|$)'){
            $ancestor=[uint32]$process.ParentProcessId
            $visited=@{}
            while($ancestor -ne 0 -and -not $visited.ContainsKey($ancestor)){
              if($ancestor -eq $root){[uint32]$process.ProcessId;break}
              $visited[$ancestor]=$true
              if(-not $parents.ContainsKey($ancestor)){break}
              $ancestor=[uint32]$parents[$ancestor].ParentProcessId
            }
          }
        })
        if($found.Count -ne 1){throw 'Expected one Core in the owned driver process tree'}
        Write-Output $found[0]
    """
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", query],
        env={**os.environ, "GROWWISE_E2E_DRIVER_PID": str(driver_pid)},
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
    pid = int(result.stdout.strip())
    if pid <= 0:
        raise AssertionError("Invalid owned Core PID")
    return pid


def run_journey(driver: WebDriver, artifacts: Path, report: dict[str, Any]) -> Path:
    steps = report["steps"]
    wait_for(
        lambda: driver.execute("return !!document.querySelector('.workspace-shell-root')"),
        "actual native WebView",
    )
    driver.execute("""
        window.__NATIVE_E2E_ERRORS__=[];
        addEventListener('error',event=>
          window.__NATIVE_E2E_ERRORS__.push(String(event.error ?? event.message)));
        addEventListener('unhandledrejection',event=>
          window.__NATIVE_E2E_ERRORS__.push(String(event.reason)));
    """)
    assert driver.invoke("core_runtime_status")["started_by_desktop"] is True
    health = driver.invoke("core_health")
    assert health["status"] == "ok"
    assert health["llm_features_enabled"] is False
    assert health["embedding_features_enabled"] is False
    data_dir = isolated_data_dir(driver.invoke("get_storage_location"))
    report["data_identifier"] = data_dir.name
    assert driver.invoke("list_children") == [], (
        "E2E data directory must be empty before this synthetic journey"
    )
    steps.append(
        "actual WebView calls original Rust IPC; Desktop starts and authenticates a real "
        "AI-disabled Core in isolated E2E storage"
    )
    driver.screenshot(artifacts / "01-native-empty-home.png")
    driver.click("프로필 입력으로 이동")
    driver.workspace("profile")
    driver.fill('.profile-form input[placeholder="예: 샘플아이"]', "윈도우합성아이")
    driver.select(".profile-form select", "elementary")
    driver.click("첫 프로필 저장")
    driver.workspace("materials")
    children = driver.invoke("list_children")
    assert len(children) == 1 and children[0]["nickname"] == "윈도우합성아이"
    child_id = children[0]["id"]
    steps.append("UI first profile persists through real Rust -> Core IPC")

    driver.fill(".material-topic-field input", "민들레 씨앗 관찰")
    driver.execute("document.querySelector('.material-composer').requestSubmit()")
    materials = wait_for(
        lambda: driver.invoke("list_materials", childId=child_id), "persisted material"
    )
    assert len(materials) == 1 and materials[0]["status"] != "approved"
    driver.click("이 활동 사용하기")
    wait_for(
        lambda: driver.invoke("list_materials", childId=child_id)[0]["status"] == "approved",
        "parent approval",
    )
    material_id = materials[0]["id"]
    driver.click("활동 결과 기록")
    observation = "민들레 씨앗을 보고 왜 날아가는지 질문했다."
    driver.fill(".material-result-panel textarea", observation)
    driver.execute("document.querySelector('.material-result-panel').requestSubmit()")
    results = wait_for(
        lambda: driver.invoke("list_material_results", materialId=material_id),
        "authoritative one-line result",
    )
    assert any(
        observation in log["parent_observation"]
        for result in results
        for log in result["learning_logs"]
    )
    assert driver.invoke("list_learning_records", childId=child_id)
    driver.screenshot(artifacts / "02-native-material-result.png")
    steps.append(
        "UI generates a real template, explicitly approves it and saves "
        "an authoritative one-line learning result"
    )

    driver.navigate("photos")
    if not driver.execute(
        "return document.querySelector('.photo-create-summary').closest('details').open"
    ):
        driver.click("새 사진 기록", ".photo-create-summary")
    photo_path = artifacts / "synthetic-activity.png"
    original = write_png(photo_path)
    file_input = driver.element('.photo-workspace input[type="file"]')
    driver.command("POST", f"/element/{file_input}/value", {"text": str(photo_path.resolve())})
    wait_for(
        lambda: driver.execute("""
        const image=document.querySelector('.photo-preview-grid img');
        return image?.complete && image.naturalWidth > 0
          && image.naturalWidth <= 384 && image.naturalHeight <= 384;
    """),
        "bounded local selected-photo preview",
    )
    driver.fill('.photo-workspace textarea[placeholder^="예: 오늘 둘이"]', observation)
    driver.execute("""
        const checkbox=[...document.querySelectorAll('.photo-workspace input[type=checkbox]')]
          .find(node=>node.closest('label').innerText.includes('로컬 AI'));
        if(checkbox.checked) checkbox.click();
    """)
    driver.click("사진 일기 저장")
    driver.click("확인하고 관찰 기록으로 저장")
    photos = wait_for(
        lambda: [
            item
            for item in driver.invoke("list_photo_records", childId=child_id)
            if item["status"] == "committed"
        ],
        "photo parent confirmation",
    )
    asset_id = photos[0]["photo_asset_ids"][0]
    thumbnail = driver.invoke("get_photo_thumbnail", childId=child_id, assetId=asset_id)
    assert (
        thumbnail["mime_type"] == "image/jpeg"
        and max(thumbnail["width"], thumbnail["height"]) <= 384
    )
    assert len(base64.b64decode(thumbnail["data_base64"])) <= 128 * 1024
    assert (
        base64.b64decode(
            driver.invoke("get_photo_asset", childId=child_id, assetId=asset_id)["data_base64"]
        )
        == original
    )
    wait_for(
        lambda: driver.execute("""
        return [...document.querySelectorAll('.photo-gallery-thumb img')]
          .some(image=>image.complete && image.naturalWidth>0
            && image.naturalWidth<=384 && image.naturalHeight<=384
            && image.src.startsWith('data:image/jpeg;base64,'));
    """),
        "native IPC thumbnail displayed",
    )
    driver.screenshot(artifacts / "03-native-photo-thumbnail.png")
    steps.append(
        "real native file selection/upload/confirmation/thumbnail IPC succeeds; "
        "2048x1536 PNG original remains byte-identical"
    )

    driver.navigate("profile")
    driver.click("아이 추가 · 사진 관리")
    driver.fill('.profile-form input[placeholder="예: 샘플아이"]', "윈도우합성둘째")
    driver.select(".profile-form select", "elementary")
    driver.click("새 프로필 저장")
    children = wait_for(
        lambda: items if len(items := driver.invoke("list_children")) == 2 else None,
        "second child profile",
    )
    second_id = next(child["id"] for child in children if child["id"] != child_id)
    driver.click("← 프로필로 돌아가기")
    driver.select(".profile-child-switcher select", second_id)
    driver.navigate("conversation")
    driver.click("기록을 직접 검색하기", "summary")
    driver.fill(".search-form input", "민들레")
    driver.execute("document.querySelector('.search-form').requestSubmit()")
    wait_for(
        lambda: driver.execute(
            "return document.querySelector('.search-results')?.innerText.includes('검색 결과 0건')"
        ),
        "private sibling search remains empty",
    )
    assert driver.invoke("list_materials", childId=second_id) == []
    assert driver.invoke("list_learning_records", childId=second_id) == []
    assert driver.invoke("list_photo_records", childId=second_id) == []
    try:
        driver.invoke("get_photo_thumbnail", childId=second_id, assetId=asset_id)
    except WebDriverError as error:
        assert "404" in str(error)
    else:
        raise AssertionError("A sibling must not read another child's photo thumbnail")
    driver.screenshot(artifacts / "04-native-private-sibling.png")
    steps.append(
        "UI child switching isolates real private search, materials, "
        "learning records and photo thumbnails"
    )

    driver.navigate("profile")
    driver.select(".profile-child-switcher select", child_id)
    driver.navigate("backup")
    driver.click("지금 백업", ".backup-status-card button")
    backups = wait_for(lambda: driver.invoke("list_backups"), "UI-created real backup")
    assert Path(backups[0]["path"]).is_file() and backups[0]["size_bytes"] > 0
    driver.screenshot(artifacts / "05-native-backup.png")
    assert any(
        observation in path.read_text(encoding="utf-8") for path in data_dir.rglob("*.md")
    ), "authoritative Markdown must be durable on disk"
    assert driver.execute("return window.__NATIVE_E2E_ERRORS__") == []
    steps.append(
        "UI creates a real local backup; authoritative Markdown is durable on disk "
        "and no unhandled renderer errors occurred"
    )
    return data_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--native-driver", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Actual native WebDriver execution is supported here only on Windows")
    integrity = integrity_level()
    if not is_medium_integrity(integrity):
        parser.error(f"Run via run_native_e2e.ps1 with Medium integrity; actual SID={integrity}")
    application = args.app.resolve(strict=True)
    native_driver = args.native_driver.resolve(strict=True)
    driver_path = shutil.which("tauri-driver")
    if not driver_path:
        parser.error("Install the workflow-pinned tauri-driver first")
    artifacts = args.artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "passed": False,
        "transport": "actual Windows WebView2 -> original Rust IPC -> authenticated managed Core",
        "steps": [],
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ai_enabled": False,
        "commit": os.environ.get("GITHUB_SHA"),
        "integrity_level": integrity,
    }
    with application.open("rb") as binary:
        report["application_sha256"] = hashlib.file_digest(binary, "sha256").hexdigest()
    port, native_port = free_port(), free_port()
    while native_port == port:
        native_port = free_port()
    env = {
        **os.environ,
        "GROWWISE_PYTHON": runtime_python(),
        "TAURI_WEBVIEW_AUTOMATION": "true",
        "MSEDGEDRIVER_TELEMETRY_OPTOUT": "1",
    }
    for key in ("LLM", "EMBEDDING", "VISION"):
        env[f"GROWWISE_{key}_FEATURES_ENABLED"] = "false"
    env["GROWWISE_PUBLIC_ENRICHMENT_ENABLED"] = "false"
    env.pop("GROWWISE_CORE_EXECUTABLE", None)
    driver = WebDriver(f"http://127.0.0.1:{port}")
    core_pid = None
    exit_code = 1
    with (artifacts / "tauri-driver.log").open("wb") as log:
        process = subprocess.Popen(
            [
                driver_path,
                "--port",
                str(port),
                "--native-port",
                str(native_port),
                "--native-driver",
                str(native_driver),
            ],
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
        )
        (artifacts / "driver-pid.json").write_text(
            json.dumps({"pid": process.pid, "executable": str(Path(driver_path).resolve())}),
            encoding="utf-8",
        )
        try:
            wait_for(lambda: driver.request("GET", "/status"), "tauri-driver startup", timeout=30)
            driver.start(application)
            isolated_data_dir(driver.invoke("get_storage_location"))
            core_pid = owned_core_pid(process.pid)
            run_journey(driver, artifacts, report)
            report["passed"] = True
            exit_code = 0
        except Exception:
            report["error"] = traceback.format_exc()
            try:
                driver.screenshot(artifacts / "failure.png")
                (artifacts / "failure.html").write_text(
                    driver.command("GET", "/source"), encoding="utf-8"
                )
                report["renderer_errors"] = driver.execute(
                    "return window.__NATIVE_E2E_ERRORS__ ?? []"
                )
            except Exception as capture_error:
                report["capture_error"] = str(capture_error)
        finally:
            try:
                driver.close()
            except Exception as close_error:
                report["session_close_error"] = str(close_error)
                report["passed"] = False
                exit_code = 1
            try:
                stop_owned_driver(process)
            except Exception as cleanup_error:
                report["driver_cleanup_error"] = str(cleanup_error)
                report["passed"] = False
                exit_code = 1
            if core_pid is not None:
                try:
                    wait_for(
                        lambda: not process_alive(core_pid),
                        "Desktop-managed Core exits with native app",
                        timeout=10,
                    )
                    report["core_exited"] = True
                except (AssertionError, OSError) as cleanup_error:
                    report["core_exited"] = False
                    report["core_cleanup_error"] = str(cleanup_error)
                    report["passed"] = False
                    exit_code = 1
                    try:
                        subprocess.run(
                            ["taskkill", "/PID", str(core_pid), "/T", "/F"],
                            check=False,
                            capture_output=True,
                            timeout=15,
                        )
                    except subprocess.TimeoutExpired:
                        report["core_force_stop_timed_out"] = True
            (artifacts / "report.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
