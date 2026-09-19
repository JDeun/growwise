# 디자인 시스템

GrowWise의 시각 언어를 정의한다. 목표는 **따뜻하고 차분하며, 한눈에 읽히고, 접근성이
높은** 인터페이스다. 게임 UI의 가독성은 빌리되 게임의 자극적·압박적 연출은 쓰지 않는다.

## 스타일 선택

> **채택: 따뜻한 미니멀 + 소프트 카드 기반, 접근성 우선.**

- 미니멀/플랫 기반: 콘텐츠와 기록에 집중한다.
- 소프트 카드: 낮은 시각적 압력으로 정보 그룹을 구분한다.
- 명확한 계층: 장식보다 제목·본문·메타데이터의 위계를 우선한다.

의도적으로 피한다.

- 뉴모피즘: 저대비 접근성 문제
- 과한 글래스/블러: 가독성과 성능 비용
- 브루탈리즘/네오브루탈리즘: 제품의 차분한 성격과 충돌
- 네온·과도한 그라데이션·게임 보상 연출: 기록/학습을 강박 루프로 만들 위험

## 디자인 원칙

1. **차분함 우선** — 색·모션·소리로 재촉하지 않는다.
2. **가독성 우선** — 한눈에 정보 구조를 파악할 수 있게 한다.
3. **접근성 필수** — WCAG AA 이상, 색 단독 의미 전달 금지, 키보드 접근성, reduced motion.
4. **비압박 시각 언어** — 큰 점수·등수·실패 배지·의무 스트릭·카운트다운을 쓰지 않는다.
5. **인쇄 친화** — 흑백에서도 자료 구조가 유지된다.
6. **크로스플랫폼** — Windows·macOS 양쪽에서 자연스럽게 동작한다.
7. **기록 공백 중립성** — 기록이 없는 날/기간을 빨강·경고·실패로 표현하지 않는다.
8. **관찰과 해석 분리** — AI 요약/추론은 원본 관찰과 시각적으로 구분한다.

## 현재 Desktop shell 계약

GrowWise desktop은 여러 개의 떠 있는 패널이 아니라 **하나의 통합 application frame**으로 구성한다.

- 좌측 고정 sidebar: 대시보드 / 아이 프로필 / 학습 기록 / 자료실 / 사진첩 / 대화하기 / 백업 및 복원
- sidebar 하단 utility: 설정 / 도움말
- 공통 topbar: 검색 진입점 → 알림 → 현재 아이 프로필
- page-local action: 새 기록, 새 사진 기록, 자료 생성 같은 CTA는 해당 화면 header 또는 본문에 둔다.
- legacy 기능인 관찰/성장/활동/자료 찾기/참고 자료는 별도 sidebar 항목으로 노출하지 않고 관련 상위 workspace의 tab/subview로 배치한다.
- shell과 feature는 역할을 분리한다. shell은 navigation/chrome을, 각 Hub는 자신의 tab/subview visibility를 책임진다.

### 승인 UI 콘셉트 geometry contract

1672×941 GrowWise UI 콘셉트 보드를 desktop visual acceptance baseline으로 사용한다. 절대 픽셀은
viewport에 따라 반응형으로 변할 수 있지만, 1540px product shell 기준의 핵심 비율은 아래를
고정한다.

- application shell max-width: 1540px
- desktop sidebar: 232px
- common topbar: 62px
- primary product card/panel radius: 약 17px
- Dashboard 하단: 최근 활동 : 추천 활동 ≈ 42 : 58
- Profile: 아이 요약 : 콘텐츠 ≈ 27 : 73
- Learning Records: profile : master : detail = 24 : 31 : 45
- Materials: document canvas : generation controls ≈ 68 : 32
- Conversation: history : chat : utility/backup ≈ 22 : 41 : 37

이 값은 단순 문서 권고가 아니라 `VisualContract.test.ts`에서 CSS 계약으로 회귀 검증한다.
940px 이하 shell, 각 workspace의 별도 breakpoint에서는 접근성과 clipping 방지를 우선해
단일/다단 반응형 레이아웃으로 전환할 수 있다.


## 성장 지도는 점수판이 아니다

방사형 지도는 구현상 숫자 projection을 사용할 수 있지만 **사용자에게 숫자 성취도로
인지되도록 표현해서는 안 된다.** 경험 커버리지도 숫자로 보이면 부모가 점수처럼 최적화할
수 있기 때문이다.

### 기본 표시

가능하면 다음과 같은 질적 상태를 우선한다.

- 최근 자주 경험함
- 다양하게 경험 중
- 새롭게 나타난 관심
- 최근 기록이 적음
- 한동안 관찰되지 않음

`최근 기록이 적음`은 `부족함`, `뒤처짐`, `개선 필요`와 동의어가 아니다. 데이터가 없는
경우에는 **"관찰되지 않음"**으로 표현하며 능력 부재로 추론하지 않는다.

### 금지되는 표현

- `82점`, `B+`, `Lv.7`, 상위 20%
- 또래 평균선과 아이를 겹쳐 비교하는 radar
- 빨간색 "부족" 영역
- 모든 축을 최대치로 채우도록 유도하는 목표
- 주간/월간 커버리지 100% 달성률
- 다른 형제·아이와의 비교

### 상세 데이터가 필요한 경우

부모가 분석 화면에서 원자료를 확인할 수는 있다. 예를 들어 "최근 30일 관련 활동 4건"은
사실 데이터다. 그러나 이 값을 능력 점수로 재명명하지 않는다. **projection은 탐색과 균형
확인을 위한 보조 시각화이고 원본 관찰이 정본**이다.

## 활동 퀘스트의 비게임화

`퀘스트`는 활동을 쉽게 탐색하는 UI metaphor일 뿐이다.

- 제안/진행/완료/건너뜀 상태를 제공한다.
- `SKIPPED`는 실패가 아니다.
- streak, XP, 레벨업, 벌점, 연속 출석 보상을 기본 기능으로 두지 않는다.
- 추천을 수행하지 않아도 반복 알림으로 압박하지 않는다.
- 부모가 자유롭게 숨김·보류·삭제할 수 있다.

## AI/자연어 인터페이스

GrowWise 전체 제품은 chat-first가 아니다. 다만 **대화하기 workspace 내부는 대화 이력이 중심인 3-pane 화면**으로 구성한다.

- 전역 검색 진입점과 Ctrl/Cmd + K는 대화하기로 이동한다.
- 대화하기는 왼쪽 대화 목록, 가운데 질문/응답, 오른쪽 백업 보조 패널로 구성한다.
- 답변에는 관련 기록·자료·출처를 근거로 유지하고 근거 부족 상태를 숨기지 않는다.
- AI가 만든 해석에는 provenance/불확실성 표시를 둔다.
- 사용자가 원본 기록과 AI 요약을 혼동하지 않게 한다.
- 중요한 추천은 한 번의 버튼으로 자동 실행하지 않고 부모가 선택/검토한다.

## 디자인 토큰 (초안)

### Light

| 토큰 | 값(예시) | 용도 |
| --- | --- | --- |
| `--bg` | `#FBF9F6` | 따뜻한 오프화이트 배경 |
| `--surface` | `#FFFFFF` | 카드 표면 |
| `--ink` | `#2B2A28` | 본문 |
| `--ink-soft` | `#6B6862` | 보조 텍스트 |
| `--primary` | `#2F8F6B` | 브랜드/성장 |
| `--primary-soft` | `#E3F1EA` | 프라이머리 배경 |
| `--accent` | `#E4A13A` | 제한적 강조 |
| `--info` | `#3B7DD8` | 정보 |
| `--attention` | `#D9903B` | 주의 |
| `--border` | `#ECE7DF` | 경계선 |

빨강은 파괴적 동작·치명적 오류 등 실제 위험에만 사용한다. 미완료·기록 공백·낮은
커버리지에는 사용하지 않는다.

### Dark

라이트와 의미 역할을 동일하게 유지하고 대비 AA를 만족하도록 값만 조정한다.

### 타이포그래피

- 한글/라틴: Pretendard 또는 동등한 OFL/system fallback
- 본문 기본 16px 수준, 줄간격 1.5 이상
- 코드/ID/수치는 등폭 폰트를 선택적으로 사용

### 간격과 형태

- 4px 기반 spacing scale
- 카드 radius 16, 버튼 10, 작은 요소 8을 초기값으로 사용
- 그림자는 낮고 부드럽게 사용

## 핵심 컴포넌트

- **WorkspaceShell**: 브랜드, sidebar, topbar, active workspace frame.
- **WorkspaceNav**: 9개 제품 workspace와 현재 위치를 명확히 표시.
- **ChildAvatar / child switcher**: 현재 child scope가 명확해야 하며 다른 아이 데이터가 섞이지 않는다.
- **ProfileWorkspaceHub**: 프로필 요약 + 학습 기록 / 발달 분석 / 성장 리포트.
- **LearningWorkspaceHub**: 학습 기록 / 관찰 기록.
- **MaterialsWorkspaceHub**: 활동 자료 / 활동 관리 / 참고 자료 / 자료 찾기.
- **PhotoActivityWorkspace**: gallery-first archive + filter + detail + create flow.
- **SearchConversationSection**: history + conversation + backup의 3-pane 구조.
- **Parent review**: 원문/근거/검토 상태를 함께 보여주고 승인/수정/폐기 결정을 명확히 한다.
- **Empty/loading/error**: 비난 없이 다음 행동과 복구 방법을 제시한다.

## 접근성 체크

- 텍스트 대비 AA 이상
- 색 + 아이콘/텍스트 병행
- 키보드 내비게이션과 명확한 focus ring
- `prefers-reduced-motion` 존중
- 확대/글꼴 스케일에서 레이아웃 유지
- 차트와 radar에 텍스트 대체 설명 제공
