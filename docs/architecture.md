# 아키텍처

> **형태: 크로스플랫폼 데스크탑 앱(Tauri, 개인용 우선).** Windows·macOS에 설치해
> 오프라인 우선으로 동작한다. 홈서버·상시 백엔드는 1차 목표가 아니다.

## 최상위 원칙: LLM-enhanced, not LLM-dependent

GrowWise는 LLM을 적극 활용하지만 **LLM이 없어도 핵심 기능이 동작해야 한다.** Ollama가
설치되지 않았거나 모델이 내려가 있거나 추론이 timeout/실패해도 앱 전체가 사용 불능이
되어서는 안 된다.

모든 주요 기능은 두 층으로 설계한다.

```text
Deterministic Core Path
    ├─ CRUD / 기록 / 자료 관리
    ├─ Markdown SoT / SQLite projection
    ├─ 규칙 기반 validation
    ├─ lexical / metadata search
    ├─ 성장 지도 projection
    ├─ activity / material 상태 관리
    ├─ conversation session persistence
    └─ export
          ↓ optional
AI Enhancement Layer
    ├─ 자동 태깅·요약
    ├─ semantic embedding search
    ├─ query rewrite
    ├─ grounded synthesis
    ├─ 개인화 활동 제안
    └─ 생성·자동 리뷰
```

### Degraded mode 계약

- `llm_features_enabled=false`에서도 core CRUD/search/export는 정상 동작한다.
- 실행 중 provider가 죽어도 현재 원본 기록/자료 저장은 실패하지 않는다.
- embedding 실패 시 lexical/metadata 검색으로 자동 강등한다.
- query rewrite 실패 시 원래 사용자 질의를 그대로 사용한다.
- AI 요약/생성 실패는 원본 데이터 손실로 이어지지 않는다.
- 기능이 축소됐을 때 UI는 `AI 보강 기능 사용 불가`를 표시하되 앱 전체 오류처럼 표현하지
  않는다.
- AI 산출물은 항상 파생 데이터이며 Source of Truth가 아니다.
- CI에는 **LLM 없이도 주요 use case가 통과하는 테스트**를 유지한다.

## 핵심 실행 구조

GrowWise는 **LangChain + LangGraph**를 공식 오케스트레이션 기반으로 사용한다. 단, 이들은
GrowWise의 도메인 코어를 대체하지 않는다.

- **LangChain**: 모델 공급자, 프롬프트, structured output, retriever, tool/adapter 연결.
- **LangGraph**: 요청 라우팅, 상태 전이, 검토 게이트, 재시도·복구, human-in-the-loop,
  checkpoint/resume을 담당하는 실행 하네스.
- LangGraph를 이유 없이 멀티에이전트화하는 용도로 쓰지 않는다. 기능별 전문 노드는 둘 수
  있지만 기본은 명시적 상태 머신과 작은 책임의 노드 조합이다.
- deterministic core 기능은 LangChain/LLM 없이 호출 가능해야 한다.

```text
Desktop UI (Tauri + React/TypeScript)
        ↓ typed IPC
Tauri Rust Host
        ↓ authenticated ephemeral loopback HTTP
Application Core (Python / FastAPI sidecar)
        ↓
Use-case / Domain Core
        ├─ deterministic path ───────────────┐
        └─ optional LangGraph Workflow      │
             ├─ context builder             │
             │    ├─ Local RAG              │
             │    └─ External Adapters      │
             ├─ optional Model Provider     │
             ├─ Generator / Enricher        │
             ├─ Automated Review            │
             └─ Parent Review Gate          │
                                             ↓
                          Markdown SoT + SQLite projection
                                             ↓
                                       export / UI
```

외부 API와 LLM은 모두 **선택적 보강 계층**이다. 인터넷·모델이 없어도 기록·자료 관리·조회,
기본 검색, 상태 관리, projection, export는 동작해야 한다.

## Desktop product composition

React desktop은 **Shell → Product Hub → active feature** 계층으로 구성한다.

```text
WorkspaceShell
 ├─ WorkspaceNav
 ├─ shared topbar
 └─ active product workspace
      ├─ HomeDashboard
      ├─ ProfileWorkspaceHub
      ├─ LearningWorkspaceHub
      ├─ MaterialsWorkspaceHub
      ├─ PhotoActivityWorkspace
      ├─ Conversation
      ├─ Backup
      ├─ Settings
      └─ Help
```

원칙:

- 사용자 노출 navigation과 legacy/internal route를 분리한다.
- 이전 workspace 저장값은 migration하되 legacy 항목을 sidebar에 되살리지 않는다.
- 모든 feature를 동시에 mount한 뒤 global CSS로 숨기지 않는다.
- 현재 workspace에 필요한 feature만 실제 mount한다.
- Profile/Learning/Materials Hub가 자신의 tab/subview visibility를 소유한다.
- child-scoped async 작업은 active child + request generation을 함께 검증한다.
- production visual QA는 CI가 업로드한 실제 Vite `desktop/dist` artifact를 기준으로 수행한다.


## Desktop local trust boundary

Desktop 앱은 localhost에 떠 있는 임의의 프로세스를 GrowWise Core로 간주하지 않는다.

1. `CoreProcessManager`가 OS에 ephemeral loopback port를 요청한다.
2. OS CSPRNG로 매 실행 256-bit session token을 생성한다.
3. Core에 host/port/token과 OS app-data 경로를 환경변수로 전달한다.
4. Core는 desktop secure entrypoint에서 Bearer 인증 middleware를 활성화한다.
5. Rust host는 세션 토큰이 포함된 `/_desktop/handshake` 응답에서 product/protocol version을
   확인한 뒤에만 준비 완료로 본다.
6. 이후 모든 Rust → Core 요청은 같은 Bearer token을 기본 header로 사용한다.
7. 앱 종료 시 자신이 시작한 Core를 종료하고 메모리에 보관한 token 문자열을 비운다.

독립 개발용 `growwise` Core는 기본 `127.0.0.1:8765` API 계약을 유지한다. Desktop은 같은 API를
사용하되 `growwise.api.secure_entry`가 인증만 추가하므로 개발/배포 API가 서로 갈라지지 않는다.

## 상태 머신

생성 산출물의 상태는 UI 관례가 아니라 도메인 규칙으로 강제한다.

```text
DRAFT
  ↓
REVIEW_PENDING
  ├─→ REVISION_REQUESTED ─→ DRAFT
  ├─→ REJECTED
  └─→ APPROVED ─→ ARCHIVED
```

- `APPROVED` 이전 산출물은 아이에게 노출하거나 최종 PDF로 배포할 수 없다.
- automated review가 unavailable이면 이를 숨기지 않고 Parent Review로 넘기되 자동 검토
  미수행 상태를 명시한다.
- parent review는 LangGraph interrupt/resume으로 구현해 앱을 닫았다 열어도 이어갈 수 있게 한다.
- 모든 전이는 audit 가능한 event/log를 남긴다.

## 모듈 경계

| 모듈 | 책임 | 경로 |
| --- | --- | --- |
| App/API | Tauri ↔ Python 코어, IPC/API, health/session | `src/growwise/api/` |
| Workflow | LangGraph state/schema/nodes/edges/checkpoint | `src/growwise/workflows/` |
| Router | 요청 유형·연령·모드 분류 | `src/growwise/router/` |
| Generators | 독서·영어·탐방·수학·과학·글쓰기·영아 활동 생성 | `src/growwise/generators/` |
| Review | 자동 검토 + 부모 검토 정책 | `src/growwise/review/` |
| RAG | 교육과정·근거자료 검색·citation provenance | `src/growwise/rag/` |
| Storage | Markdown SoT / SQLite projection / rebuild | `src/growwise/storage/` |
| Export | HTML/CSS 및 PDF 출력 | `src/growwise/export/` |
| Adapters | 도서·지도·교육과정 등 외부 데이터 경계 | `src/growwise/adapters/` |
| Model | LangChain 기반 모델 공급자 추상화 | `src/growwise/model/` |
| Domain | Pydantic domain model, enum, invariant | `src/growwise/domain/` |
| Services | deterministic use case + optional AI enrichment | `src/growwise/services/` |

## Model Provider

모든 생성·검토·임베딩 호출은 특정 공급자 SDK를 직접 호출하지 않고 LangChain-compatible
provider 인터페이스 뒤에서 수행한다. **Provider는 nullable/optional dependency**다.

초기 어댑터:

1. Ollama(local default)
2. llama.cpp/OpenAI-compatible local endpoint
3. OpenAI-compatible remote endpoint
4. 필요 시 Anthropic/Google 등 추가

기능별 모델을 분리할 수 있다(`generation`, `review`, `embedding`). 원격 공급자는 부모가
명시적으로 활성화할 때만 사용하며 아동 데이터 전송 정책을 통과해야 한다.

### Provider failure policy

- startup 시 모델 연결 실패가 앱 startup 실패로 이어지지 않는다.
- chat/structured output과 embedding 호출에 bounded HTTP timeout을 둔다.
- consecutive failure circuit breaker를 둔다.
- 실패 횟수가 임계치를 넘으면 cooldown 동안 provider를 즉시 우회한다.
- cooldown 뒤 첫 호출은 half-open probe처럼 동작하며 성공 시 circuit을 reset한다.
- embedding exception/circuit-open은 lexical retrieval fallback으로 수렴한다.
- core use case는 provider 결과를 필수 반환값으로 요구하지 않는다.

## LangGraph 설계 원칙

### 기본 그래프

```text
START
 → normalize [deterministic]
 → route [deterministic first]
 → gather_context [deterministic retrieval available]
 → generate? [optional LLM]
 → validate_structure [deterministic]
 → review_safety [deterministic + optional LLM]
 → review_grounding [deterministic + optional LLM]
 → parent_review [interrupt]
      ├─ approve → persist → export? → END
      ├─ revise  → generate/fallback edit
      └─ reject  → persist_rejection → END
```

### 안정화

- 모든 노드는 typed state(Pydantic/TypedDict 계약)만 주고받는다.
- structured output은 JSON schema/Pydantic으로 검증한다.
- 재시도는 실패 유형별로 제한하고 무한 루프를 금지한다.
- deterministic node와 LLM node를 구분한다.
- **LLM node 실패가 가능한 경우 deterministic fallback edge를 둔다.**
- checkpoint를 통해 crash/restart 후 재개한다.
- idempotency key로 중복 저장·중복 export를 방지한다.
- create idempotency는 lease와 stable reserved resource ID를 사용해 crash 후 같은 ID로 수렴한다.
- timeout/cancellation/circuit breaker를 공급자 계층에 둔다.

### 적대적 검토

완료 조건은 happy-path 성공이 아니다. 각 workflow에 다음을 포함한다.

- malformed model output
- hallucinated source/citation
- prompt injection in retrieved/external content
- PII leakage
- age-inappropriate content
- answer-giving/scaffold violation
- provider outage/timeout
- provider absent / model not installed
- embedding outage
- corrupt Markdown/SQLite index
- offline mode
- duplicate/replayed request
- child switch 중 stale async response
- backup restore 후 stale live record

## RAG 장기 검색

RAG는 relevance와 recency를 혼합한 하나의 불투명 점수로 만들지 않는다.

1. lexical/vector relevance로 관련 후보를 만든다.
2. relevance 순서를 각 시간 tier 안에서 유지한다.
3. 현재 월 → 현재 연도 → archive → timestamp unknown 순서로 결과 limit을 채운다.
4. embedding 장애 시 동일 후보 집합을 lexical 기반으로 만들 수 있어야 한다.

따라서 최근이지만 무관한 기록이 오래된 관련 기록을 이기는 식으로 recency가 relevance를
제조하지 않는다.

## 저장

- **Markdown = Source of Truth**
- **SQLite = 재생성 가능한 projection/index**
- **LLM output = optional derived metadata/artifact**
- 모든 문서는 YAML frontmatter로 최소 메타데이터를 가진다.

```yaml
---
schema_version: 1
id: <uuidv7>
entity_type: learning_log
child_id: <uuidv7>
created_at: <ISO-8601>
updated_at: <ISO-8601>
---
```

SQLite 전체 삭제 뒤 Markdown만으로 동일한 projection을 복구할 수 있어야 한다. AI 파생
메타데이터가 없어져도 원본 기록의 의미와 기본 기능은 유지되어야 한다.

### 개인정보 삭제 lifecycle

`DELETE /v1/children/{child_id}`는 child profile만 삭제하지 않는다. 해당 child의 Markdown 정본과
`.md.bak`, SQLite projection, RAG chunks, conversation, background jobs, idempotency metadata,
observation/material-review checkpoint까지 함께 purge한다. 다른 child와 global/public resource는
보존한다.

기존 backup ZIP은 immutable historical snapshot으로 유지한다. 따라서 UI는 삭제 후에도 과거
backup에 개인정보가 남아 있을 수 있음을 알리고, 완전 폐기가 필요하면 해당 ZIP을 별도로
삭제하도록 한다.

## 기술 스택

- Desktop: Tauri 2 + React + TypeScript + Vite
- Python: 3.12+, uv, Pydantic v2, FastAPI
- Orchestration: **LangChain + LangGraph (optional AI workflow layer)**
- Persistence: Markdown + SQLite
- Local model default: Ollama, **optional**
- RAG: lexical/metadata baseline + optional embedding hybrid retrieval
- PDF: WeasyPrint 기본, Typst 보조
- Test: pytest + Vitest + Playwright
- Quality: Ruff + mypy + ESLint + Prettier
- CI: GitHub Actions Windows + macOS + Linux

## 데스크탑 패키징

Tauri가 Python 코어를 sidecar로 실행한다. Python 코어는 PyInstaller로 독립 실행 파일을 만들고
플랫폼별 Tauri bundle에 resource로 포함한다. 모델은 앱과 분리하며 **모델 설치를 앱 실행의
전제조건으로 두지 않는다.** 모델이 없는 첫 실행에서도 기본 기능을 사용할 수 있어야 한다.

패키지 CI는 sidecar를 build한 뒤 랜덤 port/token으로 실제 실행해 unauthenticated 요청 거부와
인증 handshake를 smoke-test한다. Python/Node/Rust toolchain과 lockfile을 고정하고 외부 GitHub
Actions도 commit SHA로 pin한다.

OS-native print/PDF가 현재 공식 승인 자료 출력 경로다. 자세한 결정은 관련 ADR을 따른다.

## 전체 완성 목표

초기 milestone은 작게 자르지만 제품 목표는 축소하지 않는다. 최종적으로 0세~고등 전 연령,
영아 상호작용·자료 생성·학습 기록·성장 지도·퀘스트·RAG·외부 연동·PDF·중고등 트래킹을
모두 구현한다. 각 기능은 구현 후 안정화, 적대적 테스트, dependency/license/security 위생,
문서화까지 통과해야 완료로 본다.

구체적인 production invariant와 merge 전 검증 목록은
[`docs/hardening-contracts.md`](hardening-contracts.md)를 따른다.
