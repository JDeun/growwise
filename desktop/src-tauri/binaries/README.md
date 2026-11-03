# GrowWise Core sidecar binaries

이 디렉터리는 Tauri release bundle에 포함될 `growwise-core` 실행 파일의 생성 위치다.

실행 파일 자체는 저장소에 커밋하지 않는다. 플랫폼별 빌드에서 다음 명령으로 생성한다.

```bash
export UV_PYTHON_INSTALL_DIR=/path/to/empty/managed-python
uv python install --python-downloads-json-url https://raw.githubusercontent.com/astral-sh/uv/901092ee11a89ba287f274e3c6e3a2e18ec2fba2/crates/uv-python/download-metadata.json 3.12.13
uv sync --locked --no-dev --extra desktop-build --managed-python --python 3.12.13
uv run --locked --no-dev --extra desktop-build --managed-python --python 3.12.13 python desktop/scripts/build_core_sidecar.py
```

생성 결과:

- macOS/Linux: `growwise-core`
- Windows: `growwise-core.exe`

빌드는 개발용 pytest/ruff/mypy 등이 남은 공유 환경을 거절한다. 필요하면
`UV_PROJECT_ENVIRONMENT`를 별도 빈 가상환경 경로로 지정한다. 빌드 전에 runtime 라이선스 원문을
`../licenses`에 모으고 해시·의존성 목록을 검증한다. Node 패키지와 Cargo source도 설치되어 있어야
하며, `.github/workflows/package.yml`이 플랫폼별 설치 순서를 제공한다.
고지문은 python-build-standalone20260623의 native component 원문까지 포함하므로, 다른
interpreter build를 쓰려면 먼저 해당 배포자의 고지문과 provenance를 검토해야 한다.

Tauri는 release 실행 시 이 디렉터리를 resource bundle에 포함하고 Rust의
`CoreProcessManager`가 해당 실행 파일을 자동으로 기동한다. 개발 모드에서는 별도 sidecar를
만들지 않고 로컬 Python 환경의 인증된 `growwise.api.secure_entry`를 실행한다.
