<p align="center">
  <img src="assets/brand/growwise-logo.svg" alt="GrowWise" width="320">
</p>

<p align="center">
  <strong>아이의 성장을 기록하고, 필요한 교육 자원을 찾고, 부모의 교육 철학에 맞는 자료를 만든다.</strong><br>
  Local-first, parent-centered Personal Education OS.
</p>

<p align="center">
  <a href="https://github.com/JDeun/growwise/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/growwise/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/growwise/actions/workflows/package.yml"><img alt="Desktop Packages" src="https://github.com/JDeun/growwise/actions/workflows/package.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/growwise/actions/workflows/secret-scan.yml"><img alt="Secret Scan" src="https://github.com/JDeun/growwise/actions/workflows/secret-scan.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0a0-informational.svg">
</p>

> [!IMPORTANT]
> **현재 상태: pre-1.0 / 활발한 구현 단계.** 소스와 CI 기반 unsigned 데스크탑 빌드는 사용할 수
> 있지만 code signing/notarization을 거친 공식 signed public release는 아직 없다. GrowWise는
> 발달 진단·평가 도구가 아니며, 생성물은 Parent Review 이후 사용한다.

> [!NOTE]
> **Local-first.** 아동 데이터의 정본은 로컬 Markdown에 저장하고 SQLite는 재생성 가능한
> projection/index로 사용한다. LLM과 외부 API는 보강 기능이며 핵심 기록·검색·백업의 필수재가 아니다.

GrowWise는 챗봇이나 단순 육아 일기장이 아니다. 부모가 아이의 실제 경험을 장기적으로 기록하고,
기록 사이의 관계를 연결하고, 현재 맥락과 관련된 공개 교육 자원을 찾고, 그 근거를 사용해 활동지나
탐구 자료를 만드는 **개인용 교육 운영 시스템**이다.

> **모토:** AI가 아이를 대신해 가르치는 것이 아니라, 부모가 자신의 교육 철학에 따라 아이를
> 이해하고 돕기 위해 필요한 기록·자료·맥락을 관리하도록 돕는다.

---

## 가장 중요한 사용 흐름

```text
관찰·사진 기록
      ↓
문서 연결 / 장기 맥락
      ↓
공개 교육 자원 발견
      ↓
부모가 필요한 후보만 라이브러리에 저장
      ↓
저장 근거 + 아이 맥락으로 교육자료 생성
      ↓
Parent Review / 직접 수정 / 승인
      ↓
활동 → 후속 관찰 → 다시 장기 기록
```

AI가 없어도 이 흐름의 기록·연결·lexical 검색·공식 교육과정 메타데이터·라이브러리·템플릿 자료 생성은
동작한다. AI가 있으면 태깅, semantic retrieval, 이미지 캡션, 질의 재작성, 자료 개인화 등을 보강한다.

## 현재 데스크톱 작업공간

사용자에게 노출되는 사이드바는 다음 9개 작업공간으로 정리되어 있다.

| 화면 | 사용자가 하는 일 | 주요 하위 기능 |
| --- | --- | --- |
| **대시보드** | 현재 아이와 최근 상태 확인 | KPI, 최근 활동, 오늘의 추천 |
| **아이 프로필** | 아이 정보와 장기 흐름 확인 | 학습 기록, 발달 분석, 성장 리포트 |
| **학습 기록** | 배움의 결과·과정·관찰 기록 | 학습 기록, 관찰 기록, 중·고 학습 트래커 |
| **자료실** | 활동 자료와 근거 자료 관리 | 활동 자료, 활동 관리, 참고 자료, 자료 찾기 |
| **사진첩** | 사진 중심 기록 관리 | 갤러리, 필터, 상세 보기, 새 사진 기록 |
| **대화하기** | 기록/자료를 근거로 검색·후속 질문 | 대화 목록, 대화 본문, 백업 보조 패널 |
| **백업 및 복원** | 로컬 데이터 snapshot 관리 | 생성, 내보내기, 가져오기, 복원, 이력 |
| **설정** | 앱 상태·가족 프로필·개인정보 관리 | 상태, 프로필 편집, 삭제 |
| **도움말** | 사용법과 데이터 원칙 확인 | 시작하기, AI/데이터 원칙, 단축키, 문제 해결 |

이전의 관찰/성장/활동/발견/라이브러리/검색 기능은 사라진 것이 아니라 각각 위 상위 작업공간의 탭·하위 기능으로 흡수됐다. 상세한 단계별 사용법은 **[docs/user-guide.md](docs/user-guide.md)**를 참고한다.
---

## 사진첩: AI가 없어도 사진 일기처럼

사진 기록은 AI 기능이 아니라 **기록 기능**이 우선이다.

```text
사진 선택
  + 부모가 직접 쓴 글
       ↓
AI 보조 OFF ───────────────→ 즉시 부모 검토 초안
       │
AI 보조 ON
       ↓
로컬 durable background job
       ↓
Vision caption + 기록 초안 보강
       ↓
부모 검토 / 수정
       ↓
LearningLog 확정
```

- JPEG/PNG/WebP 파일 크기·MIME·이미지 무결성을 확인한다.
- 사진 원본은 로컬 managed asset으로 저장하고 DB에는 hash·경로·메타데이터 관계를 저장한다.
- 정확한 사진 GPS는 기본 보존하지 않는다.
- 느린 로컬 VLM은 HTTP 요청을 붙잡지 않고 background worker에서 처리한다.
- 앱이 종료되면 durable job queue에서 중단 작업을 다음 실행에 복구한다.
- AI가 반복 실패해도 사진과 부모 글을 잃지 않고 직접 기록 가능한 draft로 전환한다.
- 부모의 최종 `저장`은 모델 호출 없이 로컬 저장만 수행한다.

### 여러 아이가 함께한 사진/활동

같은 원본을 아이마다 복제하지 않는다. `EntityLink`의 `child_scope` 관계로 한 문서를 여러 아이의 문맥에
공유하고 backlink를 유지한다. 사진 기록을 확정하면 연결된 `LearningLog`도 같은 참여 아이 문맥에서
참조할 수 있다.

```text
하나의 가족 활동
 ├─ 첫째 child context
 ├─ 둘째 child context
 └─ PhotoActivityRecord / LearningLog 원본은 하나
```

---

## 자료실 > 자료 찾기

`자료실 > 자료 찾기`는 GrowWise가 단순 기록장에 머물지 않도록 **아이의 현재 맥락과 외부 교육 자원을 연결**한다.

검색어를 직접 입력할 수도 있고, 비워두면 로컬에서 다음 정보의 일반 키워드만 추출한다.

- 아이가 부모에게 공개적으로 설정한 관심사
- 학습 목표
- 최근 관찰의 태그/관심사
- 최근 활동 제목

외부 API에는 child ID, 이름, 닉네임, 관찰 원문, 부모 메모, 사진을 보내지 않는다.

### 현재 Discovery source

`자료실 > 자료 찾기`는 초기 기획의 교육 소스 matrix를 코드 registry로 유지한다. 한 소스 장애가 전체 검색을 깨지 않도록 네트워크 소스는 독립 timeout/cache/stale fallback으로 병렬 조회한다.

| 구분 | 연결 소스 | 동작 |
| --- | --- | --- |
| **기본/공식** | 공식 한국 교육과정 카탈로그, 설정형 Public Curriculum | 번들 메타데이터 또는 선택 endpoint |
| **도서·문해력** | Data4Library, 국립중앙도서관 ISBN, Google Books, Open Library, Gutendex/Project Gutenberg, Global Digital Library | 서지·공개 메타데이터 검색 |
| **언어·어휘** | KRDict, 우리말샘, Tatoeba | 사전/예문 검색 |
| **탐방·역사** | Nominatim, Overpass, OpenTopoData, Wikidata, Wikipedia, Wikimedia Commons, 국가유산청, e뮤지엄 | 장소·역사·공개 미디어·지형 |
| **과학·자연** | NASA Image and Video Library, Wikidata, Wikimedia Commons, GBIF, 기상청, KBR | 우주·생물·날씨·공개 이미지/메타데이터 |
| **공식 카탈로그 링크** | StoryWeaver, Standard Ebooks, PhET, Illustrative Mathematics 1판, Khan Academy Kids, OpenStax | 안정적인 공개 검색 API를 가정하지 않고 공식 사이트로 연결 |
| **로컬/오프라인 capability** | WordNet, CMUdict, wordfreq, Kiwi, spaCy, soynlp, LanguageTool, hunspell-ko, BioCLIP, SymPy, Manim, JSXGraph, mathjs, Leaflet, Three.js | source registry에서 로컬 엔진/렌더러로 명시 |

공개 live API 중 key가 필요 없는 소스는 기본적으로 활성화된다. key가 필요한 소스는 설정이 없으면 `설정 필요`, 좌표 기반 지형·기상 소스는 부모가 좌표를 직접 입력하지 않으면 `위치 필요`로 표시된다. 전체 source catalog와 현재 연결 상태는 자료 찾기 화면에서 펼쳐볼 수 있다.

외부 검색에는 child ID, 이름, 관찰 원문, 부모 메모, 사진을 보내지 않는다. 텍스트는 로컬에서 일반 교육 주제어로 축약하며, 좌표는 부모가 탐방 위치를 명시적으로 입력한 요청에서만 사용한다.
### Discovery 설정

키가 필요한 소스만 환경변수 설정이 필요하다. 실제 secret은 저장소, README example 값, 로그에 커밋하지 않는다.

```bash
# 도서관 정보나루
GROWWISE_DATA4LIBRARY_API_KEY=...

# 국립중앙도서관 ISBN/서지
GROWWISE_NATIONAL_LIBRARY_API_KEY=...

# 국립국어원 사전
GROWWISE_KRDICT_API_KEY=...
GROWWISE_OPENDICT_API_KEY=...
# 선택: 우리말샘 인증키 번호
GROWWISE_OPENDICT_CERT_KEY_NO=...

# data.go.kr 계열: 기상청 + 명시적으로 설정한 공공데이터 endpoint
GROWWISE_PUBLIC_DATA_API_KEY=...

# KBR은 별도 access_key 계약
GROWWISE_KBR_API_KEY=...
# upstream의 HTTPS endpoint를 검증한 경우에만 설정
GROWWISE_KBR_ENDPOINT=https://...

# e뮤지엄 API endpoint는 계정/공공데이터 계약에서 확인한 HTTPS URL만 사용
GROWWISE_EMUSEUM_ENDPOINT=https://...

# 선택: 별도 공공 교육과정 endpoint
GROWWISE_CURRICULUM_ENDPOINT=https://example.org/curriculum/search
```

확장 공개 API 검색 전체를 끄려면 `GROWWISE_EXTERNAL_LIVE_SOURCES_ENABLED=false`를 사용한다. 공식 번들 교육과정과 이미 저장한 참고 자료는 계속 사용할 수 있다.
---

## 자료실 > 활동 자료

현재 생성 종류:

- 활동 가이드
- 독서 활동
- 영어 카드
- 수학 활동
- 과학 탐구
- 글쓰기 프롬프트
- 탐방 활동

자료 생성 시 자료실의 참고 자료에 저장한 `resource:<UUID>`를 근거로 선택할 수 있다. 생성물은 부모 검토 상태
머신을 거치며 수정 요청과 부모 직접 편집은 새 버전으로 보존한다. 승인된 자료만 사용/인쇄 대상으로
취급한다.

외부 교육과정 endpoint가 설정되어 있으면 `CurriculumGroundedMaterialService`가 공공 교육과정 결과를
일반 `ResourceRecord`로 먼저 저장한 뒤 동일한 provenance contract로 자료 생성에 사용한다.

---

## RAG와 장기 검색

GrowWise 검색은 단순히 최신순으로 결과를 자르지 않는다.

1. 먼저 query relevance를 계산한다.
2. 관련 있는 근거 안에서 **현재 월**을 우선한다.
3. 부족하면 **현재 연도의 이전 기록**으로 확장한다.
4. 그래도 부족하면 **장기 archive**를 사용한다.

즉 `current-month → current-year → archive` 시간 계층을 사용하되, 관련 없는 최신 기록이 관련 있는 오래된
근거보다 앞서도록 만들지는 않는다.

LLM/embedding이 없으면 child-scoped lexical 검색으로 계속 동작한다.

---

## LLM의 역할

GrowWise는 **LLM-enhanced이지 LLM-dependent가 아니다.**

LLM이 하는 일:

1. 관찰의 선택적 태깅·요약·분류
2. 자연어 검색 의도 해석과 RAG 질의 보조
3. 여러 기록 사이의 맥락 정리
4. 학습자료 문장 구성과 개인화 보강
5. 활동 후보 생성 보조
6. 사진 caption과 기록 초안 생성
7. 저장된 근거를 바탕으로 한 후속 질문 응답

LLM이 없어도 가능한 일:

- 아이 프로필/관찰/사진 일기 CRUD
- Markdown SoT / SQLite projection
- child-scoped lexical 검색
- current-month → current-year → archive 시간 계층
- 공식 교육과정 메타데이터 조회
- 외부 API adapter와 cache
- 활동 lifecycle
- 경험 축 성장 지도
- 라이브러리/RAG lexical 근거
- deterministic 학습자료 템플릿
- Parent Review
- 백업/복원/삭제

provider 호출에는 bounded timeout과 circuit breaker를 적용한다. 사진·Vision 작업은 일반 대화형 요청보다
느려도 괜찮으므로 별도의 긴 timeout과 durable background job을 사용한다.

---

## 데이터와 프라이버시

- Markdown = authoritative Source of Truth
- SQLite = rebuildable projection/index
- 사진 = local managed assets + hash/relative path metadata
- Desktop Core = per-run random loopback port + 256-bit session token
- Desktop data path = OS app-data
- 외부 adapter = 공개 검색 차원만 전달
- Parent Review = 생성물 사용 전 필수
- Child purge = 해당 아이 live data와 파생 데이터를 함께 정리

아이 삭제는 프로필 한 줄만 지우지 않는다. Markdown/.bak, projection, RAG, conversation, job, idempotency,
LangGraph checkpoint, 사진 asset, entity link 등 child-scoped live data를 함께 정리한다. 기존 backup ZIP은 과거
시점의 immutable snapshot이므로 별도로 관리한다.

---

## 제품 원칙

1. **부모 중심** — 부모 판단과 교육 철학이 최종 기준이다.
2. **기록 중심** — 생성물보다 누적되는 실제 경험 맥락이 우선이다.
3. **발견과 연결** — 기록을 외부 교육 자원과 연결해 다음 선택을 돕는다.
4. **로컬 우선** — 아동 데이터는 가능한 로컬에서 처리한다.
5. **근거 기반** — 검색·추천·생성에 provenance와 출처를 남긴다.
6. **비점수화** — 또래 비교·등수·XP·streak을 핵심 동기로 쓰지 않는다.
7. **검토 후 사용** — 생성 자료는 Parent Review를 거친다.
8. **LLM 비의존성** — AI 장애가 핵심 기록 기능 장애가 되지 않는다.
9. **문서 그래프** — 같은 활동/자료를 복제하기보다 EntityLink/backlink로 관계를 보존한다.

---

## 기술 구조

- Desktop: Tauri 2 + React/TypeScript
- Core: Python 3.12+ / FastAPI sidecar
- Desktop IPC: React → typed Tauri commands → Rust → authenticated ephemeral loopback Core
- Orchestration: LangChain + LangGraph
- Workflow persistence: LangGraph `SqliteSaver`
- Storage: Markdown SoT + SQLite projection/index
- RAG: lexical + optional embedding hybrid retrieval + temporal hierarchy
- External resources: bounded adapter layer + SQLite external cache
- Background jobs: SQLite durable job queue
- Model: local-first provider abstraction, 현재 Ollama adapter
- Packaging: PyInstaller one-file Core bundled as Tauri resource
- Platforms: Windows + macOS

자세한 구조는 [docs/architecture.md](docs/architecture.md), 안정성 invariant는
[docs/hardening-contracts.md](docs/hardening-contracts.md)를 참고한다.

---

## 현재 구현 상태

**pre-1.0 / repository-side implementation complete, operator validation remaining.** 제품 코드는 9-workspace IA와 production visual QA까지 반영되어 있고, stable public release에 필요한 서명/노터라이즈·updater trust root·실기기 benchmark·household dogfooding은 별도 운영 증거로 남아 있다.

주요 코드 기반에는 다음이 포함된다.

- Python FastAPI local Core
- Pydantic bounded domain model + UUIDv7
- Markdown atomic SoT + SQLite rebuild
- child-scoped lexical retrieval + optional embeddings
- current-month → current-year → archive RAG
- normalized append-only conversation storage
- crash-recoverable idempotency lease
- durable background job queue
- 영아 활동/관찰 가이드 + deterministic fallback
- 중·고 학습 tracking domain
- 자료 생성 + Parent Review + immutable version chain
- 외부 curriculum/Data4Library/Overpass adapters + bounded cache
- parent-controlled Education Discovery
- 사진 일기 + local Vision background processing
- first-class `EntityLink`/backlink graph
- 다자녀 async child-scope race guard
- authenticated random-port desktop Core
- child full purge + backup/restore
- 콘텐츠 안전 가드와 적대적 회귀 테스트
- Windows/macOS/Linux Python CI, React test/build, Rust check/Clippy
- dependency vulnerability/license audit + secret scan
- 9-workspace desktop IA + production Vite visual QA artifact
- crash/retry-safe create operations, purge fencing, crash-consistent photo/material/discovery flows

운영 단계에서 별도로 필요한 항목은 실제 code signing/notarization 자격증명, 장기 updater trust key,
실기기/로컬모델 benchmark, 가정 dogfooding이다.

---

## 로컬 Core 실행

```bash
python -m pip install -e ".[dev]"
growwise
```

독립 개발용 Core 기본 주소:

```text
http://127.0.0.1:8765
```

주요 환경변수:

```bash
GROWWISE_DATA_DIR=~/.growwise

GROWWISE_MODEL_PROVIDER=ollama
GROWWISE_MODEL_ID=qwen3.5:9b
GROWWISE_MODEL_BASE_URL=http://127.0.0.1:11434
GROWWISE_MODEL_TIMEOUT_SECONDS=12
GROWWISE_MODEL_CIRCUIT_FAILURE_THRESHOLD=3
GROWWISE_MODEL_CIRCUIT_RECOVERY_SECONDS=30
GROWWISE_LLM_FEATURES_ENABLED=true

GROWWISE_EMBEDDING_TIMEOUT_SECONDS=8
GROWWISE_EMBEDDING_FEATURES_ENABLED=true

GROWWISE_VISION_PROVIDER=ollama
GROWWISE_VISION_MODEL_ID=gemma3:4b
GROWWISE_VISION_BASE_URL=http://127.0.0.1:11434
GROWWISE_VISION_TIMEOUT_SECONDS=300
GROWWISE_VISION_FEATURES_ENABLED=true

GROWWISE_DATA4LIBRARY_API_KEY=...
GROWWISE_CURRICULUM_ENDPOINT=...
```

AI 기능을 완전히 끄려면:

```bash
GROWWISE_LLM_FEATURES_ENABLED=false
GROWWISE_EMBEDDING_FEATURES_ENABLED=false
GROWWISE_VISION_FEATURES_ENABLED=false
```

사진 기록, 관찰, 활동, lexical 검색, 공식 교육과정 카탈로그, 라이브러리, deterministic 자료 생성은 계속
사용할 수 있다.

---

## Desktop 개발 실행

```bash
python -m pip install -e ".[dev]"
cd desktop
npm install
npm run tauri:dev
```

Tauri는 개발 환경에서도 `growwise.api.secure_entry`를 자식 프로세스로 시작한다. 실행마다 임의의 loopback
port와 새 세션 토큰을 만들고 authenticated protocol handshake가 성공한 뒤에만 IPC를 연결한다. 데이터는
Tauri가 제공하는 OS app-data 경로를 사용한다.

## Desktop Core sidecar 빌드

```bash
python -m pip install -e ".[desktop-build]"
python desktop/scripts/build_core_sidecar.py
python desktop/scripts/smoke_core_sidecar.py
```

결과:

```text
desktop/src-tauri/binaries/growwise-core
desktop/src-tauri/binaries/growwise-core.exe
```

실행 파일은 Git에 커밋하지 않고 CI/릴리스 과정에서 플랫폼별로 생성한다. sidecar smoke는 임의 port/token으로
Core를 실행해 무인증 요청 거부와 authenticated handshake까지 확인한다.

---

## 주요 API vertical slices

```text
POST   /v1/children
DELETE /v1/children/{child_id}

POST   /v1/observations
GET    /v1/children/{child_id}/observations
POST   /v1/children/{child_id}/photo-records
POST   /v1/photo-records/{record_id}/commit

POST   /v1/children/{child_id}/activities
GET    /v1/children/{child_id}/activities

GET    /v1/children/{child_id}/discover
POST   /v1/children/{child_id}/discover/save
POST   /v1/resources

GET    /v1/children/{child_id}/search?q=...
POST   /v1/rag/ask
POST   /v1/children/{child_id}/ask
POST   /v1/children/{child_id}/conversations
POST   /v1/conversations/{session_id}/turns

POST   /v1/children/{child_id}/materials
POST   /v1/children/{child_id}/materials/curriculum
POST   /v1/materials/{material_id}/review

POST   /v1/links
GET    /v1/links/{entity_id}

GET    /v1/children/{child_id}/growth-map
GET    /health
```

---

## 문서

| 문서 | 내용 |
| --- | --- |
| **[docs/README.md](docs/README.md)** | **문서 전체 인덱스와 현재 IA 문서화 규칙** |
| **[docs/user-guide.md](docs/user-guide.md)** | **화면별 사용법과 대표 사용자 시나리오** |
| **[docs/pedagogy.md](docs/pedagogy.md)** | **교육 원칙과 제품 철학** |
| [docs/vision.md](docs/vision.md) | 제품 비전·LLM 역할·성공 기준 |
| [docs/product-spec.md](docs/product-spec.md) | 전 연령 제품 사양 |
| [docs/material-product-ux.md](docs/material-product-ux.md) | 자료 생성·검토 UX |
| [docs/architecture.md](docs/architecture.md) | Tauri/Python/LangChain/LangGraph 실행 구조 |
| [docs/hardening-contracts.md](docs/hardening-contracts.md) | 인증·복구·삭제권·race·RAG·AI fallback invariant |
| [docs/data-model.md](docs/data-model.md) | Markdown SoT·SQLite projection·상태 머신 |
| [docs/integrations.md](docs/integrations.md) | 외부 API·데이터 소스·Model Provider |
| [docs/privacy-and-safety.md](docs/privacy-and-safety.md) | 프라이버시·비감시·비진단 원칙 |
| [docs/threat-model.md](docs/threat-model.md) | 위협 모델·데이터 보존/삭제 |
| [docs/evaluation.md](docs/evaluation.md) | 생성/RAG/장기해석/안전 평가 |
| [docs/curriculum-sources.md](docs/curriculum-sources.md) | 교육과정·과목별 공개 자료 후보 |
| [docs/design-system.md](docs/design-system.md) | 브랜드·UI 디자인 규칙 |
| [docs/FRONTEND_COMPLETION_AUDIT.md](docs/FRONTEND_COMPLETION_AUDIT.md) | 현재 데스크톱 IA·visual acceptance·프론트 완료 상태 |
| [docs/RELEASE_READINESS.md](docs/RELEASE_READINESS.md) | 저장소 완료 범위와 stable release 운영 경계 |
| [docs/hardware.md](docs/hardware.md) | 최소/권장 하드웨어 |
| [docs/release.md](docs/release.md) | 릴리스·패키징 절차 |
| [docs/operational-validation.md](docs/operational-validation.md) | 실기기 benchmark·서명·updater 검증 |
| [docs/roadmap.md](docs/roadmap.md) | 전체 기능 완성 로드맵 |

브랜드 자산은 [assets/brand](assets/brand)를 참고한다.

## 라이선스

[Apache License 2.0](LICENSE). Copyright 2026 Yong-eun Cho.
