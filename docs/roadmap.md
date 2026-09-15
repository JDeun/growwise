# 로드맵

## 최종 목표

GrowWise는 작은 MVP에서 멈추는 프로젝트가 아니다. **0세부터 고등학교까지** 부모가 아이의
학습과 성장을 지원할 수 있는 완성형 크로스플랫폼 데스크탑 오픈소스를 목표로 한다.

최종 완성 범위:

- 영아(0~2): 놀이·상호작용 제안, 보드북 추천, 부모 관찰 기록, 경험 커버리지 성장 지도
- 유아·초등: 독서·영어·탐방·수학·과학·글쓰기 자료 생성, 활동 퀘스트, 기록
- 중·고: 학습 진도·약점 지도·오답/회고·자원 추천·부모 지원 포인트
- 다자녀 프로필/전환
- Markdown SoT + SQLite projection/rebuild
- LangChain + LangGraph 기반 생성/RAG/검토 workflow
- 모델 공급자 교체(Ollama/local/OpenAI-compatible 등)
- Parent Review human-in-the-loop
- 성장 지도/경험 커버리지
- 외부 데이터 adapter + offline cache/fallback
- PDF/인쇄 출력
- 개인정보·보안·라이선스·attribution
- Windows/macOS 설치/업데이트/CI
- 안정화·적대적 테스트·위생·문서화

마일스톤은 위험을 관리하기 위해 작게 자르지만 **기능 범위를 포기하기 위한 v1 축소는 하지
않는다.** 각 단계는 다음 단계를 위한 기반이며 최종 체크리스트가 모두 닫힐 때까지 계속한다.

> 체크 표시는 코드가 존재하는지만 보지 않고 현재 Definition of Done을 보수적으로 적용한다.
> 부분 구현은 `[ ]`로 유지하고 현재 상태를 괄호로 기록한다.

## 왜 0~2세부터 시작하는가

첫 실사용 대상은 **현재 생후 9개월 아이를 둔 부모가 실제 일상에서 사용할 수 있는 영아
모드**다. 따라서 0~2세 지원은 임의로 고른 데모 범위가 아니라 다음 장점이 있는 첫 검증
도메인이다.

1. 실제 가정에서 즉시 dogfooding할 수 있다.
2. 아이 대면 UI 없이 부모 보조라는 제품 철학을 가장 명확히 검증한다.
3. 발달을 점수화하지 않고 관찰·경험 커버리지로 기록하는 데이터 모델을 초기에 검증한다.
4. 생성 품질뿐 아니라 장기간 기록의 유용성을 실제 사용으로 확인할 수 있다.

단, 영아 모드에 갇히지 않는다. 영아 vertical slice가 기반을 검증하면 유아·초등 생성 트랙,
중·고 트래킹까지 순차 확장한다.

## 확정된 기술/제품 결정

- 개인용 홈스쿨링 데스크탑 앱 우선
- Windows + macOS 동시 지원
- Tauri 2 + React/TypeScript UI
- Python 3.12+ sidecar
- **LangChain + LangGraph 공식 채택**
- LangGraph는 상태 머신·human-in-the-loop·checkpoint/recovery 실행 하네스로 사용
- Markdown = Source of Truth, SQLite = 재생성 가능한 projection/index
- UUIDv7 계열 안정 ID + schema versioning
- 모델 독립성: local default, provider adapter로 교체
- **LLM-enhanced, not LLM-dependent**: LLM/임베딩 장애 시에도 핵심 CRUD·검색·트래킹·템플릿 생성은 동작
- 아이 대면 챗봇 없음
- Parent Review 승인 전 최종 사용/export 금지
- 다자녀 `child_id` 분리
- 성장 지도는 성취 점수가 아니라 self-vs-self 경험/관찰 커버리지
- permissive/commercial-safe dependency 우선
- offline-first, external enrichment optional

## Phase 0 — Foundation / Walking Skeleton

### 프로젝트 기반

- [x] `pyproject.toml` + uv dependency management (`uv.lock`, uv 0.12.13, CI `uv sync --locked`/`uv lock --check`)
- [x] Tauri 2 + React/TypeScript/Vite shell
- [x] Python FastAPI sidecar + health/runtime endpoint
- [x] typed IPC contract
- [x] Windows/macOS GitHub Actions
- [x] Ruff/mypy/pytest + ESLint/TypeScript/Vitest
- [x] pre-commit / dependency audit / license inventory

### Domain/Storage

- [x] UUIDv7 entity IDs
- [x] schema version
- [x] Pydantic domain entities
- [x] `MaterialStatus` state machine
- [x] Markdown YAML-frontmatter repository
- [x] atomic write + backup/recovery
- [x] SQLite projection
- [x] Markdown → SQLite deterministic rebuild
- [x] migration/version compatibility tests

### LangGraph runtime

- [x] typed graph state
- [x] node registry
- [x] checkpoint persistence
- [x] retry/timeout/cancellation policy
- [x] idempotency (SQLite claim/complete/release + schema migration + observation API `Idempotency-Key` 회귀 테스트)
- [x] interrupt/resume parent review skeleton (SQLite checkpoint 기반 LangGraph interrupt/resume 회귀 테스트)
- [x] provider abstraction + Ollama adapter

**Phase 0 상태: 완료.**

## Phase 1 — 영아(0~2) 실사용 모드

- [x] 다자녀 프로필/아이 전환
- [x] 월령/단계 기반 놀이·상호작용 제안
- [x] 표준보육과정 기반 관찰 힌트 (2024 개정 0~2세 5개 영역 + 비진단 fallback/회귀 테스트)
- [x] 비진단/비비교 가드레일
- [x] 보드북/책 읽어주기 추천 (child/global local resource 우선 + deterministic offline fallback)
- [x] 활동 퀘스트(제안/진행/완료/건너뜀)
- [x] 부모 자유 관찰 기록
- [x] learning log
- [x] 경험 커버리지 태깅
- [x] 3층 성장 지도 기초
- [x] LLM 없이 핵심 기능 동작(Core-only degraded mode)
- [x] export/import/backup (portable ZIP backup/restore + Desktop import/export UX + safety backup)

**남은 Phase 1 검증:** 실제 가정 dogfooding. 개인 실사용 데이터는 저장소에 넣지 않는다.

## Phase 2 — 생성 Vertical Slice

```text
input → router → RAG/context → optional LLM → structured material
 → automated review → parent review → Markdown/SQLite → print/PDF → learning log
```

- [x] 독서 1종 end-to-end 회귀 (resource provenance → reading material → revision → approval)
- [x] LangChain structured output
- [x] grounding/citation provenance 기초 + 존재/child-scope source guard
- [x] scaffold guard (ScaffoldGuard — direct-answer/rote/injection/pii/age/stereotype)
- [x] prompt injection defense 회귀 세트 (`test_material_prompt_injection.py`, `test_scaffold_adversarial.py`)
- [x] Parent Review interrupt/resume를 material workflow 동일 thread로 통합 (`workflows/material_pipeline.py`)
- [x] revision loop (수정 요청 → deterministic/optional-AI 새 immutable version → 재검토)
- [x] 부모 직접 편집 + immutable version 관리 + 동시 successor race guard
- [ ] 전용 PDF renderer/packaging 결정 (현재 OS print/PDF 경로)
- [ ] local model latency/quality benchmark (하네스 `scripts/benchmark_model.py` 완료; 실측·로컬/원격 결정=운영자)
- [ ] 최소/권장 하드웨어 benchmark (하네스 `scripts/benchmark_hardware.py` 완료; 실기기 실측=운영자)

## Phase 3 — 유아·초등 전체 생성 기능

- [ ] 독서 활동지 제품 UX 완성 (Core vertical slice는 구현)
- [ ] 영어 대화 카드 제품 UX 완성
- [ ] 탐방/여행 활동지 제품 UX 완성
- [ ] 수학 놀이 제품 UX 완성
- [ ] 과학 탐구 제품 UX 완성
- [ ] 글쓰기·말하기 코치 제품 UX 완성
- [ ] 그림/표/도형 등 출력 컴포넌트
- [ ] curriculum mapping
- [x] 활동 템플릿 라이브러리 확장 (`generators/templates.py` — kind별 5변형, 결정적 선택)
- [x] 생성물 편집/재생성/immutable 버전 관리
- [ ] 인쇄 레이아웃 설정
- [ ] source/citation 표시 완성

## Phase 4 — 성장 지도 / 퀘스트 / 장기 기록

- [x] 전인 고정축 기초
- [x] 학습 6축 기초
- [x] 연령 적응형 stage-focus layer 기초
- [x] 기간별 경험 커버리지
- [x] 활동 다양성/편중 탐지 기초 (sparse-data guard 포함 qualitative diversity)
- [x] 다음 활동 추천 기초(영아)
- [x] 퀘스트 추천/보류/완료/회고 상태 기반
- [x] 검색/필터/타임라인 기초
- [x] Markdown 묶음 portable export (백업 서비스: Markdown 레코드 zip 아카이브)

랭킹·레벨·또래 비교·강제 streak는 넣지 않는다.

## Phase 5 — 중·고 학습 트래킹

Core/API + Markdown SoT/SQLite projection 기준 기능은 완료됐다. Desktop 전용 UX와 실사용 검증은
제품화 단계에서 계속한다.

- [x] 과목/단원 진도
- [x] weakmap
- [x] 오답/실수 유형
- [x] 학습 회고
- [x] 자원 추천
- [x] 부모 지원 포인트
- [x] 자기설명/근거검증 로그
- [x] 시험 대비 계획(압박형 gamification 없이)

## Phase 6 — Integrations

- [x] 도서관 정보나루(Data4Library) adapter
- [ ] 교육과정/공공 교육자료 adapter
- [x] OpenStreetMap/Overpass adapter
- [x] 외부 metadata/image license filtering (`adapters/license_filter.py`; 어댑터 배선은 상류 per-item 라이선스 필드 생기면)
- [x] cache TTL / stale fallback
- [x] offline fixture/회귀 테스트
- [x] attribution/NOTICE 자동 생성 (`scripts/generate_notice.py` → THIRD_PARTY_NOTICES.md)

외부 adapter는 아이 관찰/개인 기록을 전송하지 않고 public query만 사용하며, 장애 시 local core를
깨뜨리지 않는다.

## Phase 7 — Desktop Productization

- [x] Windows installer CI (NSIS)
- [x] macOS app/dmg CI (Apple Silicon + Intel)
- [ ] 실제 배포용 code signing/notarization 자격증명/자동화
- [ ] Tauri updater
- [x] 모델 다운로드/삭제/무결성 검증 (`model/registry.py` — 원자적 쓰기+sha256 검증)
- [x] storage location 관리 (`storage/location.py` — 검증+안전 relocate)
- [x] backup/restore/import/export Desktop UX
- [x] Core sidecar package/smoke + crash-safe start/stop 기초
- [x] crash recovery 전체 (`test_crash_recovery.py`; 손상 인덱스/부분 레코드 복구 하드닝)
- [ ] accessibility
- [ ] keyboard navigation
- [ ] localization 기반

## Phase 8 — 완성도 강화

### 안정화

- [x] unit/integration/e2e/property tests (e2e `test_e2e_api_flow.py`, property `test_markdown_roundtrip_property.py`)
- [x] workflow replay tests (리뷰 그래프 재시작-재개, `test_interrupted_recovery.py`)
- [x] Core-only / provider failure fallback tests 기초
- [x] corrupt Markdown/DB recovery 기초
- [x] interrupted export/review recovery (재시작 후 체크포인트 재개 + export 원자성, `test_interrupted_recovery.py`)
- [x] long-running soak tests (`test_soak_generation.py` — 1500 사이클 안전 가드)
- [x] performance/memory profiling (`test_performance_smoke.py` — 시간·피크메모리·누수 가드)

### 적대적 리뷰

- [x] prompt injection (ScaffoldGuard `_INJECTION_PATTERNS` + boundary enforcement, `test_material_prompt_injection.py`)
- [x] malicious retrieved content 기초 (`test_rag_adversarial.py`, hardened material adversarial guard)
- [x] citation/source fabrication 기초 (material source refs existence/scope 검증)
- [x] PII leakage (ScaffoldGuard `_PII_PATTERNS` reject, `test_material_pii_guard.py`)
- [x] age-inappropriate generation (ScaffoldGuard `_AGE_UNSAFE_PATTERNS`, PR #24 병합)
- [x] diagnostic/medical-like infant claims 회귀 기초
- [x] stereotype/bias (ScaffoldGuard `_STEREOTYPE_PATTERNS` — 규정적 고정관념 차단, `test_scaffold_stereotype.py`)
- [x] answer-giving/scaffold violations (ScaffoldGuard `_DIRECT_ANSWER_PATTERNS`/rote-pressure, `test_scaffold_adversarial.py`)
- [x] malformed structured output (empty/whitespace/oversized/control-char draft → 결정적 템플릿 폴백, `test_material_malformed_output.py`)
- [x] path traversal/file corruption attempts 기초
- [x] external API failure/stale fallback 기초
- [x] concurrent immutable-version race 회귀

### 위생

- [x] TODO/FIXME audit (현재 코드 검색 기준 잔여 없음)
- [x] dependency lock/update policy 기초(`uv.lock`, `package-lock.json`, `Cargo.lock`, Dependabot)
- [x] Python/Node/Rust CVE audit CI
- [x] secret scan (Gitleaks workflow)
- [x] Python license inventory CI
- [x] docs/code consistency audit (`test_docs_code_consistency.py` — 로드맵 코드참조 검증)
- [x] sample/test data privacy audit (`test_repo_privacy_audit.py` — 구조적 전화/주민번호 + GROWWISE_PII_DENYLIST 실명 감사)
- [x] reproducible dependency resolution where practical (`uv sync --locked`, `npm ci`, Cargo `--locked`)

## Definition of Done

기능은 코드가 존재한다고 완료가 아니다. 다음을 모두 만족해야 한다.

1. 실제 사용자 흐름에서 동작
2. unit + integration + 필요한 e2e test 통과
3. offline/failure path 존재
4. privacy/safety policy 준수
5. adversarial case 통과
6. dependency/license hygiene 통과
7. 문서와 실제 동작 일치
8. Windows/macOS에서 검증

이 기준으로 **전 기능 완료**를 목표로 한다.
