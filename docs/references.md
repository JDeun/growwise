# 참고 시스템과 선행 사례

growwise 설계의 근거가 된 외부 프로젝트·자료와, 각각에서 **무엇을 빌려오는지**를
정리한다. 모두 공개 자료이며, 실제 도입 전에는 라이선스·안정성을 개별 확인한다.

---

## 학습 시스템 설계 참고

### PAIDEIA / PAIDEIA-codex

- https://github.com/TaewoooPark/PAIDEIA · https://github.com/TaewoooPark/PAIDEIA-codex
- 학생 자신의 강의자료·과제·풀이·손글씨 답안·오답을 **plain markdown 학습 그래프**로
  축적해 개인화된 학습 루프를 만드는 Claude Code / Codex 플러그인.
- 사이클: `ingest → analyze → drill → grade → weakmap → cheatsheet`.
- 산출물은 코스 폴더 안 plain markdown(`errors/log.md`, `weakmap/*.md`,
  `cheatsheet/final.md` 등). 원칙: **HW density = exam probability**.

**growwise가 빌려오는 것**
- 공부 기록은 결과물이 아니라 **성장 그래프**여야 한다(오답·반복 실수·약점 지도).
- AI는 정답 생성기가 아니라 **회고 보조자**. 아이가 풀고, AI는 전략·실수 패턴·다음
  연습을 정리한다.
- **plain markdown 소유권** — 교육 기록이 특정 SaaS에 잠기지 않고 가족이 읽고 수정·
  보존할 수 있어야 한다.
- `ingest → practice → feedback → weakmap` 구조를 시험 대비를 넘어 독서 토론·영어
  말하기·글쓰기 피드백에도 응용한다.
- 주의: 시험 확률 최적화·자동 채점 구조는 아이가 자기 설명·회고를 충분히 배운 뒤에나
  맞다. 어린 시기 목표(호기심·언어·독서·신체/예술)와는 다르다.

### DeepTutor

- https://github.com/HKUDS/DeepTutor
- "Agent-Native Personalized Learning Assistant." 단순 Q&A가 아니라 자료 수집·지식
  베이스·문제 풀이·리서치·가이드 학습을 묶은 학습 작업공간.
- 아키텍처: **Tools + Capabilities 2계층 플러그인**
  - `Tools`(LLM이 호출하는 기능): rag, web_search, code_execution, reason,
    brainstorm, paper_search …
  - `Capabilities`(다단계 워크플로): chat, deep_solve, deep_question,
    deep_research, math_animator …
- 진입점 3종: **CLI / WebSocket API / Python SDK** — 다른 프로그램·에이전트가 조작할
  수 있는 런타임으로 설계.
- `Persistent Memory`(이력·관심사·수준·선호 축적), `TutorBot`(workspace·memory·
  persona를 각자 가진 지속형 에이전트). 안정성 위해 RAG는 `LlamaIndex only`로 단순화.

**growwise가 빌려오는 것**
- "도구를 어떻게 쓰는가(Tools)"와 "어떤 작업 흐름인가(Capabilities)"의 분리는
  growwise의 라우터/생성 모듈 경계 설계에 참고가 된다.
- 아이 교육에 적용할 때 확인할 질문: 학습 기록이 어떻게 축적되는가 / 오답·환각을
  어떻게 통제하는가 / 과목·성향별 persona를 어떻게 나누는가 / **부모 review layer를
  둘 수 있는가**.
- 기능 폭보다 **운영 안정성**이 먼저다(DeepTutor도 기능을 덜어내며 단순화했다).

### TutorMoments (AI2 / allenai)

- https://github.com/allenai/tutormoments · https://huggingface.co/blog/allenai/tutormoments
- LLM 튜터가 **언제 도와주고(scaffold) 언제 물러서서(push for rigor)** 아이가 스스로
  하게 둘지를 아는지 측정하는 replay 기반 평가. 실제 1:1 수학 튜터링 전사 462건,
  교사 27명이 표시한 핵심 결정 순간 1,500+개(de-identified 공개).
- 핵심 발견: "튜터 잘해"라고만 하면 모델은 **과도하게 도와주고** 깊은 사고를 거의
  안 밀어붙인다. 트레이드오프를 프롬프트에 명시하면 나아지지만 인간 튜터엔 못 미치고
  모델별 편차가 크다. 기본 "helpful assistant" 성향만으론 좋은 튜터가 못 된다.

**growwise가 빌려오는 것**
- "AI를 정답 기계로 쓰지 않는다"는 [pedagogy.md](pedagogy.md) 원칙의 **실증적 평가
  지표**. 생성·코치 모듈이 과도한 scaffold를 피하는지 점검하는 잣대로 쓴다.
- Parent Review Layer와 코치 프롬프트에 scaffold/rigor 트레이드오프를 명시한다.

---

## 콘텐츠·체험 학습 도구 참고

### Claude Tour Skill

- https://github.com/choimin1243/claude-tour-skill
- 역사탐방·우리동네 공공시설 탐색·지형(등고선/3D)·기후지대 탐방을 통합한 교육용
  인터랙티브 도구.
- 동작 예: 역사 사건명 → 관련 장소 5~8개 수집(WebSearch/Wikipedia) → 탐방 코스 /
  학교명 → 2km 반경 공공시설(Overpass API) / 산·해저 지형 → OpenTopoData·SRTM90m·
  ETOPO1로 등고선·3D·단면도.
- 기술 스택: Python 표준 라이브러리 HTTP 서버, Leaflet, Three.js, Nominatim,
  Overpass API, Wikimedia Commons API.

**growwise가 빌려오는 것**
- **탐방 활동 생성기(Tour Activity Generator)의 구체 설계 원형**. 흐름은
  `역사 사건 → 장소 탐방 → 관찰 포인트 → 탐구 질문 → 보고서`.
- 단, 장소 정보를 받는 데서 끝나지 않고 아이가 **질문을 만들고, 관찰을 기록하고, AI
  설명을 현장에서 검증**하게 한다([pedagogy.md](pedagogy.md) 검증력).
- 관련 외부 API는 [integrations.md](integrations.md)에 정리. 실제 사용 전 API 안정성·
  지도 저작권·이미지 라이선스·연령별 질문 난이도를 점검한다.

### MisoTTS 8B

- https://github.com/MisoLabsAI/MisoTTS
- 영어 대화형 음성 생성용 8B TTS(text-to-dialogue RVQ Transformer, Llama 3.2 스타일
  8B backbone + 300M audio decoder, Mimi tokenizer). 생성 음성에 SilentCipher
  워터마킹 기본 적용. **영어 전용**, 로컬 실행은 PyTorch/GPU 기반.

**growwise가 빌려오는 것**
- 영어 듣기·말하기 자료용 **고품질 음성 후보**이자 워터마킹 사례.
- 주의: 8B·GPU/VRAM 요구로 홈서버 상시 운용엔 무겁고, 영어 전용·라이선스
  (NOASSERTION) 불명확. 한국어·가족 음성엔 부적합. 음성 후보 비교는
  [integrations.md](integrations.md) 참고. 아이 음성 데이터는 외부 전송을 기본값으로
  삼지 않는다.

---

## 교육 철학 자료

- **「장송의 프리렌으로 배우는 AI 시대 공부법」** — AI 시대 공부를 질문력·연결력·
  검증력·맥락력·목적력으로 재정의. [pedagogy.md](pedagogy.md)의 뼈대.
- **노르웨이 초등 생성형 AI 제한 권고** — 문해·수리·비판적 사고가 자리 잡기 전 AI
  직접 사용을 늦추는 정책 근거([pedagogy.md](pedagogy.md) 단계적 노출 원칙).
- **깊이 읽기(deeper reading) 프롬프트** — AI를 빠른 요약기가 아니라 깊이 읽기·비판적
  재독의 파트너로 쓰는 관점.
- **인격 교육 자료** — 사람을 귀하게 보는 태도와 목적력이라는 인격 교육 축.
