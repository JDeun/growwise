# Material product UX invariants

The desktop material workflow mirrors Core/API/IPC state rather than inventing a second lifecycle.

1. Generation remains available through deterministic templates when the optional LLM is unavailable.
2. Parent Review is a visible lane, not a hidden status field.
3. Draft, review-pending, and revision-requested material cannot expose print/PDF actions.
4. Only `approved` material is presented as ready to use.
5. Revision and direct parent editing create immutable successors through existing IPC commands.
6. Selected resource provenance is shown with human-readable titles during review.
7. Rejected/archived material remains recoverable but visually de-emphasized.
8. Busy state disables duplicate mutations and errors are announced with `role=alert`.

## How material generation works

GrowWise uses a **template-first, evidence-grounded, optionally LLM-enhanced** pipeline. The LLM does
not start from an empty prompt and is not allowed to invent a product structure freely.

```text
parent request: kind + topic + goal
            +
child context: stage + age + interests
            +
verified curriculum alignment
            +
explicitly selected ResourceRecord evidence
            ↓
deterministic material template
            ↓
optional LLM enhancement
            ↓
scaffold / safety / malformed-output guards
            ↓
review_pending draft
            ↓
Parent Review → approve / edit / request revision / reject
```

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
worksheet-style tasks.

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
- resource text is marked as **untrusted evidence**, so prompt-like text inside a saved document is
  never an instruction to the model
- source refs remain attached to the generated material for provenance and review

External discovery results therefore follow this path:

```text
Discovery candidate → parent saves it → ResourceRecord/RAG → parent selects it for generation
→ bounded source evidence → material draft
```

### LLM unavailable or unsafe output

The deterministic template is built **before** the optional LLM call. If the provider is unavailable,
times out, returns malformed output, fabricates unsafe content, violates scaffold rules, or the
request contains review-bypass/prompt-injection markers, GrowWise keeps or restores the deterministic
template. The resulting artifact still enters Parent Review rather than being auto-approved.
