# Learning Wiki

GrowWise의 Learning Wiki는 아이의 원본 기록을 대신하는 새 정본이 아니라, 여러 기록 사이의
연결을 계속 유지하기 위한 **재생성 가능한 파생 지식층**이다.

아이의 질문·관찰·활동 결과·학습 기록이 쌓일 때마다 원본만 직접 검색하는 대신, 최근 관심,
반복 질문, 이미 해본 경험, 열린 흐름, 다음 연결 후보를 하나의 Markdown 문서로 합성한다.

```text
Authoritative records
  learning_log
  activity_plan
  study progress / reflection
        ↓
source-grounded synthesis
        ↓
Learning Wiki (derived Markdown)
        ↓
RAG / graph context / conversation / material generation
```

## 핵심 원칙

1. **원본 우선**
   - `learning_log`, `activity_plan`, 학습 기록이 정본이다.
   - Learning Wiki는 언제든 삭제하고 다시 만들 수 있는 derived artifact다.
2. **자기참조 금지**
   - 새 Wiki를 만들 때 기존 Wiki를 evidence로 사용하지 않는다.
   - 매번 원본 기록 집합만으로 source fingerprint를 계산하고 합성한다.
3. **근거 없는 항목 금지**
   - LLM structured output의 각 항목은 현재 원본 집합에 존재하는 `source_ref`를 최소 하나
     가져야 한다.
   - 존재하지 않는 source ref가 붙은 항목은 저장 전에 제거한다.
4. **명시적 연결**
   - Wiki와 원본은 `derived_from` entity link로 연결한다.
   - source가 사라지면 다음 refresh에서 stale link를 제거한다.
5. **비진단**
   - 또래 비교, 발달 진단, 고정된 능력·성격 추론을 Wiki에 넣지 않는다.
   - 위험 marker가 있는 model item은 저장 전에 거부한다.
6. **LLM optional**
   - 모델이 없거나 실패하면 deterministic projection으로 Wiki를 만든다.
   - LLM 합성에서 빠진 명시적 `next_activity`, `next_step`, `open_question` 등은
     deterministic projection으로 보완한다.

## 문서 구조

현재 Wiki는 다음 섹션을 가진다.

- 현재 요약
- 최근 관심과 반복 주제
- 반복되거나 이어지는 질문
- 이미 해본 경험
- 아직 열린 흐름
- 다음에 이어볼 연결

각 항목은 Markdown에 원본 source ref를 함께 기록한다.

```markdown
## 반복되거나 이어지는 질문

- 씨앗은 왜 날아가?
  - 근거: `learning_log:<uuid>`
```

## 업데이트 방식

`LearningWikiService.refresh(child_id)`는 child-scoped 원본을 모아 canonical JSON fingerprint를
계산한다. LLM synthesis는 loopback model provider일 때만 수행하며, 일반 text provider가 원격이면
원본 장기 기록을 외부로 보내지 않고 deterministic projection을 사용한다.

- fingerprint가 기존 Wiki와 같으면 재생성하지 않는다.
- 원본이 추가·수정·삭제되면 fingerprint가 달라져 새 revision을 만든다.
- `force=True`는 수동 rebuild에 사용한다.
- 대화와 자료 생성처럼 장기 맥락이 실제로 필요한 경로에서는 사용 직전에 refresh한다.

API:

```text
GET  /v1/children/{child_id}/learning-wiki
POST /v1/children/{child_id}/learning-wiki/rebuild
```

## Retrieval integration

`ChildContextService`는 `learning_wiki`를 일반 child context entity와 함께 검색한다.

따라서 질의 시:

```text
direct records
     +
Learning Wiki
     +
RAG chunks
     +
1-hop document graph
     ↓
grounded answer
```

구조가 된다.

Wiki는 검색 비용을 줄이고 장기 흐름을 보존하는 보조 context이며, 답변의 최종 근거를 원본보다
높은 신뢰도로 취급하지 않는다.

## Material generation integration

자료 생성 직전에 Wiki를 refresh한다. **실제 generation provider가 loopback일 때만** 최대
6,000자의 Wiki context를 `generation_guidance`로 전달한다. 원격 provider에는 Wiki 본문을
전달하지 않는다.

이 guidance는 untrusted private context로 escape된 delimiter 안에 들어가며 learner-facing 산출물의
메타데이터로 출력하지 않는다. 기존 자료 생성기의
prompt-injection/scaffold/quality gate와 동일하게 private generation context로 취급한다.

## 개인정보와 삭제

Learning Wiki는 `child_id`를 가진 Markdown entity다. 따라서 child purge 대상에 자동 포함된다.

- Wiki Markdown 및 `.bak`
- SQLite projection
- Wiki에서 원본으로 향하는 `derived_from` links

가 함께 삭제된다. 과거 backup ZIP은 기존 privacy contract에 따라 별도 historical snapshot으로
남을 수 있다.

## 회귀 테스트

`tests/test_learning_wiki.py`는 최소 다음을 검증한다.

- 동일 source fingerprint에서 revision이 불필요하게 증가하지 않음
- 원본 변경 시 revision/fingerprint 갱신
- `derived_from` provenance link
- 존재하지 않는 source ref 제거
- 진단성/위험 model item 제거
- evidence delimiter escaping
- child contextual retrieval에서 Wiki 사용
