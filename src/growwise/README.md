# 소스 구조 (스캐폴드)

아직 구현 전이다. 아래는 [architecture.md](../../docs/architecture.md)의 모듈을
디렉토리로 매핑한 뼈대다. 각 디렉토리는 첫 마일스톤(M0, [roadmap.md](../../docs/roadmap.md))
에서 순차적으로 채운다.

```
src/growwise/
├── api/          API Server — HTTP 진입점, 요청/응답, 세션
├── router/       Request Router — 입력 유형 분류 → 생성 모듈 라우팅
├── generators/   생성 모듈 — 독서/영어/탐방/수학/과학 활동 생성
├── rag/          Local RAG — 로컬 근거 자료 검색
├── storage/      Storage — Markdown/SQLite 저장·조회, 학습 로그
├── export/       PDF Export — 인쇄 품질 문서 출력
├── review/       Parent Review Layer — 노출 전 검토(난이도·민감성·PII)
├── adapters/     External API Adapters — 외부 자료 접근(경계 통제)
└── model/        Model Provider — LLM 추상화(모델·공급자 교체·이식, 폴백)
```

## 채우는 순서

**M0(첫 빌드) = 영아(0-2) 모드**는 워크시트 생성 파이프라인이 아니라 부모 대면 기록·추천
이다([roadmap.md](../../docs/roadmap.md) M0). 순서:

1. `api/` + `storage/` — Tauri↔Python 사이드카 연결 + 데이터 모델 v0(다자녀 `child_id`,
   학습 로그) + Markdown(SoT)/SQLite(인덱스)
2. 영아 모드: 관찰 기록 저장·조회, 놀이/상호작용 제안(표준보육과정 템플릿), 책 추천
   (도서관 정보나루 DB), 성장 지도 기초, 아이 전환(다자녀)
3. `review/` 경량 + README 로컬 실행 가이드

**이후(자료 생성 트랙)**: `router/` + `generators/`(첫 워크시트=탐방) → `export/`(WeasyPrint
PDF) → `model/`(Model Provider). 이 트랙에서 로컬 LLM+PDF+scaffold 파이프라인을 검증한다.

> 자세한 v1 경계·순서는 [roadmap.md](../../docs/roadmap.md). 저장=하이브리드, PDF=WeasyPrint,
> 벡터=Chroma로 확정([architecture.md](../../docs/architecture.md)).
