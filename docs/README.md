# GrowWise documentation

이 디렉터리는 GrowWise의 제품, UX, 아키텍처, 안전성, 릴리스 운영 문서를 역할별로 정리한다.

## Start here

| 문서 | 용도 |
| --- | --- |
| [../README.md](../README.md) | 비개발자 중심 제품 소개와 첫 사용 흐름 |
| [user-guide.md](user-guide.md) | 현재 9-workspace 데스크톱 사용법 |
| [local-ai-setup.md](local-ai-setup.md) | Ollama 설치, 사양별 오픈 모델 추천, 모델 변경 |
| [technical-guide.md](technical-guide.md) | 개발·아키텍처·테스트·모델·패키징 기술 진입점 |
| [product-spec.md](product-spec.md) | 제품 범위, 연령별 요구사항, Desktop product IA |
| [FRONTEND_COMPLETION_AUDIT.md](FRONTEND_COMPLETION_AUDIT.md) | 현재 프론트 구조와 visual acceptance 상태 |

## Product and UX

- [vision.md](vision.md) — 제품 비전과 성공 기준
- [pedagogy.md](pedagogy.md) — 교육 원칙과 부모 중심 철학
- [design-system.md](design-system.md) — 브랜드, shell, workspace, 접근성 규칙
- [material-product-ux.md](material-product-ux.md) — 활동 자료 생성/검토/승인 UX
- [roadmap.md](roadmap.md) — 저장소 구현 및 operator-only 잔여 항목

## Engineering

- [technical-guide.md](technical-guide.md) — 개발/운영 기술 진입점
- [architecture.md](architecture.md) — Tauri/React/Python/LangGraph 구조와 Desktop composition
- [data-model.md](data-model.md) — Markdown SoT, SQLite projection, 상태 모델
- [hardening-contracts.md](hardening-contracts.md) — crash/retry/purge/race/RAG invariant
- [integrations.md](integrations.md) — 외부 데이터와 model provider 경계
- [evaluation.md](evaluation.md) — 생성/RAG/안전 평가
- [adr/](adr/) — 주요 아키텍처 결정 기록

## Privacy and security

- [privacy-and-safety.md](privacy-and-safety.md) — 개인정보, 비진단, 비감시 원칙
- [threat-model.md](threat-model.md) — 위협 모델과 데이터 lifecycle
- [attribution.md](attribution.md) — 외부 자료 attribution 규칙

## Release and operations

- [RELEASE_READINESS.md](RELEASE_READINESS.md) — 저장소 완료 범위와 stable release 경계
- [release.md](release.md) — 패키징, 서명, notarization, updater 절차
- [operational-validation.md](operational-validation.md) — 실기기/실모델/서명/dogfooding 검증
- [operator-handoff.md](operator-handoff.md) — 운영자 handoff checklist
- [hardware.md](hardware.md) — 최소/권장 하드웨어 기준

## Education sources

- [curriculum-sources.md](curriculum-sources.md) — 교육과정/공개 자료 출처
- [references.md](references.md) — 제품/교육/기술 참고 자료

## Current documentation rule

사용자에게 노출되는 desktop IA는 다음 9개 workspace를 기준으로 문서화한다: **대시보드, 아이 프로필, 학습 기록, 자료실, 사진첩, 대화하기, 백업 및 복원, 설정, 도움말**.

관찰 기록, 성장 보기, 활동, 자료 찾기, 참고 자료는 독립 primary navigation으로 문서화하지 않는다. 각각 학습 기록, 아이 프로필, 자료실의 하위 기능으로 설명한다.

저장소에서 자동으로 검증 가능한 구현 상태와 실제 기기/서명 자격증명/장기 updater key가 필요한 operator evidence를 구분한다. 후자는 코드가 있다고 완료로 표시하지 않는다.