# 소스 구조

GrowWise는 **교육 트래킹·자료 지식베이스·학습자료 생성 시스템**이며, LLM은 백그라운드
지능 계층으로 사용한다. chat session 자체는 핵심 도메인이 아니다.

```text
src/growwise/
├── api/          Tauri ↔ Python API/IPC, health/version, request DTO
├── domain/       핵심 엔티티·enum·invariant·schema
├── workflows/    LangGraph state/nodes/edges/checkpoint/recovery
├── router/       자연어/기능 요청을 workflow/use-case로 라우팅
├── generators/   독서/영어/탐방/수학/과학/글쓰기/영아 활동 생성
├── rag/          기록·교육과정·도서·외부 자료 검색과 provenance
├── storage/      Markdown SoT, SQLite projection, migration/rebuild
├── export/       HTML/CSS/PDF 및 portable Markdown export
├── review/       automated review + Parent Review 정책
├── adapters/     외부 데이터/API 경계, cache/offline fallback
└── model/        LangChain 기반 Model Provider와 embedding abstraction
```

## 의존 방향

도메인과 저장 규칙이 모델 프레임워크에 종속되지 않도록 한다.

```text
api/workflows/generators/rag/review
              ↓
           domain

model/adapters/storage/export
      = infrastructure boundary
```

`domain/`은 LangChain/LangGraph, FastAPI, Tauri를 import하지 않는다.

## LangChain / LangGraph 역할

- **LangChain**: chat model/embedding/retriever/structured output/prompt/tool adapter
- **LangGraph**: 상태 머신, workflow orchestration, retry/recovery, checkpoint,
  human-in-the-loop Parent Review

LangGraph는 "여러 에이전트를 만들기 위해" 쓰는 것이 아니라 안정적인 **execution harness**로
사용한다.

대표 workflow:

```text
natural-language request or UI action
 → normalize
 → route
 → retrieve/context
 → generate or analyze
 → validate
 → automated review
 → parent review if needed
 → persist/project
 → export or answer
```

## LLM의 위치

LLM은 다음에 사용한다.

- 기록 분류·태깅·요약
- 자연어 검색 의도 해석
- RAG 기반 질의응답
- 장기 기록 비교·정리
- 학습자료 생성
- 다음 활동 후보 생성
- 구조/안전/grounding 검토

아이와 지속적으로 대화하는 chatbot/companion은 구현하지 않는다.

## 구현 순서

### Phase 0 — Walking Skeleton

1. `domain/` — ID, stage, material state, learning/observation entities
2. `storage/` — Markdown SoT + SQLite projection/rebuild
3. `workflows/` — LangGraph typed state/checkpoint
4. `model/` — LangChain provider + Ollama adapter
5. `api/` — Tauri sidecar API
6. UI → API → workflow → storage → UI end-to-end

### Phase 1 — 영아(0~2) 실사용

현재 생후 9개월 아이에게 실제로 사용할 수 있는 첫 dogfooding 기능을 만든다.

- 아이 프로필/다자녀 전환
- 월령 기반 놀이·상호작용 제안
- 부모 관찰 기록
- 책 읽어주기 추천
- 경험 커버리지 성장 지도
- 활동 퀘스트
- 자연어 기록 검색

### Phase 2+ — 전체 기능 확장

독서·영어·탐방·수학·과학·글쓰기 생성 → 성장/퀘스트 → 중·고 tracking → integrations →
desktop productization → 안정화·적대적 리뷰·위생 순으로 진행한다.

상세 체크리스트는 [roadmap.md](../../docs/roadmap.md)를 따른다.
