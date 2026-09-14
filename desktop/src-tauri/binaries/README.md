# GrowWise Core sidecar binaries

이 디렉터리는 Tauri release bundle에 포함될 `growwise-core` 실행 파일의 생성 위치다.

실행 파일 자체는 저장소에 커밋하지 않는다. 플랫폼별 빌드에서 다음 명령으로 생성한다.

```bash
python -m pip install -e ".[desktop-build]"
python scripts/build_core_sidecar.py
```

생성 결과:

- macOS/Linux: `growwise-core`
- Windows: `growwise-core.exe`

Tauri는 release 실행 시 이 디렉터리를 resource bundle에 포함하고 Rust의
`CoreProcessManager`가 해당 실행 파일을 자동으로 기동한다. 개발 모드에서는 별도 sidecar를
만들지 않고 로컬 Python 환경의 `growwise.api.main`을 실행한다.
