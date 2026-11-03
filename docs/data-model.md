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
| `child_profile` | 로컬 학습자 프로필 | stage, birth_date/age_months/grade, 언어, interests/preferences, learning_goals, notes |
| `resource` (`kind=book` 등) | 도서·웹·메모·공식 근거 | title, author, summary/content, source_url, tags, provenance; 독서 시각은 연결된 LearningLog.occurred_at |
| 활동 템플릿 | 별도 저장 엔티티가 아닌 generator catalog | kind/stage/topic별 결정적 활동 본문과 교안 |
| `activity_plan` | 아이별 활동/퀘스트 인스턴스 | child_id, title, status, source_refs, 경험 축, 시작/완료/건너뜀 시각 |
| `generated_material` | AI/규칙 기반 생성 산출물 | content_markdown, parent_guide_markdown, generator_mode, source_refs, status, version |
| `learning_log` | 핵심 학습/관찰 기록 | occurred_at, process, parent_observation, book_id, ai_hint, evidence_checked, child_reexplanation, next_activity |
| 경험 커버리지 | 별도 competency_observation 엔티티가 아닌 재계산 projection | LearningLog.experience_axes/tags/occurred_at → GrowthMap의 layer/axis/count |
| 부모 검토 | 별도 parent_review 엔티티가 아닌 산출물 상태·검토 checkpoint | GeneratedMaterial.status/review_note + LangGraph 검토 상태 |
| `workflow_run` | LangGraph 실행 추적 | workflow_type, thread_id, status, attempt_count, input_ref/output_ref, last_error_code |

이 표는 현재 저장 모델을 설명한다. 초기 설계의 `ai_exposure_level`은 현재 typed profile
필드가 아니며 AI 사용 관련 부모 메모는 `notes`에 기록할 수 있다. `institution_profile`과
`classroom_context`는 후속 기관용 설계 후보이며 현재 사용 가능한 저장 엔티티가 아니다.

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

실제 저장 필드:

- `id`, `child_id`, `kind`, `content_markdown`, `status`, `version`
- `generator_mode`, `generator_version`: 기본 구성·AI 보강·부모 수정 여부와 생성 규칙 버전
- `model_provider`, `model_id`: AI 보강이 실제 채택된 경우의 provider와 모델 식별자
- `source_refs[]`, `parent_material_id`: 실제 근거와 이전 버전 계보
- `ai_job_id`: 백그라운드 생성에 사용한 실제 durable job ID. 동기 생성이나 이전 자료에는 없을 수 있다.
- `review_decision`, `reviewed_at`, `review_note`: 실제 부모 결정과 그 시각·메모
- `created_at`, `updated_at`

`source_refs`는 citation fabrication을 검증할 수 있도록 실제 retriever/adaptor 결과와 연결된다.
자료 생성은 별도 `workflow_run_id`를 만들었다고 가정하지 않는다. 백그라운드 실행 연결은
`ai_job_id`로 추적하며, 자료 검토 checkpoint는 자료 ID를 사용한다. 기본 양식이나 실패 후
fallback은 시도했던 모델을 작성 모델로 표시하지 않는다. 부모 수정본은 새로운 producer를
`parent_edit`로 기록하고 모델 식별자를 비우며, 원본의 provenance는 이전 버전 계보에 남긴다.
이 필드가 없는 이전 자료도 읽을 수 있고, 알 수 없는 모델·검토 시각을 추정해 채우지 않는다.

## ParentReview

| 필드 | 의미 |
| --- | --- |
| `GeneratedMaterial.id` | 검토 대상 |
| `status` | 현재 상태. 보관하면 `archived`가 된다. |
| `review_decision` | 마지막 실제 부모 결정: approved / revision_requested / rejected |
| `review_note` | 선택적 수정·거절 메모 |
| `reviewed_at` | 실제 부모 결정 시각. 보관이나 다른 갱신으로 덮어쓰지 않는다. |

부모의 **이 활동 사용하기** 또는 상세 검토 결정은 명시적 사용 승인·수정 요청·거절이다.
연령 적합성, 민감 내용, 개인정보, scaffold, grounding은 검토 기준이며 개별 부모 확인
checkbox나 통과 인증으로 저장하지 않는다. 자동 생성 시 적용하는 안전·출처·구조 gate도
부모의 교육적 적합성 판단을 대신하지 않는다.

LangGraph human-in-the-loop checkpoint와 연결해 앱 재시작 후에도 검토를 이어간다.
실제 checkpoint 결정에는 `decision_status`, `decision_note`, `decision_at`을 남기며,
정본 자료의 결정·시각은 checkpoint 복구 가능 여부와 무관하게 보존한다.

## LearningWiki — 파생 장기 맥락

`learning_wiki`는 원본 학습 기록을 대체하지 않는 rebuildable child-scoped entity다.

| 필드 | 의미 |
| --- | --- |
| `child_id` | 대상 아이 |
| `summary` | 짧은 파생 요약 |
| `content_markdown` | 장기 맥락 Wiki 본문 |
| `source_refs[]` | 이번 revision을 만든 원본 기록 |
| `source_fingerprint` | canonical 원본 집합 SHA-256 |
| `generator_mode` | `llm_wiki` / `deterministic_projection` |
| `model_provider/model_id` | 사용한 모델 provenance |
| `revision` | source 변화/rebuild revision |
| `derived` | 항상 true |
| `rebuilt_at` | 마지막 합성 시각 |

**Invariant:** Wiki는 기존 Wiki를 evidence로 다시 합성하지 않는다. 각 LLM item은 현재 허용된
`source_refs` 중 최소 하나를 가져야 하며, 원본과의 관계는 `derived_from` link로 유지한다.

## LearningLog — 핵심 데이터

GrowWise의 중심은 활동지 자체보다 **아이의 질문·시도·부모 관찰·검증·자기 언어 재구성**이다.

| 필드 | 뜻 |
| --- | --- |
| `occurred_at?` | 실제 사건 날짜/시각, 이전 기록은 created_at으로 대체 |
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
현재 원본은 `learning_log`의 경험 축·태그·관찰이며, radar 값은 재계산 가능한 projection이다.
별도의 `competency_observation` entity를 저장하지 않는다.

## WorkflowRun

`WorkflowRun`의 실제 저장 필드는 다음과 같다. 현재 동기 관찰 수집 경로
(`api/main.py`의 `observation_ingest`)가 생성·완료/실패와 출력 기록 ref를 저장한다.
자료 background 작업의 실행 식별자는 이 entity가 아니라 자료의 `ai_job_id`와 durable queue에
있고, 자료 검토 재개 상태는 LangGraph checkpoint에 있다.

- `workflow_type`
- `thread_id` (checkpoint 자체는 LangGraph checkpointer에 보관)
- `child_id`
- `input_ref?`, `output_ref?`
- `status` (`running`, `waiting_review`, `completed`, `failed`, `cancelled`)
- `attempt_count`
- `last_error_code?`
- `created_at`, `updated_at`

LLM의 전체 chain-of-thought는 저장하지 않는다. 제품에 필요한 입력/출력, 검증 결과, 사용자
결정, provenance만 기록한다.

## 관계

```text
child_profile
 ├─ activity_plan ─→ learning_log (관찰·과정·경험 축)
 ├─ generated_material (status/review_decision/reviewed_at/review_note)
 │          └────────────→ ai_job_id + durable queue / LangGraph review checkpoint
 ├─ observation_ingest ─→ workflow_run ─→ learning_log (output_ref)
 ├─ resource(kind=book) ─→ learning_log.book_id
 └─ photo_activity_record ─→ photo_asset / learning_log

entity_link ─→ 원본 간 provenance / 다른 아이와의 child_scope 공유
learning_wiki ─→ 원본 source_refs에서 다시 계산하는 파생 문서
```

## Markdown SoT + SQLite Projection

- 원본 파일 write는 temp file → fsync 가능한 범위 → atomic rename 패턴을 사용한다.
- 인덱스 쓰기 실패가 원본 쓰기를 손상시키면 안 된다.
- SQLite를 지운 뒤 Markdown만으로 rebuild하는 테스트를 CI에 둔다.
- Markdown parse 실패 파일은 인덱스 rebuild에서 건너뛰고 `last_rebuild_skipped`에 보고한다.
  원본을 자동으로 이동·삭제하지 않는다. 지원하지 않는 schema version은 rebuild를 중단하고
  이전 인덱스를 보존한다. `.bak` 세대 복구는 검증 후 명시적으로 수행한다.
- `schema_version`별 migration/parser를 제공해 오래된 기록을 잃지 않는다.
- child scope와 기간별 원본 Markdown·참조 asset ZIP은 [기록 내보내기](record-export.md)를 따른다.
  전체 백업과 다른 manifest를 사용하며 전체 복원에 넣을 수 없다.
