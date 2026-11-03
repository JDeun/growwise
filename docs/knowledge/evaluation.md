# Evaluation investigation

현재 근거: source:GW-EVALUATION-DESIGN, source:GW-EVALUATION-CODE,
source:GW-OPERATIONAL-VALIDATION, source:GW-ISSUE-198.

시스템을 평가하며 아이를 평가하지 않는다. [자동 평가](../evaluation.md),
[콘텐츠 rubric](../material-content-qa.md), [운영 검증](../operational-validation.md)을 함께 쓴다.
자동 회귀, 모델 샘플 품질 검토, 실제 앱 흐름, 가정 현장 유용성, 학습 효과를 별도 증거로 관리한다.

baseline PR들이 보고한 CI는 `reported`이며 이를 독립 재현했다고 표기하지 않는다.
[experiment registry](experiments.jsonl)는 다섯 workstream의 실행 예정 계획과
[직접 실행한 위키 회귀](experiments/wiki-validation-20261103.md),
[실제 Core에 연결한 production UI 검증](experiments/live-core-browser-20261103-final.md),
[렌더링 타이포그래피·위계 검증](experiments/design-validation-20261103.md)을 구분한다.
`observed`/`failed` 항목을 추가할 때 날짜·revision·환경·artifact를 빠뜨리면 offline checker가 거부한다.

2026-11-03의 최종 UI run은 합성 입력과 별도 임시 저장소로 14개 흐름을 검증했다.
이전 13개 흐름 기록은 남겨 두고 자료 선택기의 양방향 실제 콘텐츠 전환 검증을 추가했다. native IPC만
테스트 transport로 바꾸고 실제 인증 Core를 사용했으며 business 응답은 mock하지 않았다.
LLM·embedding·vision·외부 보강은 껐다. 이 결과는 native 패키징, 실모델 품질, 실제 가정의
장기 유용성 또는 학습 효과를 증명하지 않는다.

열린 조사: 35 Stage × Kind family와 토픽을 가로지르는 실패 분포, malformed/injection/PII
출력의 fallback, 실제 앱에서 부모 선택 경계와 활동 후 기록 연결, backup/restore 데이터 보존,
정식 패키지 시작·업데이트 복구. 교육 효과와 교사 검증은 해당 현장 연구가 없으면 unknown이다.
