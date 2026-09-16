from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINARIES = ROOT / "desktop" / "src-tauri" / "binaries"


def binary_name() -> str:
    return "growwise-core.exe" if os.name == "nt" else "growwise-core"


def reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def authorized_request(url: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )


def wait_until_healthy(
    process: subprocess.Popen[str],
    *,
    base_url: str,
    token: str,
    timeout_seconds: float,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    handshake_url = f"{base_url}/_desktop/handshake"
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(f"GrowWise Core exited before health check: {exit_code}")
        try:
            with urllib.request.urlopen(
                authorized_request(handshake_url, token),
                timeout=0.75,
            ) as response:
                payload = response.read().decode("utf-8")
                parsed = json.loads(payload)
                if (
                    response.status == 200
                    and parsed.get("product") == "growwise-core"
                    and parsed.get("protocol_version") == 1
                ):
                    return payload
        except (OSError, ValueError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise TimeoutError(f"GrowWise Core health check timed out: {last_error}")


def assert_unauthorized(base_url: str) -> None:
    try:
        urllib.request.urlopen(f"{base_url}/health", timeout=0.75)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return
        raise RuntimeError(f"unauthenticated Core request returned HTTP {exc.code}") from exc
    raise RuntimeError("unauthenticated Core request unexpectedly succeeded")


def stop_process(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        # PyInstaller one-file executables use a parent/child process model on Windows.
        # Killing only the Popen process can leave the extracted child holding log/data files.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def wait_until_releasable(path: Path, *, timeout_seconds: float = 5.0) -> None:
    """Wait for Windows child processes to release a recently closed log handle."""
    if os.name != "nt" or not path.exists():
        return

    deadline = time.monotonic() + timeout_seconds
    probe = path.with_name(f"{path.name}.release-probe")
    while True:
        try:
            path.replace(probe)
            probe.replace(path)
            return
        except PermissionError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"GrowWise Core did not release log file: {path}") from exc
            time.sleep(0.1)


def smoke(binary: Path, *, timeout_seconds: float) -> None:
    if not binary.is_file():
        raise FileNotFoundError(binary)

    with tempfile.TemporaryDirectory(prefix="growwise-sidecar-smoke-") as temp_dir:
        temp = Path(temp_dir)
        log_path = temp / "core.log"
        port = reserve_port()
        token = secrets.token_hex(32)
        base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update(
            {
                "GROWWISE_API_HOST": "127.0.0.1",
                "GROWWISE_API_PORT": str(port),
                "GROWWISE_SESSION_TOKEN": token,
                "GROWWISE_DATA_DIR": str(temp / "data"),
                "GROWWISE_LLM_FEATURES_ENABLED": "false",
                "GROWWISE_EMBEDDING_FEATURES_ENABLED": "false",
            }
        )
        try:
            with log_path.open("w", encoding="utf-8") as log_file:
                process = subprocess.Popen(
                    [str(binary)],
                    cwd=ROOT,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                try:
                    payload = wait_until_healthy(
                        process,
                        base_url=base_url,
                        token=token,
                        timeout_seconds=timeout_seconds,
                    )
                    assert_unauthorized(base_url)
                    with urllib.request.urlopen(
                        authorized_request(f"{base_url}/health", token),
                        timeout=0.75,
                    ) as response:
                        health = response.read().decode("utf-8")
                    print(payload)
                    print(health)
                finally:
                    stop_process(process)
        except Exception:
            if log_path.exists():
                print(log_path.read_text(encoding="utf-8", errors="replace"))
            raise
        finally:
            # On Windows, taskkill can return just before the PyInstaller child releases
            # its inherited stdout handle. Waiting here keeps TemporaryDirectory cleanup
            # from turning a successful health smoke into a spurious WinError 32 failure.
            wait_until_releasable(log_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a bundled GrowWise Core executable.")
    parser.add_argument(
        "binary",
        nargs="?",
        type=Path,
        default=BINARIES / binary_name(),
        help="Path to the platform-local Core executable.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    smoke(args.binary.resolve(), timeout_seconds=args.timeout)


if __name__ == "__main__":
    main()
