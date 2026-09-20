# GrowWise 기술 가이드

이 문서는 **개발자와 운영자**를 위한 진입점입니다. 일반 사용법은 [README](../README.md)와 [사용자 가이드](user-guide.md)를 참고하세요.

GrowWise의 기술 문서는 역할별로 나뉘어 있습니다. 이 문서에는 개발 환경, 실행, 테스트, 모델 설정, 배포 흐름만 요약하고 세부 설계는 전용 문서로 연결합니다.

---

## 기술 개요

```text
React / TypeScript UI
        ↓
Tauri 2 IPC
        ↓
Rust host
        ↓
authenticated ephemeral loopback
        ↓
Python FastAPI Core
        ↓
Domain / Storage / RAG / Workflow / Model adapters
```

핵심 원칙:

- **Markdown = authoritative Source of Truth**
- **SQLite = rebuildable projection/index**
- **LLM = optional enrichment**
- **Desktop Core = random loopback port + per-run session token**
- **AI outage must not block core record persistence**
- **child-scoped async work must reject stale child context**
- **generated material has an internal review state machine even when the primary UI hides that plumbing**

세부 구조:

- [architecture.md](architecture.md)
- [data-model.md](data-model.md)
- [hardening-contracts.md](hardening-contracts.md)
- [threat-model.md](threat-model.md)

---

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Desktop | Tauri 2, React, TypeScript, Vite |
| Core | Python 3.12+, FastAPI, Pydantic v2 |
| Workflow | LangChain, LangGraph |
| Storage | Markdown + SQLite |
| RAG | lexical baseline + optional embeddings |
| Model | Ollama / OpenAI-compatible provider abstraction |
| Background work | durable SQLite job queue |
| Packaging | PyInstaller sidecar + Tauri bundle |
| Test | pytest, Vitest, Playwright, Rust tests |
| Quality | Ruff, mypy, ESLint/Prettier, Clippy |
| CI | GitHub Actions on Windows/macOS/Linux |

---

## 개발 환경 준비

권장 도구:

- Python 3.12+
- uv
- Node.js 22+
- Rust stable
- npm
- macOS에서는 Xcode Command Line Tools
- Windows에서는 Tauri 요구 빌드 도구와 WebView2

저장소 루트에서:

```bash
python -m pip install "uv==0.12.13"
uv sync --locked --extra dev --extra desktop-build
```

Desktop 의존성:

```bash
cd desktop
npm ci
cd ..
```

---

## Python Core 실행

독립 개발용 Core:

```bash
uv run growwise
```

기본 주소:

```text
http://127.0.0.1:8765
```

Core만 실행할 때는 Desktop용 random-port/session-token 경계가 아니라 독립 개발 API 모드가 사용됩니다.

---

## Desktop 개발 실행

```bash
cd desktop
npm run tauri:dev
```

Desktop에서는 Rust host가 Python Core를 직접 시작합니다.

실행 순서:

1. OS에 ephemeral loopback port 요청
2. CSPRNG session token 생성
3. Python secure entrypoint 실행
4. authenticated handshake 확인
5. 이후 Tauri command를 통해서만 Core 호출

Desktop 데이터는 OS app-data 경로를 사용합니다.

---

## Core sidecar 빌드

저장소 루트:

```bash
uv run python desktop/scripts/build_core_sidecar.py
uv run python desktop/scripts/smoke_core_sidecar.py
```

플랫폼별 결과:

```text
desktop/src-tauri/binaries/growwise-core
desktop/src-tauri/binaries/growwise-core.exe
```

sidecar 바이너리는 Git에 커밋하지 않습니다. CI와 package workflow가 플랫폼별로 생성합니다.

---

## 모델 provider

GrowWise Core는 특정 vendor SDK에 직접 결합하지 않습니다.

지원 경로:

1. **Ollama** — local default
2. **OpenAI-compatible Chat Completions endpoint** — llama.cpp, LM Studio, vLLM 등
3. **명시적으로 허용된 remote OpenAI-compatible endpoint**

기본 설정:

```text
GROWWISE_MODEL_PROVIDER=ollama
GROWWISE_MODEL_ID=qwen3.5:9b
GROWWISE_MODEL_BASE_URL=http://127.0.0.1:11434

GROWWISE_VISION_PROVIDER=ollama
GROWWISE_VISION_MODEL_ID=qwen3.5:9b
GROWWISE_VISION_BASE_URL=http://127.0.0.1:11434

GROWWISE_EMBEDDING_PROVIDER=ollama
GROWWISE_EMBEDDING_MODEL_ID=nomic-embed-text
GROWWISE_EMBEDDING_BASE_URL=http://127.0.0.1:11434
```

일반 사용자용 모델 설치와 사양별 추천은 [local-ai-setup.md](local-ai-setup.md)를 참고하세요.

기본 Desktop은 text/vision adapter를 논리적으로 분리하지만 같은 Qwen 3.5 멀티모달 모델 ID를 주입한다. 이를 통해 사진 처리의 별도 timeout/privacy 경계는 유지하면서 모델 artifact 중복 다운로드와 런타임 model swapping을 줄인다. 고급 설정에서만 두 역할의 모델을 다르게 지정한다.

### AI 완전 비활성화

```bash
GROWWISE_LLM_FEATURES_ENABLED=false
GROWWISE_EMBEDDING_FEATURES_ENABLED=false
GROWWISE_VISION_FEATURES_ENABLED=false
```

이 상태에서도 기록, lexical 검색, 기본 자료 생성, 교육과정, 백업/복원 등 Core 기능은 동작해야 합니다.

### OpenAI-compatible local endpoint

예:

```bash
GROWWISE_MODEL_PROVIDER=openai_compatible
GROWWISE_MODEL_ID=your-model
GROWWISE_MODEL_BASE_URL=http://127.0.0.1:8080/v1
```

비-loopback endpoint는 아동 학습 맥락이 외부로 전달될 수 있으므로 명시적 opt-in이 필요합니다.
이 경계는 OpenAI-compatible뿐 아니라 원격 Ollama text endpoint에도 동일하게 적용됩니다.

```bash
GROWWISE_MODEL_REMOTE_ALLOWED=true
GROWWISE_MODEL_API_KEY=...
```

API key를 사용하는 원격 endpoint는 HTTPS가 요구됩니다.

세부 정책은 [integrations.md](integrations.md)를 참고하세요.

---

## 주요 데이터 경계

### Child data

- Markdown records = 정본
- SQLite = projection/index
- photos = managed local asset
- conversations = local SQLite
- jobs/checkpoints/idempotency = local operational state

### External enrichment

외부 adapter에는 allow-list된 공개 검색 차원만 보냅니다.

금지되는 기본 outbound context:

- child ID
- 이름/닉네임
- 관찰 원문
- 부모 자유 메모
- 사진

### Deletion

아이 삭제는 profile row 하나만 지우지 않습니다.

child-scoped:

- Markdown / backup sidecar
- projection
- RAG chunk
- conversation
- job
- idempotency metadata
- workflow checkpoint
- photo asset
- entity link

를 함께 정리합니다.

과거 immutable backup ZIP은 별도 파일이므로 자동 삭제하지 않습니다.

---

## 생성 자료 내부 상태

Primary UX에서는 사용자가 workflow plumbing을 볼 필요가 없지만 도메인에서는 상태 전이를 강제합니다.

```text
DRAFT
  ↓
REVIEW_PENDING
  ├─→ REVISION_REQUESTED
  ├─→ REJECTED
  └─→ APPROVED
          ↓
       ARCHIVED
```

현재 UI의 **“이 활동 사용하기”**는 한 번의 명시적 사용자 결정으로 보이지만 내부에서는 허용된 review gate를 통과한 뒤 `APPROVED` 상태가 됩니다.

따라서 progressive disclosure로 UX를 단순화해도 export/사용 안전 invariant는 유지됩니다.

---

## 교육과정 versioning

교육과정 선택은 stage label 하나만으로 결정하지 않습니다.

사용 가능한 경우:

- birth date
- current/reference date
- explicit grade

를 사용해 학년별 시행 시점을 계산합니다.

전환기에 grade/birth-date 정보가 부족하면 모호한 새 개정본을 임의 적용하지 않고 fail-closed 상태를 사용합니다.

구조화된 외부 curriculum metadata가 bundled resolver를 덮어쓰려면 official host, notice, effective date, grade scope 등을 검증해야 합니다.

새 고시 HTML 탐지는 **candidate alert**일 뿐 자동 production activation이 아닙니다.

세부 출처와 규칙:

- [curriculum-sources.md](curriculum-sources.md)
- [integrations.md](integrations.md)

---

## 테스트

### Python

```bash
uv run pytest
```

### Python quality

```bash
uv run ruff check .
uv run mypy src
```

### Desktop frontend

```bash
cd desktop
npm test
npm run build
```

### Rust

```bash
cd desktop/src-tauri
cargo check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

실제 CI 정의가 최종 기준입니다.

```text
.github/workflows/ci.yml
.github/workflows/package.yml
.github/workflows/secret-scan.yml
```

---

## 적대적 품질 기준

GrowWise는 happy path 성공만으로 완료로 보지 않습니다.

회귀 범위에는 다음이 포함됩니다.

- malformed model output
- hallucinated citation
- prompt injection
- child PII leakage
- age-inappropriate material
- scaffold/answer-giving violation
- model outage / timeout
- embedding outage
- offline mode
- duplicate/replayed request
- child switch race
- corrupt/rebuildable projection
- crash recovery
- backup restore
- stale external curriculum metadata

세부 invariant:

[hardening-contracts.md](hardening-contracts.md)

---

## 하드웨어와 모델 benchmark

Core-only hardware:

```bash
uv run python scripts/benchmark_hardware.py
```

모델 latency/quality:

```bash
uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3
```

실제 최소/권장 사양은 CI runner가 아니라 대표 가정용 Windows/macOS 기기에서 검증해야 합니다.

- [hardware.md](hardware.md)
- [operational-validation.md](operational-validation.md)

---

## 데스크톱 패키징

Core sidecar를 먼저 만들고 Tauri bundle에 resource로 포함합니다.

일반 validation package:

### Windows

```bash
cd desktop
npm run tauri -- build --bundles nsis
```

### macOS

```bash
cd desktop
npm run tauri -- build --bundles dmg
```

PR package는 Windows unsigned / macOS ad-hoc signing을 허용합니다. stable release는 별도 production signing credential을 요구합니다.

세부 절차:

[release.md](release.md)

---

## Stable release 전 운영 작업

코드만으로 완료할 수 없는 항목:

- Apple Developer ID signing
- macOS notarization
- Windows Authenticode signing
- long-lived Tauri updater signing key
- clean-device install/update recovery test
- representative hardware benchmark
- household dogfooding

완료 기준:

[operational-validation.md](operational-validation.md)

---

## 문서 구조

### Product / UX

- [user-guide.md](user-guide.md)
- [product-spec.md](product-spec.md)
- [vision.md](vision.md)
- [pedagogy.md](pedagogy.md)
- [design-system.md](design-system.md)
- [material-product-ux.md](material-product-ux.md)

### Engineering

- [architecture.md](architecture.md)
- [data-model.md](data-model.md)
- [hardening-contracts.md](hardening-contracts.md)
- [integrations.md](integrations.md)
- [evaluation.md](evaluation.md)
- [adr/](adr/)

### Security / privacy

- [privacy-and-safety.md](privacy-and-safety.md)
- [threat-model.md](threat-model.md)
- [attribution.md](attribution.md)

### Release / operations

- [release.md](release.md)
- [RELEASE_READINESS.md](RELEASE_READINESS.md)
- [operator-handoff.md](operator-handoff.md)
- [operational-validation.md](operational-validation.md)

전체 문서 목차는 [docs/README.md](README.md)를 참고하세요.
