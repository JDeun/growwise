# Desktop completion audit

이 문서는 현재 React/Tauri 데스크톱을 Core API 데모가 아니라 **실제 제품 사용자 화면**으로 보고 완료 상태를 점검한다.

## Current product workspace surface

사용자에게 노출되는 persistent workspace는 9개다.

1. Dashboard / 대시보드
2. Child Profile / 아이 프로필
3. Learning Records / 학습 기록
4. Materials / 자료실
5. Photos / 사진첩
6. Conversation / 대화하기
7. Backup / 백업 및 복원
8. Settings / 설정
9. Help / 도움말

이전의 observations, growth, activities, discovery, library, search는 제품 사이드바 항목이 아니다. 저장된 구형 workspace 값은 새 상위 workspace로 migration되고 기능은 다음처럼 재조립됐다.

| Legacy feature | Current product location |
| --- | --- |
| observations | 학습 기록 → 관찰 기록 / 아이 프로필 맥락 |
| growth | 아이 프로필 → 발달 분석 / 성장 리포트 |
| activities | 자료실 → 활동 관리 |
| discovery | 자료실 → 자료 찾기 |
| library | 자료실 → 참고 자료 |
| search | 대화하기 |

## Desktop composition status

- [x] WorkspaceShell이 브랜드, 사이드바, 공통 topbar, 작업공간 frame을 소유한다.
- [x] topbar는 검색 진입점 → 데이터 기반 알림 → 아이 프로필 순서다.
- [x] 전역 새 기록 버튼은 제거하고 page-local CTA로 이동했다.
- [x] WorkspaceView의 사용자 노출 IA와 legacy migration 경계를 분리했다.
- [x] feature를 모두 mount한 뒤 CSS로 숨기는 전역 projection 방식을 제거했다.
- [x] 현재 workspace에 필요한 feature만 실제 mount한다.
- [x] Profile/Learning/Materials는 상위 Hub가 탭과 subview visibility를 소유한다.
- [x] child switch 중 stale async response가 현재 아이 상태를 덮지 않도록 generation/scope guard를 유지한다.
- [x] 프로필 저장은 전체 페이지 reload 없이 ActiveChildProvider와 App state를 즉시 reconciliation한다.

## Visual acceptance status

승인된 GrowWise concept/brand 기준으로 다음을 production Vite bundle에서 검수했다.

- [x] Warm Off White / Ink / Sage / Leaf / Stone 토큰
- [x] 하나의 rounded desktop application frame
- [x] integrated left sidebar
- [x] 9-workspace navigation + 하단 설정/도움말
- [x] Dashboard: title → four KPI cards → recent activity + recommendation
- [x] Profile: child summary + 기록/발달 분석/성장 리포트
- [x] Learning: 학습 기록 + 관찰 기록
- [x] Materials: document canvas + generation controls를 first viewport에 배치
- [x] Photos: gallery-first + filter + detail + create workflow
- [x] Conversation: history + chat + backup 3-pane composition
- [x] Backup / Settings 분리
- [x] Help 독립 workspace
- [x] 전역 print toolbar 누출 제거
- [x] production-render 기준 horizontal overflow 0
- [x] production-render 기준 visible text/button clipping 0
- [x] production-render 기준 page error 0
- [x] 승인 concept geometry 재대조: shell 1540 / sidebar 232 / topbar 62
- [x] Dashboard 42:58, Profile 27:73, Learning 24:31:45, Materials 68:32, Conversation 22:41:37 비율 고정
- [x] `VisualContract.test.ts`가 brand token + shell geometry + workspace split 비율 drift를 차단

CI의 desktop-frontend job은 production desktop/dist를 growwise-frontend-dist artifact로 업로드해 동일 bundle을 시각 검수에 재사용할 수 있다.

## Runtime regressions closed during visual QA

- [x] 이전 대화 선택 UI와 실제 후속 질문 session이 다르게 유지되던 경로 수정
- [x] 사진첩 filter 밖 record detail이 남는 상태 수정
- [x] 사진첩 DOM 순서와 visual order를 일치시켜 keyboard/screen-reader order 보정
- [x] 승인 material mount 시 window.location.reload fallback으로 발생할 수 있던 reload loop 제거
- [x] material result/quest 생성 뒤 전체 reload 대신 activities/observations/growth context만 선택 재조회
- [x] material result reload regression test 추가
- [x] profile edit action이 실제 Settings editor로 연결되도록 의미 정렬

## Core product-quality completion

- [x] Core-only mode: 기록, lexical retrieval, activity management, deterministic material generation, Parent Review, backup/restore가 LLM 없이 동작
- [x] Parent Review material state machine
- [x] durable background photo processing
- [x] child full purge
- [x] crash/retry-safe create operations with stable reserved IDs
- [x] conversation operation identity persistence
- [x] discovery/RAG interrupted-ingest reconciliation
- [x] managed file permission hardening
- [x] authenticated random-port desktop Core boundary
- [x] Windows/macOS package validation, CodeQL, secret scan, dependency/license hygiene

## Remaining non-repository evidence

현재 저장소 코드/자동화 관점의 blocker는 없다. 다음은 운영자가 실제 장비·자격증명·장기 키를 사용해 증명해야 한다.

- production code signing/notarization
- updater long-lived trust-root activation and packaged-client update test
- representative local-model latency/quality benchmark
- representative minimum/recommended hardware benchmark
- household dogfooding

관련 절차는 docs/operational-validation.md와 docs/operator-handoff.md를 따른다.