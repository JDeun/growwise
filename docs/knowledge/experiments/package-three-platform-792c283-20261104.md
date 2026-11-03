# 세 플랫폼 패키지 검증 — 792c283 / 2026-11-04

`792c28367c0a1549027f0f14289b359c36eeb831`의
[Desktop Package 실행](https://github.com/JDeun/growwise/actions/runs/41666654868)이 성공했다.
Windows NSIS, macOS ARM·Intel DMG와 SBOM 작업이 모두 통과했다.
PR 실행이므로 실제 GitHub Release 게시 작업은 건너뛰었다.
이 기록은 생성된 파일과 실제 포함 Core를 검증한 범위를 보존한다.
[JSON](package-three-platform-792c283-20261104.json)에 파일 해시와 세부 결과가 있다.

| 플랫폼 | 실제 CI 결과 | 포함 라이선스 항목 |
| --- | --- | --- |
| [Windows x64](https://github.com/JDeun/growwise/actions/runs/41666654868/job/126023664113) | 14분 6초, 업데이트 보호 테스트 3개·Core 빌드·인증/사진 검사·NSIS 생성/업로드 성공 | 374 |
| [macOS ARM64](https://github.com/JDeun/growwise/actions/runs/41666654868/job/126023664123) | 9분 48초, 업데이트 보호 테스트 3개·Core 빌드·인증/사진 검사·ad-hoc 앱/DMG 생성/업로드 성공 | 376 |
| [macOS Intel](https://github.com/JDeun/growwise/actions/runs/41666654868/job/126023663723) | 18분 23초, 업데이트 보호 테스트 3개·Core 빌드·인증/사진 검사·ad-hoc 앱/DMG 생성/업로드 성공 | 377 |

모든 플랫폼에서 검토된 Python **3.12.16 / 배포판 20261026**과 실제 PyInstaller 사용 버전을
확인했다. 라이선스 수는 Python·Node·Rust·표준 라이브러리 등을 합친 플랫폼별 항목 수다.
각 업데이트 전용 실행은 실패·무시 0개였으며, 그 모듈 밖 테스트는 필터링됐다.
실제 Core 검사는 인증 없는 접근 거부, 인증된 handshake/상태 조회,
합성 PNG 업로드와 JPEG 썸네일 생성을 포함한다. AI 추론은 실행하지 않았다.

## 독립적으로 내려받은 설치 파일

다음 크기와 SHA-256은 CI 출력의 해시를 복사한 값이 아니라 다운로드한 파일에서 계산했다.

| 파일 | 바이트 | SHA-256 |
| --- | ---: | --- |
| `GrowWise_0.1.0-alpha.0_x64-setup.exe` | 31,936,826 | `1c0328743d931b86fd30f1c5cd645c2fe240d9939fbab1384020ec657a607721` |
| `GrowWise_0.1.0-alpha.0_aarch64.dmg` | 30,459,185 | `a9c55a26cd50105e5d07b5825715544d2fa6490d966c5f102d249d6f1f4fe6c9` |
| `GrowWise_0.1.0-alpha.0_x64.dmg` | 32,057,144 | `c33b7b396a3074201b72c87af3361063f482ea2683f5ed38db1514a3edbf45d2` |

- Windows 파일은 PE·NSIS 형식 표식과 인증서 디렉터리 `0/0`을 확인했다.
  Windows 설치 파일을 macOS에서 실행하거나 설치하지 않았다. 디지털 서명은 주장하지 않는다.
- 두 DMG를 읽기 전용으로 연결해 앱의 `codesign --verify --deep --strict`와 실제 포함
  라이선스 목록·파일 해시 검사를 통과했다. 각각 ARM64·x86_64이며 서명은 ad-hoc,
  TeamIdentifier는 없었다. 검사 후 이미지를 모두 해제했다.
- ARM 앱의 **실제 포함 Core**를 직접 실행해 인증·상태 조회·PNG→JPEG 검사를 다시 통과했다.
  Intel Core는 실제 Intel CI에서 실행됐고, 로컬 ARM 컴퓨터에서는 실행하지 않았다.
- 두 앱의 Core 실행 파일과 라이선스 manifest도 별도로 해시했다. 상세 값은 JSON에 있다.

## 현재 트리와의 관계

기록 시점의 로컬 HEAD `ecaf711cab0e37f4f7e024170a97f06a07987ae9`와 비교해
제품 Core·프런트엔드·Tauri 소스, 잠금 파일·매니페스트, 브랜드·라이선스 자산,
패키징 설정·빌드 도구의 변경이 없음을 확인했다. 검사한 경로 범위와 빈 차이 목록을 JSON에 남겼다.
추가된 네이티브/브라우저 검증 도구의 성공 여부는 별도 근거다.

이 기록은 실제 GUI 조작, 교육 효과, Developer ID 서명, notarization,
정식 Authenticode 서명이나 업데이트 배포 키 검증을 뜻하지 않는다.
[이전 b074175 Windows 기록](windows-package-validation-20261104.md)과
[이전 런타임 보안 검토](python-runtime-security-20261103.md)는 수정하지 않고 보존한다.

개인정보 검토: 공개 CI 주소, 버전, 합성 검사 결과와 파일 해시만 포함한다.
가정 기록·자격증명·사용자 SID·개인 기기 경로·원본 작업 로그는 포함하지 않는다.
