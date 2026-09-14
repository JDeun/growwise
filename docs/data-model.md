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
| `child_profile` | 학습자 프로필(로컬 전용) | 연령, 관심사, 언어 수준, 주의할 점 |
| `book` | 도서 | 제목, 저자, 난이도, 주제, 읽은 날짜 |
| `activity` | 활동 정의 | 활동 유형, 목표, 소요 시간, 자료 |
| `generated_material` | 생성 산출물 | 활동지, 카드, 질문, 수업안 |
| `learning_log` | 학습 기록 | 반응, 어려움, 흥미, 다음 추천 |
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

## 저장 방식(미정)

학습 기록을 Markdown 중심으로 둘지, 별도 SQLite 앱 데이터로 둘지는 아직 결정 전이다
([roadmap.md](roadmap.md) 미해결 질문 참고). 어느 쪽이든 로컬 우선 원칙을 지킨다.
