# Hardening contracts

이 문서는 GrowWise의 장기 안정성·개인정보·로컬 데스크톱 신뢰 경계에 대한 **구현 계약**을 정리한다.
설계 의도가 아니라 회귀 테스트와 CI로 유지해야 하는 제품 invariant를 기록한다.

## 1. Desktop ↔ Core 신뢰 경계

배포용 Tauri 앱은 고정 `localhost:8765` Core를 신뢰하지 않는다.

- 데스크톱 시작 시 OS가 배정한 ephemeral loopback port를 사용한다.
- 매 실행마다 OS CSPRNG로 256-bit 세션 토큰을 생성한다.
- Python sidecar에는 port, token, OS app-data 경로를 환경변수로 전달한다.
- 데스크톱 sidecar는 모든 HTTP 요청에 `Authorization: Bearer <session-token>`을 요구한다.
- readiness는 단순 TCP connect가 아니라 인증된 `/health` + GrowWise protocol handshake로 확인한다.
- Tauri IPC는 사용자가 입력한 URL을 받지 않고 프로세스 매니저가 만든 endpoint/token만 사용한다.
- Rust HTTP 오류 본문은 UI 오류 문자열로 전달하기 전에 크기를 제한한다.
- 일반 개발용 Core API 계약은 유지하고, desktop 전용 secure entrypoint가 인증 middleware만 추가한다.

회귀 증거:

- `desktop/scripts/smoke_core_sidecar.py`
- `tests/test_desktop_security.py`
- Desktop Package / `core-sidecar-smoke` CI

## 2. Markdown Source of Truth와 복구

- Markdown record가 정본이다.
- SQLite index/RAG/checkpoint는 재생성 또는 삭제 가능한 파생 상태다.
- Markdown write는 temp file + fsync + atomic replace로 수행한다.
- 기존 generation은 `.md.bak` 한 세대를 남겨 명시적 복구가 가능해야 한다.
- SQLite rebuild 중 hard failure가 발생하면 이전 projection을 보존한다.
- restore는 같은 filesystem의 임시 rollback state로 현재 live 상태를 보호한 뒤 swap한다.
- managed backup format v2는 Markdown record, managed asset, conversation SQLite snapshot을 함께 보존한다.
- v1 archive restore는 해당 시점에 conversation state가 없던 것으로 취급해 현재 conversation을 비운다.
- restore는 선택한 ZIP을 immutable 임시 snapshot으로 복사하고 전체 preflight를 통과한 뒤에만 destructive cleanup을 시작한다.
- restore 전 pre-restore jobs/idempotency/checkpoint projection을 제거해 이전 generation 실행 상태를 남기지 않는다.
- restore 성공 후 archive에 존재하지 않는 이전 live record/conversation/RAG projection을 남기지 않는다.
- RAG rebuild 실패는 정본 restore를 되돌리지 않고 명시적 degraded 상태로 보고한다.

## 3. Idempotency와 crash recovery

Create 계열 retry는 같은 요청을 다른 entity로 중복 생성하지 않는다.

- idempotency key는 request fingerprint와 결합한다.
- 최초 claim 때 stable resource ID를 예약한다.
- `PENDING` claim은 lease를 가진다.
- 프로세스 crash/abandoned request 뒤 lease가 만료되면 **같은 reserved resource ID**로 재획득한다.
- 정본이 이미 commit된 상태라면 retry가 이를 찾아 claim을 completed로 수렴시킨다.
- 같은 key를 다른 payload/resource type에 재사용하면 conflict다.

## 4. Child scope 격리와 async race

다자녀 전환에서 이전 아이의 늦은 response가 새 아이 화면에 commit되어서는 안 된다.

- child-context request generation과 active child ID를 모두 검증한다.
- child switch 시 child-scoped search/conversation/guidance/material/activity state를 초기화한다.
- mutation 이후 partial reload도 원래 child scope가 현재 scope와 일치할 때만 commit한다.
- search, conversation, infant guidance처럼 공통 reload helper를 통하지 않는 async 경로도 같은 규칙을 따른다.

회귀 증거:

- `desktop/src/child-context-state.ts`
- `desktop/src/child-context-state.test.ts`

## 5. 개인정보 삭제권

`DELETE /v1/children/{child_id}`는 profile 한 줄 삭제가 아니다. 한 아이의 **live data lifecycle 전체 purge**다.

삭제 대상:

- child profile 및 `child_id`가 같은 Markdown 정본
- 해당 정본의 `.md.bak`
- SQLite projection
- child-owned RAG chunks
- conversation sessions/turns
- background jobs whose payload references the child
- 해당 child entity에 연결된 idempotency metadata
- observation workflow thread checkpoints
- child material review checkpoints

보존 대상:

- 다른 child의 정본/파생 데이터
- global/public resource
- 과거 사용자가 만든 backup ZIP

과거 backup ZIP은 변경하지 않는다. immutable snapshot의 의미를 보존하기 위해서다. 따라서 UI는 삭제 후에도 과거 backup에 해당 아이 데이터가 있을 수 있음을 명시한다. 사용자가 완전 폐기를 원하면 해당 과거 ZIP도 삭제해야 한다.

Desktop UX는 삭제할 child를 선택하고 해당 nickname을 다시 입력해야 실행된다. 성공 후 전체 UI reload로 모든 in-memory child scope를 폐기한다.

회귀 증거:

- `src/growwise/services/privacy.py`
- `tests/test_child_purge.py`
- `tests/test_privacy_api.py`
- `desktop/src/features/DataManagementSection.tsx`

## 6. RAG 시간 계층과 fallback

장기간 기록에서 오래된 자료가 최근 맥락을 무작위로 밀어내지 않도록 relevance와 time navigation을 분리한다.

1. lexical/vector relevance로 후보를 만든다.
2. relevance order를 각 tier 안에서 보존한다.
3. current month → current year → archive → unknown timestamp 순서로 limit을 채운다.
4. 최근이지만 관련 없는 chunk는 후보에 들어오지 않으므로 recency가 relevance를 제조하지 않는다.
5. embedding 실패/timeout/circuit-open 시 lexical search로 즉시 강등한다.

## 7. Model provider failure policy

AI는 optional dependency다.

- Chat/structured generation에 bounded HTTP timeout을 둔다.
- embedding에도 별도 bounded timeout을 둔다.
- consecutive failure circuit breaker를 사용한다.
- threshold 이상 실패하면 cooldown 동안 provider 호출을 즉시 거절해 반복 timeout을 피한다.
- cooldown 뒤 첫 요청은 half-open probe처럼 동작한다.
- 성공하면 failure count와 open state를 reset한다.
- caller는 provider exception을 데이터 손실로 연결하지 않고 deterministic/template/lexical fallback을 사용한다.

관련 설정:

- `GROWWISE_MODEL_TIMEOUT_SECONDS`
- `GROWWISE_MODEL_CIRCUIT_FAILURE_THRESHOLD`
- `GROWWISE_MODEL_CIRCUIT_RECOVERY_SECONDS`
- `GROWWISE_EMBEDDING_TIMEOUT_SECONDS`

## 8. 입력/저장 위생

저장 가능한 도메인 모델이 API DTO보다 강한 마지막 경계다.

- 사용자 텍스트에는 목적별 최대 길이를 둔다.
- list/dict field에는 최대 원소 수를 둔다.
- tag/source ref/language/provenance key/value 길이를 제한한다.
- invalid domain payload는 desktop secure API에서도 422로 수렴시킨다.
- 오류 응답을 UI에 전달할 때 무제한 body를 그대로 포함하지 않는다.

목표는 메모리/디스크 폭주, pathological prompt, 거대한 local IPC payload가 장기 데이터베이스에 들어가는 것을 입구에서 차단하는 것이다.

## 9. 공급망과 재현성

- Python: `uv.lock`, `uv sync --locked`, `uv lock --check`, uv version pin.
- Node: `package-lock.json`, `npm ci`, npm version pin, `npm audit`.
- Rust: `Cargo.lock`, `cargo --locked`, root `rust-toolchain.toml`로 Rust 1.98.1 pin.
- Rust advisory scan: `cargo-audit 0.22.2` pin.
- GitHub Actions: third-party action은 mutable major tag가 아니라 검증한 commit SHA로 pin하고 주석에 major version을 기록한다.
- secret scan은 full history를 검사한다.
- sidecar packaging은 build 후 authenticated runtime smoke를 통과해야 한다.

## 10. Definition of Done

하드닝 변경은 코드가 존재하는 것으로 끝나지 않는다. 최종 merge 전 다음이 모두 green이어야 한다.

- Ruff
- mypy
- pytest
- Python vulnerability audit/license inventory
- ESLint
- Vitest
- TypeScript/Vite build
- npm audit
- `cargo fmt --check`
- `cargo check --locked`
- Clippy `-D warnings`
- cargo-audit
- authenticated PyInstaller sidecar smoke
- Windows NSIS validation package
- macOS arm64 DMG validation package
- macOS x64 DMG validation package
- secret scan

실제 stable 배포의 code signing/notarization/updater trust-root 검증은 운영자 credential이 필요한 별도 operator evidence다.
