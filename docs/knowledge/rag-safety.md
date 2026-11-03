# RAG and safety investigation

현재 근거: source:GW-RAG-DESIGN, source:GW-RAG-CODE, source:GW-SAFETY-CONTRACTS,
source:GW-PR-172.

[Learning Wiki](../learning-wiki.md)는 child-scoped 원본에서 재생성하는 제품 파생 맥락이다.
이 maintainer wiki를 아이 검색 index에 ingest하지 않는다. 이전 wiki를 근거로 다시 합성하지
않고 원본 source fingerprint, source ref와 `derived_from` 관계를 유지한다.

[회귀](../../tests/test_learning_wiki.py)는 존재하지 않는 출처, 진단성 표현, child isolation,
provider 실패와 원격 장기 맥락 경계를 점검한다. 검사가 있다고 모든 미래 모델 출력의 안전성을
보장하는 것은 아니다. [평가 원칙](../evaluation.md)에 따라 근거 없는 확신과 부모 전제 강화,
기록량을 능력으로 오인하는 경우를 계속 조사한다.

열린 조사: 적은 기록과 기록 편향, 오래된 관련 자료의 검색 누락, embedding 실패 후 lexical
검색 품질, 삭제·restore 뒤 파생 맥락, 원본과 파생 요약 사이의 인용 충실도.
private household record 대신 synthetic adversarial fixture로 먼저 재현한다.
