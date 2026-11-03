# Maintainer research wiki

이 위키는 **공개 유지보수 연구·엔지니어링 근거**를 관리한다. 아이별 원본 기록과 파생
[Learning Wiki](../learning-wiki.md)는 제품 데이터이며 이 디렉터리에 복사하지 않는다.
아동 이름·생년·사진·관찰·학습 이력, 가족 데이터 경로, 토큰·인증서·장치 식별자는 넣지 않는다.
벤치마크에는 고정 synthetic fixture와 일반화한 환경 정보만 사용한다.

## Research landscape

| Workstream | 현재 근거와 남은 질문 |
| --- | --- |
| [Curriculum](curriculum.md) | 학년·시행일 resolver와 공식 고시 후보 검토 |
| [Pedagogy](pedagogy.md) | 부모 중심·최소 기록·단계별 scaffold와 현장 유용성 |
| [Models](models.md) | 교체 가능한 로컬 모델과 실제 지연·품질·메모리 |
| [RAG and safety](rag-safety.md) | provenance·child scope·원본 우선과 adversarial 회귀 |
| [Evaluation](evaluation.md) | 자동 회귀와 실사용·교육 효과 증거의 구분 |

[sources.jsonl](sources.jsonl)은 출처·선행 작업의 append-only ledger이고,
[experiments.jsonl](experiments.jsonl)은 재현할 조사·실험의 상태 ledger다.
[ADR index](../adr/README.md)는 채택한 결정과 재검토 조건을 연결한다.

## Evidence vocabulary

- `design`: 저장소에 명시한 설계·정책. 실효성 증거를 뜻하지 않는다.
- `implemented`: 해당 revision에서 코드·테스트가 존재함. 실행 성공을 뜻하지 않는다.
- `reported`: PR·CI·기존 문서가 보고한 결과. 독립 재현 여부는 summary에 명시한다.
- `observed`: artifact·명령·환경·revision과 함께 직접 관찰한 결과.
- `candidate`: 외부 참고 또는 새 고시 후보. 사실 확인·권리·적용성 검토 전이다.

`unknown`은 조사하지 못한 값을 명시한다. 계획 실험은 `planned`로 유지한다. CI 성공,
정상적인 출력 구조, 교육적 유용성, 실제 학습 효과는 서로 다른 주장이다.

## Offline commands

저장소 루트에서 Python 표준 라이브러리만으로 실행한다. 검색·검사는 네트워크·LLM·앱 데이터에
접근하지 않는다. 외부 URL은 HTTPS 구조만 검사하므로 실제 접근성과 내용은 별도 검토 대상이다.

```bash
python scripts/research_wiki.py check
python scripts/research_wiki.py search "scaffold"
python scripts/research_wiki.py search "source:GW-CURRICULUM-CODE"
python scripts/research_wiki.py check --base-ref main
uv run pytest tests/test_research_wiki.py
```

검사는 필수 메타데이터, ID·출처 연결, 다섯 workstream, 실제 수행 실험의 증거,
로컬 링크의 존재와 저장소 경계를 검증한다. `--base-ref`는 기존 ledger 항목의 삭제·수정을
거부한다. CI는 PR base / push 이전 commit과 비교해 이를 강제한다.

## Update lifecycle

1. [research template](templates/research.md)로 질문·가설·근거·반례·한계를 작성한다.
2. 원문 URL 또는 저장소 경로, 확인일, revision/고시 번호, 적용 대상·시행일, 이용 조건을
   source ledger에 새 ID로 추가한다. 외부 원문을 재배포하지 않는다.
3. [experiment template](templates/experiment.md)로 synthetic fixture·명령·모델 revision·환경을
   고정하고 experiment ledger에 `planned` 항목을 추가한다.
4. 실제 수행 후 outcome·실패 분석·재현 방법과 공개 가능한 artifact를 포함한 새 ledger 항목을
   추가한다. 과거 항목을 덮어쓰지 않고 `supersedes`로 이전 ID를 지목한다.
5. 사람이 출처의 신뢰도, 라이선스, 개인정보, 비진단·scaffold 조건을 검토한다. 모델 합성은
   선택적 검토 초안이며 스스로 `candidate`를 승격하거나 제품 정책을 바꾸지 않는다.
6. 결정이 달라지면 ADR을 제안하고 기존 ADR에 superseding 관계를 기록한다. 코드 변경과
   해당 회귀·offline fallback을 별도로 검증한 뒤 문서 상태를 갱신한다.
7. 위 `check`와 테스트를 통과시켜 PR에서 리뷰한다.

## Curriculum watch handoff

기존 [curriculum watcher](../../scripts/check_curriculum_updates.py)의 JSON을 입력으로 사용한다.
live watcher는 네트워크가 필요하고 `--strict`는 후보 발견 시 2를 반환한다.

예약 workflow는 원본 JSON과 변환한 review-only JSONL을 `growwise-curriculum-review`
artifact로 30일 보관한다. 후보를 발견한 `--strict` 실패 상태는 유지하면서 후속 변환·업로드는
실행하므로, 유지보수자가 artifact를 내려받아 출처·적용성·권리를 검토할 수 있다.

```bash
uv run python scripts/check_curriculum_updates.py > /tmp/growwise-curriculum-watch.json
python scripts/research_wiki.py curriculum-candidates /tmp/growwise-curriculum-watch.json
```

변환 명령은 공식 watcher origin을 검증하고 **review-only candidate JSONL을 stdout으로만**
출력한다. 제품 catalog·resolver·ledger를 자동 수정하지 않는다. 후보를 사람이 조사한 뒤
고유 `GW-...` ID·확인일·workstream·summary를 더해 source ledger에 append한다. 시행일·학년과
라이선스를 모르면 `unknown` / 빈 날짜 목록을 유지한다. 실제 runtime 반영은 기존
[교육과정 검증 경계](../curriculum-sources.md)를 통과한 별도 코드·데이터 변경이다.
