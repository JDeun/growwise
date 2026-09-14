# 데이터 모델

개인용을 우선하지만 기관용 확장을 막지 않는 공용 도메인 모델이다. GrowWise의 핵심 데이터는
점수표가 아니라 **활동·관찰·학습 과정의 장기 기록**이다.

## 공통 메타데이터

Markdown SoT의 모든 엔티티는 최소한 아래 메타데이터를 가진다.

| 필드 | 의미 |
| --- | --- |
| `schema_version` | 파일/엔티티 스키마 버전 |
| `id` | UUIDv7 계열 안정 ID |
| `entity_type` | 엔티티 종류 |
| `child_id` | 아이별 데이터인 경우 연결 키 |
| `created_at` | timezone 포함 ISO-8601 |
| `updated_at` | timezone 포함 ISO-8601 |

예:

```yaml
---
schema_version: 1
id: 0199...
entity_type: learning_log
child_id: 0199...
created_at: 2026-09-14T16:00:00+09:00
updated_at: 2026-09-14T16:00:00+09:00
---
```

SQLite는 이 Markdown을 읽어 언제든 재생성 가능한 projection/index다.

## 개인정보 원칙

- 아이 실명·정확한 생년월일·주소·사진·음성 원본을 저장소(git)에 넣지 않는다.
- 로컬 프로필은 앱 데이터 디렉터리에만 저장한다.
- 외부 모델/API로 보내기 전 별도의 privacy policy/gate를 통과한다.
- 예제와 fixture는 모두 합성 데이터만 사용한다.

## 다자녀

`child_profile`은 다중 인스턴스다. 아이별 엔티티는 모두 `child_id`로 분리한다. UI의 아이
전환은 표시상의 필터가 아니라 repository query 자체의 scope가 바뀌는 방식으로 구현한다.

## 핵심 엔티티

| 엔티티 | 설명 | 주요 필드 |
| --- | --- | --- |
| `child_profile` | 로컬 학습자 프로필 | stage, 월령/연령 범주, 관심사, 언어 수준, 주의점, ai_exposure_level |
| `book` | 도서 메타데이터 | title, author, topic, source/provenance, read_at |
| `activity` | 재사용 가능한 활동 템플릿 | type, goals, estimated_duration, materials, curriculum_tags |
| `activity_plan` | 아이별 활동/퀘스트 인스턴스 | child_id, activity_id, status, optional schedule |
| `generated_material` | AI/규칙 기반 생성 산출물 | content, generator, sources, status, version |
| `learning_log` | 핵심 학습/관찰 기록 | process, parent_observation, evidence, reexplanation, next_activity |
| `competency_observation` | 성장 지도 계산용 관찰 이벤트 | layer, axis, tags, observed_at, source_log_id |
| `parent_review` | human review 결과 | decision, checklist, notes, reviewed_at |
| `workflow_run` | LangGraph 실행 추적 | workflow_type, checkpoint/thread id, status, errors |
| `institution_profile` | 후속 기관용 | 기관 설정 |
| `classroom_context` | 후속 기관용 | 학급 맥락 |

## 발달 단계

`child_profile.stage`:

- `INFANT_0_2`
- `PRESCHOOL_3_5`
- `ELEMENTARY`
- `MIDDLE`
- `HIGH`

영아 모드는 월령에 민감하므로 내부적으로 `age_months` 또는 월령 band를 계산할 수 있지만,
발달 성취 판정이나 또래 percentile을 만들지 않는다.

## ActivityPlan 상태

```text
SUGGESTED → ACTIVE → COMPLETED
     └────────────→ SKIPPED
```

- `SKIPPED`는 실패가 아니다.
- streak/연속완료 압박을 만들지 않는다.
- 완료 시 필요하면 `learning_log`를 생성한다.

## GeneratedMaterial 상태 머신

생성물 노출 정책은 다음 enum으로 강제한다.

```text
DRAFT
  ↓
REVIEW_PENDING
  ├─→ REVISION_REQUESTED ─→ DRAFT
  ├─→ REJECTED
  └─→ APPROVED ─→ ARCHIVED
```

권장 enum:

```python
class MaterialStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_PENDING = "review_pending"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"
```

**Invariant:** `APPROVED`가 아닌 생성물은 최종 export/아이 노출 대상으로 사용할 수 없다.
이 규칙은 UI가 아니라 application/domain layer에서 검사한다.

## GeneratedMaterial provenance

최소 필드:

- `id`, `child_id`, `material_type`
- `content`
- `status`
- `version`
- `model_provider`, `model_id`
- `prompt_template_id` 또는 generator version
- `source_refs[]`
- `workflow_run_id`
- `created_at`, `updated_at`

`source_refs`는 citation fabrication을 검증할 수 있도록 실제 retriever/adaptor 결과와 연결된다.

## ParentReview

| 필드 | 의미 |
| --- | --- |
| `material_id` | 검토 대상 |
| `decision` | approve / revise / reject |
| `age_appropriate` | 연령 적합 |
| `sensitive_content_ok` | 민감 내용 |
| `privacy_ok` | 개인정보 |
| `scaffold_ok` | 정답 대납 여부 |
| `grounding_ok` | 근거/출처 확인 |
| `notes` | 수정 메모 |
| `reviewed_at` | 검토 시각 |

LangGraph human-in-the-loop checkpoint와 연결해 앱 재시작 후에도 검토를 이어간다.

## LearningLog — 핵심 데이터

GrowWise의 중심은 활동지 자체보다 **아이의 질문·시도·부모 관찰·검증·자기 언어 재구성**이다.

| 필드 | 뜻 |
| --- | --- |
| `date` | 기록 날짜 |
| `activity_plan_id?` | 관련 활동 |
| `book_id?` | 관련 책 |
| `child_question` | 아이가 만든 질문, 영아는 비어 있을 수 있음 |
| `process` | 시도·풀이·상호작용 과정 |
| `ai_hint` | 부모에게 제공된 scaffold/힌트 |
| `parent_observation` | 흥미·집중·반응 등 정성 관찰 |
| `evidence_checked` | 근거/출처 검증 |
| `child_reexplanation` | 자기 언어 재설명; 연령에 따라 선택 |
| `interest` | 정성적 관심 변화 |
| `difficulty_note` | 어려웠던 지점의 메모; 점수화 금지 |
| `next_activity` | 다음 활동 후보 |
| `tags` | 성장 지도/검색용 관찰 태그 |

영아에서는 `child_question`, `child_reexplanation`을 강제하지 않고 상호작용·반응·관찰 중심으로
사용한다.

## 성장 지도

기존 `competency`를 하나의 숫자 테이블로 저장하지 않고 **관찰 이벤트에서 projection으로
계산**하는 것을 기본으로 한다.

세 층:

1. 전인 고정축: 신체, 정서/인성, 표현/예술, 사고/탐구, 사회성
2. 학습 6축: 읽기, 말하기, 쓰기, 수학, 탐구, 사회성
3. 연령 적응형 축: 영아 발달영역 / 학령기 교과·역량

표시 값은 정답률이나 또래 대비가 아니라 일정 기간의 **경험/관찰 커버리지와 다양성**이다.
원본은 `learning_log`와 `competency_observation`, radar 값은 재계산 가능한 projection이다.

## WorkflowRun

LangGraph 실행의 재현·복구를 위해 기록한다.

- `workflow_type`
- `thread_id/checkpoint_id`
- `child_id`
- `input_ref`
- `state` (`running`, `waiting_review`, `completed`, `failed`, `cancelled`)
- `attempt_count`
- `last_error_code?`
- `created_at`, `updated_at`

LLM의 전체 chain-of-thought는 저장하지 않는다. 제품에 필요한 입력/출력, 검증 결과, 사용자
결정, provenance만 기록한다.

## 관계

```text
child_profile
 ├─ activity_plan ─→ learning_log ─→ competency_observation
 ├─ generated_material ─→ parent_review
 │          └────────────→ workflow_run
 └─ book ────────────────→ learning_log
```

## Markdown SoT + SQLite Projection

- 원본 파일 write는 temp file → fsync 가능한 범위 → atomic rename 패턴을 사용한다.
- 인덱스 쓰기 실패가 원본 쓰기를 손상시키면 안 된다.
- SQLite를 지운 뒤 Markdown만으로 rebuild하는 테스트를 CI에 둔다.
- Markdown parse 실패 파일은 격리하고 diagnostics를 제공한다.
- `schema_version`별 migration/parser를 제공해 오래된 기록을 잃지 않는다.
- export는 child scope와 기간을 지정해 portable Markdown bundle로 만들 수 있어야 한다.
