# growwise

**AI 기반 아동 학습자료 생성 · 학습기록 시스템**

부모가 아이의 관심사와 성장 기록을 바탕으로 집에서 바로 쓸 수 있는 학습자료를 만드는
보조 도구다. **개인이 운영하는 홈스쿨링용 데스크탑 앱**으로 작게 시작하는 것이 현재
목표이며(홈서버·상시 백엔드 불요, 오프라인 우선), 구조는 나중에 유치원·어린이집·학원용
교사 자료 제작으로 확장될 수 있게 설계한다.

> 핵심 방향: growwise는 **문제지 생성기가 아니라 학습 대화 기록장**에 가깝다.
> 중요한 데이터는 정답이 아니라 아이의 질문, 풀이 과정, 부모의 관찰,
> 다음에 해볼 활동이다.

---

## 무엇인가

- 책·연령·목표를 입력하면 **독서 활동지, 영어 대화 카드, 탐방/여행 활동지,
  수학 놀이, 글쓰기·말하기 활동**을 만드는 자료 생성기
- 날짜·자료·아이 반응·어려웠던 점·다음 활동을 남기는 **학습 기록장**
- 아이에게 보여주기 전 난이도·민감성·개인정보를 점검하는 **부모 검토 계층**

## 무엇이 아닌가

- 아이를 대신해 답을 주는 자율 튜터가 **아니다**. AI는 부모·교사가 자료를 만들고
  질문을 설계하도록 돕는 조수 역할만 한다.
- 아이를 점수화·서열화하는 평가 도구가 **아니다**. 기록은 점수보다 관찰과
  흥미 변화 중심이다.
- 완전한 홈스쿨링 대체가 **아니다**. 가족 대화·동네 탐방·체험까지 포함하는
  학습을 부모가 다루도록 보조한다.

## 핵심 원칙

1. **부모 검토 우선** — 생성물은 아이에게 보여주기 전 부모·교사가 검토한다.
2. **로컬 우선** — 아이의 사진·음성·위치·실명은 기본적으로 로컬에서만 처리한다.
3. **관찰 중심 기록** — 점수·낙인 대신 관찰·흥미·다음 활동을 남긴다.
4. **외부 전송 최소화** — 외부 API로 나가는 데이터를 최소화한다.
5. **확장 가능한 구조** — 개인용에서 기관용으로 재구조화 없이 성장한다.

자세한 내용은 [docs/privacy-and-safety.md](docs/privacy-and-safety.md) 참고.

## 현재 상태

**설계 단계 (pre-alpha).** 이 저장소는 지금 제품 설계 문서와 최소 스캐폴드만
담고 있다. 코드 구현은 아직 시작 전이며, 첫 마일스톤은
[docs/roadmap.md](docs/roadmap.md)에서 정한다.

## 문서

| 문서 | 내용 |
| --- | --- |
| **[docs/pedagogy.md](docs/pedagogy.md)** | **교육 원칙과 사상 — 제품의 중심. 먼저 읽을 것** |
| [docs/vision.md](docs/vision.md) | 제품 비전 요약 — 왜 만드는가 |
| [docs/product-spec.md](docs/product-spec.md) | 개인용 MVP·핵심 기능·기관용 확장 |
| [docs/architecture.md](docs/architecture.md) | 데스크탑 앱 아키텍처·모듈·기술 스택 후보 |
| [docs/data-model.md](docs/data-model.md) | 데이터 모델(엔티티) 초안 |
| [docs/integrations.md](docs/integrations.md) | 외부 API·데이터 소스와 어댑터 설계 |
| [docs/references.md](docs/references.md) | 선행 사례 분석과 빌려오는 점(PAIDEIA·DeepTutor·TutorMoments 등) |
| [docs/privacy-and-safety.md](docs/privacy-and-safety.md) | 안전·개인정보 원칙과 저장소 규칙 |
| [docs/curriculum-sources.md](docs/curriculum-sources.md) | 과목별 기준 자료·공개 API 후보 |
| [docs/roadmap.md](docs/roadmap.md) | 제품화 단계와 미해결 설계 질문 |

코드 구조는 [src/growwise/README.md](src/growwise/README.md)를 참고한다.

## 라이선스

[Apache License 2.0](LICENSE). Copyright 2026 Yong-eun Cho.
