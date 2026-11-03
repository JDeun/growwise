# Curriculum investigation

현재 근거: source:GW-CURRICULUM-DESIGN, source:GW-CURRICULUM-CODE,
source:GW-CURRICULUM-WATCH, source:GW-PR-182.

학년과 기준일에 따라 2015/2022 개정 및 일부개정 적용을 나누는 구현이 있다.
정확한 notice·시행일은 [resolver](../../src/growwise/curriculum_versions.py)와
[회귀 세트](../../tests/test_curriculum_versioning.py)를 함께 검토한다.
현재 ledger는 baseline repository metadata를 기록하며, 공식 고시 원문을 새로 독립 검증했다는
주장을 하지 않는다. 공식 문서의 시행 범위·최신성·원문 이용 조건은 적용 변경 전에 재확인한다.

| 계열 | 저장소에 기록된 기준 | 적용 범위·날짜 | 근거 수준 |
| --- | --- | --- | --- |
| 영아 | 2024 개정 표준보육과정, 교육부고시 제2024-23호 | 0–2세, 2025-03부터 | baseline catalog metadata |
| 유아 | 2019 개정 누리과정 | 3–5세; 구체 고시별 시행일은 원문 재확인 | baseline catalog metadata |
| 학교 | 2022 개정, 국가교육위원회고시 제2024-3호 | 2024 초1–2, 2025 초3–4/중1/고1, 2026 초5–6/중2/고2, 2027 중3/고3; 각 03-01 | baseline resolver implementation |
| 일부개정 | 국가교육위원회고시 제2026-1호 | 고1–2: 2026-03-01, 고3: 2027-03-01, 초1–2: 2028-03-01 | baseline resolver implementation |

공식 URL과 notice는 [bundled catalog](../../src/growwise/adapters/official_curriculum_catalog.py)에
남긴다. source license는 원문별 재확인 대상이며 링크·메타데이터·자체 설명만 관리한다.

열린 조사: 새 고시의 실제 적용 학년, 개정 계열과 일부개정의 차이, 혼합 전환기의 불확실성,
공식 페이지 변경 시 watcher 탐지 누락. watcher 결과는 candidate이며 자동 채택 근거가 아니다.
재현 명령과 후보 수용 절차는 [wiki workflow](README.md)에 있다.
