# 실제 Windows 앱 E2E

`.github/workflows/native-e2e.yml`은 GitHub Windows runner에서 GrowWise 실행 파일을 열고
WebView2 → 원래 Rust IPC → Desktop이 시작한 인증 Core → Markdown 저장 경로를 검증한다.
브라우저의 IPC 어댑터 테스트와 별도 검사이며 `invoke`, `fetch`, API 응답을 대체하지 않는다.

Python 표준 라이브러리 HTTP 클라이언트가 W3C WebDriver 명령을 전송한다. 공식 `tauri-driver`
2.1.0과 Microsoft Edge WebDriver를 사용하고, 앱에 테스트 플러그인이나 새 의존성을 넣지 않는다.
공식 근거: [Tauri 수동 WebDriver 설정](https://v2.tauri.app/develop/tests/webdriver/manual-setup/),
[Tauri driver 릴리스](https://v2.tauri.app/release/tauri-driver/),
[Microsoft WebView2 테스트](https://learn.microsoft.com/microsoft-edge/webview2/how-to/webdriver),
[W3C 프로토콜](https://www.w3.org/TR/webdriver/).

WebView2 150 이후에는 관리자 권한 host의 디버깅 환경 변수가 무시된다. GitHub Windows runner는
관리자 권한으로 시작하므로 `run_native_e2e.ps1`은 현재 로그인 사용자의 `Interactive / RunLevel
Limited` task를 데스크톱 bootstrap으로 사용한다. Medium label만으로는 관리자 권한이 제거되지
않는다. bootstrap이 여전히 상승 토큰/활성 Administrators 그룹을 갖고 있으면
`windows_filtered_process.cs`가 linked token, SAFER NormalUser, 제한된 LUA token 순서로
검증 가능한 토큰을 선택하고 실제 테스트를 별도 자식 프로세스로 실행한다.

실행 전에는 같은 사용자, Medium 범위(8192 이상, High 12288 미만), `TokenElevation=0`,
Administrators 그룹 비활성화를 검사한다. 자식은 suspended 상태에서 다시 검사한 뒤 시작하며,
Python harness도 자신의 토큰에서 이 조건을 독립적으로 확인한다. artifact에는 토큰 출처와
무결성/권한 상태를 기록하고 사용자 SID나 환경 변수 전체를 출력하지 않는다. 머신 정책,
계정, 앱 배포 설정, 브라우저 sandbox는 변경하지 않는다. 테스트 파일 접근은 현재 사용자에게만
부여한다.

이전 Windows 실행은 Medium SID 확인 뒤 WebView 생성 중 `0x80010108`로 중단되어 실제 UI
단계에 진입하지 못했다. 필터링된 토큰 방식은 로컬 C# 컴파일·8개 순수 권한 조건 검사와
Python harness 회귀 검사를 통과했으며, 실제 Win32 토큰 생성과 GUI 성공은 다음 Windows CI로
검증해야 한다. 권한 보강만으로 이전 HRESULT의 원인이 확정되거나 해결이 입증된 것은 아니다.
근거: [Microsoft의 권한 권고](https://learn.microsoft.com/microsoft-edge/webview2/concepts/security#recommended-privilege-level-for-webview2-host-applications),
[Tauri Wry 추적 이슈](https://github.com/tauri-apps/wry/issues/1782),
[Windows 제한 권한 task principal](https://learn.microsoft.com/powershell/module/scheduledtasks/new-scheduledtaskprincipal).

## 격리와 실제 검증 범위

- `tauri.e2e.conf.json` overlay의 identifier는 `io.github.jdeun.growwise.e2e`다. 테스트는 native
  `get_storage_location`이 이 identifier의 디렉터리를 반환하고 아이 목록이 비었는지 확인한 뒤
  합성 데이터를 작성한다. 일반 GrowWise 저장 위치에서는 실행을 거부한다.
- `--debug --no-bundle`로 프로덕션 프런트엔드와 실제 Rust 핸들러를 빌드한다. 디버그 Core 실행
  경로만 CI `.venv/Scripts/python.exe`로 연결하며 배포 sidecar 패키징 검사는 기존 workflow가 맡는다.
- AI·임베딩·vision·외부 enrichment를 끈다. 모델 품질이나 인터넷 서비스의 가용성을 이 테스트의
  성공으로 주장하지 않는다. 프로필 작성, 자료 생성·명시적 사용, 한 줄 결과 저장, PNG 선택·업로드·확정,
  작은 썸네일·원본 보존, 다자녀 격리, 로컬 백업을 실제 경로로 확인한다.
- WebView2 런타임을 찾아 정확한 버전을 우선 내려받고 Microsoft가 허용하는 앞 세 버전 요소가
  일치하는지 검사한다. 다운로드는 Microsoft HTTPS 주소만 사용하며 실행 전 Microsoft Authenticode
  서명을 검증한다. 런타임·드라이버 버전, 다운로드 URL, SHA256을 artifact에 기록한다.
- 실패 스크린샷·HTML·오류와 드라이버 로그를 보관한다. 종료 시 소유한 driver process tree만
  정리한다. 관리 Core의 PID가 종료됐는지도 검사하며, 살아 있으면 실패로 보고하고 정리한다.

## 실행

Windows에 WebView2·Rust 1.98.1·Node 22·Python 3.12가 준비된 환경에서:

```powershell
python -m pip install uv==0.12.13
$env:UV_PYTHON_INSTALL_DIR = Join-Path $env:TEMP 'growwise-native-python'
uv python install --no-bin --no-registry --python-downloads-json-url https://raw.githubusercontent.com/astral-sh/uv/901092ee11a89ba287f274e3c6e3a2e18ec2fba2/crates/uv-python/download-metadata.json 3.12.13
uv sync --locked --no-dev --managed-python --python 3.12.13
npm ci --prefix desktop
cargo install tauri-driver --version 2.1.0 --locked
./desktop/scripts/install_edge_webdriver.ps1 -Destination "$env:TEMP/growwise-edge-driver"
Push-Location desktop
npm run tauri -- icon ../assets/brand/growwise-symbol.svg
npm run tauri -- build --debug --no-bundle --config src-tauri/tauri.e2e.conf.json -- --locked
Pop-Location
./desktop/scripts/run_native_e2e.ps1 `
  -Python .venv/Scripts/python.exe `
  -App desktop/src-tauri/target/debug/growwise-desktop.exe `
  -NativeDriver "$env:TEMP/growwise-edge-driver/msedgedriver.exe" `
  -Artifacts desktop/artifacts/native-e2e
```

설치 스크립트는 GitHub Actions에서 `$GITHUB_ENV`를 통해 런타임 경로를 다음 step에 전달한다.
로컬 실행에서는 동일한 PowerShell 세션의 환경 변수도 설정한다. 합성 E2E 데이터는 `.e2e`
저장소에 남으므로 재실행은 새 Windows 사용자/일회용 CI runner에서 수행하거나 해당 테스트
저장소만 직접 정리한 뒤 수행한다. 테스트가 일반 앱 데이터를 자동으로 삭제하지 않는다.

실제 Windows 검증의 근거는 해당 커밋의 성공한 CI 실행과 `report.json`이다. 소스·프로토콜
단위 검사만으로 Windows GUI 통과를 주장하지 않는다. macOS GUI 실물 테스트 역시 이 검사에
포함되지 않는다.
