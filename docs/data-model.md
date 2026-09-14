# 데이터 모델 (초안)

개인용/기관용 공용으로 쓸 수 있도록 설계한 엔티티 초안이다. 실제 구현에서 필드는
확장될 수 있다.

> **개인정보 원칙**: `child_profile`을 포함해 어떤 엔티티에도 아이의 실명·생년·주소·
> 사진·음성 원본을 이 저장소나 외부로 내보내지 않는다. 프로필 값은 로컬 설정으로만
> 채우며, 저장소에는 스키마와 예시(값 없는 형태)만 둔다.
> ([privacy-and-safety.md](privacy-and-safety.md))

## 엔티티

| 엔티티 | 설명 | 주요 필드(초안) |
| --- | --- | --- |
| `child_profile` | 학습자 프로필(로컬 전용) | 연령, 관심사, 언어 수준, 주의할 점, **발달 단계(`stage`), AI 노출 수준(`ai_exposure_level`)** |
| `book` | 도서 | 제목, 저자, 난이도, 주제, 읽은 날짜 |
| `activity` | 활동 정의 | 활동 유형, 목표, 소요 시간, 자료 |
| `generated_material` | 생성 산출물 | 활동지, 카드, 질문, 수업안 |
| `learning_log` | **학습 대화 로그(핵심)** | 질문·풀이 과정·AI 힌트·부모 관찰·검증 근거·자기 언어 재구성·흥미·다음 활동(아래 상세) |
| `competency` | 역량 | 읽기, 말하기, 쓰기, 수학, 탐구, 사회성 |
| `parent_review` | 검토 결과 | 부모/교사의 검토 결과와 수정 사항 |
| `institution_profile` | 기관 프로필 | 기관명, 연령대, 수업 유형, 출력 포맷 |
| `classroom_context` | 학급 맥락 | 반 수준, 인원, 수업 시간, 주제 |

## 관계(개념)

- `activity` → `generated_material`: 하나의 활동 정의로 여러 산출물이 생성될 수 있다.
- `generated_material` → `parent_review`: 산출물은 노출 전 검토를 거친다.
- `activity` / `book` → `learning_log`: 활동·도서 수행 후 기록이 남는다.
- `learning_log` → `competency`: 기록은 역량 관찰로 요약될 수 있다(점수화가 아님).
- `institution_profile` + `classroom_context`: 기관용에서 반 단위 맥락을 담는다.

## 개인용 ↔ 기관용

- 개인용은 `child_profile` + `book`/`activity`/`generated_material`/`learning_log` 중심.
- 기관용은 여기에 `institution_profile` + `classroom_context`를 더해 반 단위로 확장한다.
- 동일 스키마를 공유하므로 개인용에서 기관용으로 재구조화 없이 넘어간다.

## `learning_log` 상세 — 학습 대화 로그

growwise의 핵심은 "문제지 생성기가 아니라 **학습 대화 기록장**"이다([pedagogy.md](pedagogy.md)).
따라서 `learning_log`는 점수가 아니라 **생각의 과정**을 남긴다. 필드(초안):

| 필드 | 뜻 |
| --- | --- |
| `date`, `activity_id`, `book_id?` | 언제, 어떤 활동/책에 대한 기록인가 |
| `child_question` | 아이가 스스로 만든 질문 |
| `process` | 풀이·시도 과정(정답 여부가 아니라 경로) |
| `ai_hint` | AI가 준 힌트/반론(정답 대납이 아니라 scaffold) |
| `parent_observation` | 부모의 관찰(흥미·집중·태도) |
| `evidence_checked` | 검증한 근거·출처(검증력 훈련의 흔적) |
| `child_reexplanation` | 아이가 **자기 언어로 다시 설명**한 최종본 |
| `interest`, `difficulty` | 흥미 변화·어려웠던 지점(점수 아님) |
| `next_activity` | 다음에 해볼 활동 추천 |

> 점수·낙인 필드는 두지 않는다. `ai_hint`에는 "얼마나 스스로 하게 남겼는가(과도한 도움
> 경계)"를 함께 기록해 코치 모듈 개선의 근거로 쓴다([references.md](references.md) TutorMoments).

## 저장 방식 — 하이브리드 (확정)

- **Markdown = 원본(Source of Truth)**. 각 기록/생성물은 사람이 읽고 소유·이식할 수 있는
  Markdown 파일로 남긴다(예: `records/2026-09-10-tour-<slug>.md`). PAIDEIA의 "마크다운
  소유권" 원칙([references.md](references.md))을 따른다.
- **SQLite = 인덱스/캐시**. 검색·역량 추적·집계용. **Markdown에서 언제든 재생성 가능**한
  파생물이라 손실돼도 원본에서 복구된다.
- 둘 다 데스크탑 로컬. 아동 데이터는 저장소(git)에 올리지 않는다([privacy-and-safety.md](privacy-and-safety.md)).
- **이식성 보장**: 아이의 모든 기록을 Markdown 묶음으로 내보낼 수 있어야 한다(SaaS 잠김 방지).
