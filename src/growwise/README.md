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

## 채우는 순서(M0 제안)

1. `storage/` — 데이터 모델 v0 스키마
2. `router/` + `generators/` — 첫 생성 모듈 1종(예: 독서 활동지)
3. `export/` — 생성물 PDF 출력
4. `review/` — 노출 전 체크리스트
5. `api/` — end-to-end 연결

> 기술 스택(FastAPI vs Node, SQLite vs Markdown, RAG 사용 여부)은 M0 착수 전에
> 확정한다([roadmap.md](../../docs/roadmap.md) 미해결 질문 1·2·5).
