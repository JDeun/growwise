# Material product UX invariants

The desktop material workflow mirrors Core/API/IPC state rather than inventing a second lifecycle.

1. Generation remains available through deterministic templates when the optional LLM is unavailable.
2. The desktop write path saves a deterministic draft first and runs optional LLM enhancement in a
   durable background job. A parent never waits on model inference to preserve the request.
3. Every generated material has two outputs: child-facing material and a parent-facing teaching
   guide. The parent guide also exists in deterministic/no-LLM mode.
4. Parent Review is a visible lane, not a hidden status field.
5. Draft, review-pending, and revision-requested material cannot expose print/PDF actions.
6. Only `approved` material is presented as ready to use.
7. An approved material is registered as a real `ActivityPlan(status=suggested)` quest, so it appears
   in the global Quest Board as `생성됨` before the activity is started.
8. Revision and direct parent editing create immutable successors through existing IPC commands.
9. Selected resource provenance is shown with human-readable titles during review.
10. Rejected/archived material remains recoverable but visually de-emphasized.
11. Busy state disables duplicate mutations and errors are announced with `role=alert`.
12. A printed/used material has a dedicated structured result path. The result becomes a
    `LearningLog(record_kind=material_use)` and can inform later material generation.

## How material generation works

GrowWise uses a **template-first, evidence-grounded, optionally LLM-enhanced** pipeline. The LLM does
not start from an empty prompt and is not allowed to invent a product structure freely.

```text
parent request: kind + topic + public goal
            +
child context: stage + age + interests
            +
verified curriculum alignment
            +
explicitly selected ResourceRecord evidence
            +
private generation guidance from prior structured records
            ↓
deterministic child material + deterministic parent guide
            ↓
save immediately as the authoritative draft
            ↓
optional durable background LLM enhancement
            ↓
scaffold / safety / malformed-output guards
            ↓
review_pending draft
            ↓
Parent Review → approve / edit / request revision / reject
            ↓
approved material → suggested Quest
            ↓
start / complete / skip → structured result record
            ↓
LearningLog feedback → later private guidance + local parent guide
```

The background job exposes `queued → running → completed/failed` state. Model failure never removes
the deterministic draft or its parent guide. Background photo/text jobs share the same execution lock
so local GPU or unified-memory workloads do not compete unnecessarily; interactive chat/query paths
are not put behind that background lock.

### Material families

| kind | parent-facing structure |
| --- | --- |
| `activity_guide` | 준비 → 함께 해 보기 → 관찰 포인트 → 다음 활동 연결 |
| `reading_activity` | 읽기 전 관심 열기 → 함께 읽기·질문 → 아이 해석 듣기 → 생활로 확장 |
| `english_card` | 상황 제시 → 부모 모델링 → 아이 차례 → 단계별 힌트 |
| `math_activity` | 생활 문제 → 실물·그림 탐색 → 단계별 힌트 → 해결 방법 설명 |
| `science_inquiry` | 궁금한 점 → 예측 → 관찰·실험 → 비교·설명 |
| `writing_prompt` | 생각 열기 → 말·그림·글 초안 → 표현 확장 → 돌아보기 |
| `field_trip` | 가기 전 궁금증 → 현장 관찰 → 사진·메모 → 돌아와 연결 |

Each kind has multiple deterministic variants. A stable hash of material kind, stage, and topic
selects a variant, so retrying the same request does not randomly change the basic pedagogical
shape. Infant templates are separately written as parent-led play/observation guides rather than
worksheet-style tasks, and all seven material families remain available for the infant stage.

### Child material vs. parent teaching guide

A material is intentionally a two-output artifact.

- `content_markdown` is the child/activity-facing content.
- `parent_guide_markdown` tells the parent how to prepare, facilitate, scaffold, observe, simplify or
  stop the activity, and what evidence is useful to record afterward.
- `request_goal` is the public goal entered by the parent. It may appear in the child-facing material
  and parent guide.
- `generation_guidance` is ephemeral model-only metadata. It contains generalized continuity or
  revision scaffolding and is never rendered as a goal, label, or metadata block in either output.
- A parent revision request is preserved as `version_note`; it may shape a regenerated version through
  private guidance but is not appended to the learner-visible goal.
- The parent guide is generated deterministically first; optional LLM enhancement may improve it but
  is not required for the guide to exist.
- Direct parent edits preserve the guide instead of silently dropping it from the next version.
- Raw parent result notes are never copied into the child-facing material.

### Content templates vs. presentation templates

GrowWise deliberately separates **what the material says** from **how an approved material is laid
out for use**.

- Content templates define the pedagogical sequence, curriculum alignment, source grounding, and
  deterministic fallback text.
- Presentation templates are desktop-only print metadata. They never change the stored Markdown or
  Parent Review state.
- The normal review screen keeps the existing safe Markdown renderer and parent guide UI.
- When an approved material is printed or exported to PDF, the presentation template adds a dedicated
  writable worksheet page after the material body. If a parent guide exists, a compact copy is placed
  on that worksheet page so the parent does not need a separate third page.
- Quest controls and result-entry UI are never included in the printed output.

| kind | print worksheet | writable zones |
| --- | --- | --- |
| `activity_guide` | 활동 실행 시트 | 준비·환경 / 아이 반응·관찰 / 다음 활동 연결 |
| `reading_activity` | 읽기 대화 시트 | 읽기 전 예상 / 기억에 남은 장면·말 / 읽은 뒤 질문·생활 연결 |
| `english_card` | 영어 표현 카드 시트 | 오늘의 표현 / 아이의 말·몸짓 반응 / 다음에 써볼 상황 |
| `math_activity` | 수학 탐구 시트 | 문제 상황·실물 / 아이의 방법 / 다른 방법·설명 |
| `science_inquiry` | 과학 탐구 시트 | 예측 / 관찰·실험 / 결과·설명 |
| `writing_prompt` | 쓰기 초안 시트 | 말·그림으로 생각 열기 / 첫 초안 / 다시 쓰고 돌아보기 |
| `field_trip` | 현장학습 기록 시트 | 가기 전 궁금증 / 현장 관찰·사진 메모 / 돌아와서 연결 |

The presentation catalog is deterministic and exhaustive for all material kinds. Layout differences
are implemented with print CSS and `data-presentation-layout`; they do not require an LLM and do not
modify the generated content artifact.

### Quest lifecycle and physical-activity result capture

Approval means the material is ready to become an activity, not that the child completed it. The
Desktop therefore registers one real activity quest per approved material and keeps completion and
result capture separate.

```text
approved GeneratedMaterial
        ↓
ActivityPlan: suggested  →  active  →  completed / skipped
        ↓
structured material result
        ↓
LearningLog(record_kind=material_use)
```

The result form stores parent observation, learner work/result, process, child question/reaction,
interest, difficulty, next activity, tags, experience axes, and optional reviewed photo-record links
as separate fields. `GeneratedMaterial → ActivityPlan → LearningLog` relationships are also
represented as first-class entity links. A completed quest is not shown as `결과 기록됨` until an
actual result `LearningLog` exists.

### Closed-loop feedback privacy

Recent `material_use` records and structured independent-learning records may influence later material
generation, but GrowWise separates public output, private model guidance, and local parent context.

- The learner-visible goal is always the parent's original public `request_goal`. Closed-loop signals
  and parent revision notes are never concatenated into that printed goal.
- Material-use `learner_work`, activity process, parent observation, child question, interest,
  difficulty, and next-activity text remain local. Bounded values may be shown in the parent teaching
  guide so the parent can continue from the actual previous activity.
- The optional enhancement model receives only generalized continuity signals such as “learner work
  exists”, “a process was recorded”, “recent difficulty was recorded”, or “a follow-up question
  exists”. Raw material-use text is not inserted into that guidance.
- For independent records such as reading reflection, diary, school/academy learning, self-study, and
  assignments, the parent guide may show bounded parent-entered metadata/summary/process for local
  continuity. Learner-authored `learner_work` is not copied into the next parent guide; only its
  existence becomes a generalized signal.
- General observations and another child's material-use or independent-learning records are not mixed
  into this material feedback snapshot.
- The child-facing worksheet never exposes raw parent difficulty/assessment notes, learner work,
  activity process, internal `generation_guidance`, or revision-note metadata.

This closes the product loop without making a model the authority over the child's record:

```text
create → review → print/use → structured result / independent learning record
       → LearningLog → local parent continuity + private generalized guidance → next material
```

### Curriculum alignment

The template receives deterministic curriculum targets before any model call:

- 0–2: 2024 개정 표준보육과정
- 3–5: 2019 개정 누리과정
- elementary / middle / high: 2022 개정 초·중등학교 교육과정 subject families

GrowWise stores framework/domain mappings and its own paraphrased alignment description. It does not
invent official achievement-standard codes; `standard_codes` remains empty until a code is verified
from curated or official-source data.

### Selected source grounding

Only resources explicitly selected by the parent can ground a material. The API first validates that
each `resource:<uuid>` exists and is visible in the child's scope. It then supplies the generator with
bounded evidence containing the resource title plus saved summary/content excerpt.

- maximum excerpt per selected resource: 4,000 characters
- maximum source-evidence budget passed to a generation: 12,000 characters
- non-selected resource evidence is discarded
- source ref, title, and excerpt are escaped before insertion into the evidence envelope
- resource text is marked as **untrusted evidence**, so prompt-like text inside a saved document is
  never an instruction to the model
- source refs remain attached to the generated material for provenance and review

External discovery results therefore follow this path:

```text
Discovery candidate → parent saves it → ResourceRecord/RAG → parent selects it for generation
→ bounded source evidence → material draft
```

### LLM unavailable or unsafe output

The deterministic template and parent guide are built **before** the optional LLM job. If the provider
is unavailable, times out, returns malformed output, fabricates unsafe content, violates scaffold
rules, or the request/internal guidance contains review-bypass or prompt-injection markers, GrowWise
keeps or restores the deterministic artifact. The resulting material still enters Parent Review
rather than being auto-approved.