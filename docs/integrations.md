# 외부 연동과 오픈소스 자원 (어댑터)

growwise가 자료를 생성할 때 참고할 수 있는 **오픈 API·오픈소스·오픈 콘텐츠**를 정리한다.
모든 외부 접근은 [architecture.md](architecture.md)의 **External API Adapters**
(`src/growwise/adapters/`) 계층으로만 이뤄지며, 두 원칙을 지킨다.

1. **경계 통제** — 외부로 나가는 요청에 아이 식별 정보를 포함하지 않는다.
2. **로컬 우선** — 인터넷 없이도 기본 생성·기록·조회가 되도록, 외부 API는 보조로 둔다.
   ([privacy-and-safety.md](privacy-and-safety.md))

> **읽는 법.** 현재 목표는 *개인이 운영하는 홈스쿨링용 데스크탑 앱*이다. 이 범위에서는
> 아래 대부분이 라이선스 문제 없이 쓸 수 있다. **라이선스·상업 재사용 표시(⚠️)는
> 주로 나중에 기관/상용으로 확장할 때를 위한 경고**다. ⭐ = 이 프로젝트 1순위 추천.
>
> 모든 항목은 리서치 시점(2026-09)에 실재·라이선스를 확인한 것이다. 도입 전 각 소스의
> 약관·요금·안정성을 다시 확인한다(특히 지도·도서·이미지·모델 가중치).

---

## 1. 콘텐츠 데이터 소스 (외부 API·데이터)

### 1.1 도서 · 문해력

| 자원 | URL | 유형 | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- | --- |
| ⭐ 도서관 정보나루 | data4library.kr | 오픈API(키) | 이용약관 | 연령·주제별 추천도서, 인기·급상승 대출도서(ISBN) 큐레이션. **1일 500건 초과 시 정책→캐싱** |
| ⭐ 국립중앙도서관 서지/ISBN | data.go.kr(3078982), nl.go.kr/seoji | 오픈API(키) | 제한 없음(무료) | ISBN→서명·저자·판·가격·키워드. 교재 메타데이터 자동 채움 |
| Google Books API | developers.google.com/books | API(키) | 약관 | 표지·서지·분류(영어 포함) |
| Open Library | openlibrary.org/developers | API+덤프 | 데이터 CC0 / **⚠️ 라이브 API는 비상업** | 서지·표지. 상용은 월간 덤프(CC0) 사용 |
| Gutendex + Project Gutenberg | gutendex.com, gutenberg.org | API+콘텐츠 | 본문 퍼블릭도메인 | 영어 고전 원서(아동용은 적음). "Gutenberg" 상표 제거 시 자유 |

**오픈 아동도서 (재사용 가능성 = 핵심)**

| 자원 | 라이선스 | 한국어 | 비고 |
| --- | --- | --- | --- |
| ⭐ Pratham StoryWeaver (storyweaver.org.in) | **CC BY 4.0(전부)** | ✅ 포함 | 5.3만+ 그림책, 읽기 수준별. **번역·개작·상업 재배포 가능(귀속만)** — 아동 콘텐츠 1순위 |
| Global Digital Library (digitallibrary.io) | 책별 CC BY 또는 **⚠️ CC BY-NC** | 일부 | 레벨별 초기 리더. 책별 라이선스 확인 |
| Standard Ebooks | 퍼블릭도메인(자유) | ❌ 영어 | 고학년 영어 원서(성인 고전 위주) |
| Unite for Literacy | **⚠️ 전 저작권(재배포 금지)** | ✅ 내레이션 | 무료지만 오픈 아님 → **링크만, 임베드·재호스팅 불가** |

### 1.2 사전 · 어휘 · 문법

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ 한국어기초사전 KRDict | krdict.korean.go.kr | 국립국어원(무료, 상업조건 확인) | **학습자·아동용 쉬운 뜻풀이+예문+다국어 대역**. 국어 콘텐츠 1순위 |
| 우리말샘 | opendict.korean.go.kr | **CC BY-SA 2.0 KR**(귀속+상속) | 대규모 개방형 국어사전 |
| 표준국어대사전 | stdict.korean.go.kr | 무료(상업조건 확인) | 규범 표준 정의 |
| ⭐ Free Dictionary API | dictionaryapi.dev | 데이터 **CC BY-SA**(귀속+상속) | 영어 정의·IPA·발음 오디오. 비공식→캐싱 |
| WordNet | wordnet.princeton.edu | **BSD류(상업 자유)** | 영어 동의어·상하위 의미망 |
| CMU Pronouncing Dictionary | github.com/cmusphinx/cmudict | **BSD(자유)** | 영어 발음(음소)·**파닉스/라임** |
| Datamuse | datamuse.com/api | 비상업 무료 / **⚠️ 상업=유료계약** | 유의어·운율·연상어(어휘 게임) |
| LanguageTool | github.com/languagetool-org | LGPL(자체호스팅) | 문법·문체 교정(영어·유럽어 강, ⚠️ 한국어 약함) |
| spaCy | spacy.io | **MIT** | 한/영 NLP(토큰·품사). 한국어 파이프라인 있음 |
| KoNLPy | konlpy.org | **⚠️ GPLv3**(배포 트리거) | 한국어 형태소 분석. 빈칸·문제 생성 |
| hunspell-dict-ko | github.com/spellcheck-ko/hunspell-dict-ko | 오픈(자체호스팅) | 한국어 맞춤법. **py-hanspell(네이버 스크래핑)은 회피** |
| Tatoeba | tatoeba.org | **CC BY**(귀속) | 다국어 예문·한영 대역 |

### 1.3 탐방 · 지리 · 역사 (Tour Activity Generator)

Claude Tour Skill을 원형으로 한 탐방 활동 생성의 외부 소스다([references.md](references.md)).

| 용도 | 소스 / API | 라이선스 / 비고 |
| --- | --- | --- |
| 장소 지오코딩 | Nominatim (OSM) | 이용정책·rate limit 준수 |
| 주변 공공시설 | Overpass API (OSM) | 예: 학교 반경 2km 도서관·주민센터 |
| 지형(등고선·고도) | OpenTopoData (SRTM90m, ETOPO1) | 등고선·3D·단면 |
| 지도 렌더링 | Leaflet / OpenLayers | 2D |
| 3D 시각화 | Three.js | 지형 3D |
| ⭐ 백과 사실 | Wikidata | **CC0(완전 자유)** — 행성 지름·동물 분류 등 사실 텍스트 |
| 사건·인물 | Wikipedia / Wikimedia Commons | Commons는 **파일별 라이선스 파싱 필수** |
| 국가유산(문화재) | 국가유산청 국가유산정보 API | 응답 XML, 출처표시 권장 |
| 유물·미술 | e뮤지엄(국립중앙박물관) | 무료, 이미지 저작권 필드 확인 |

**생성 흐름**: `역사 사건/장소 → 관련 장소 수집 → 관찰 포인트 → 탐구 질문 → 활동지`.
장소 정보 제공에서 끝내지 말고 아이가 질문을 만들고 관찰을 기록하며 AI 설명을 현장에서
검증하게 한다([pedagogy.md](pedagogy.md)).

### 1.4 과학 · 자연

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ NASA Open APIs | api.nasa.gov | 대체로 공공영역(로고 제외) | 오늘의 천체사진(APOD)·화성·지구 실사진 |
| ⭐ Wikidata | query.wikidata.org | **CC0** | 과학 사실 텍스트 자동생성(정확도 검증 병행) |
| ⭐ PhET Simulations | phet.colorado.edu | 시뮬 **CC BY 4.0**(오프라인 앱 有) | 물리·화학 체험 시뮬(저학년+) |
| iNaturalist API | api.inaturalist.org | **⚠️ 사진 대개 CC BY-NC**(CC0/BY만 필터) | 산책 중 곤충·식물 종 식별, 관찰 |
| GBIF API | gbif.org | 데이터셋별 CC0/BY/⚠️BY-NC | 종 분포·분류 |
| Pl@ntNet API | my.plantnet.org | 무료 일 500(출처표기) | 식물 식별 |
| eBird API | ebird.org | **⚠️ 상업 조건 확인** | 지역 조류 |
| Wikimedia Commons | commons.wikimedia.org | 파일별 상이(파싱 필수) | 과학 삽화 |
| KMA 기상청 | data.go.kr(15084084) | 공공(KOGL 확인) | 한국 날씨·계절(승인 ~1일, 격자좌표 변환) |
| 국립생물자원관 KBR | kbr.go.kr | ⚠️ 이미지 재사용 불명 | 한국 자생생물 이름·생태(텍스트 위주) |

### 1.5 수학

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ SymPy | github.com/sympy/sympy | **BSD(자유)** | 문제 자동 생성 + **정답 검증**. 완전 오프라인 |
| ⭐ Manim Community | github.com/ManimCommunity/manim | **MIT** | 개념 애니메이션 영상(세기·도형 변형). LaTeX/FFmpeg 의존 |
| Illustrative Mathematics **1판** | illustrativemathematics.org | **CC BY 4.0**(1판만! 2판=⚠️NC) | 초등 수학 문제·과제 텍스트 리믹스(미국 CCSS→한국 매핑) |
| GeoGebra | geogebra.org | 무료 임베드 / **⚠️ 상업=계약** | 그래프·도형 위젯 임베드 |
| Desmos API | desmos.com/api | 키 필요(상업 조건 확인) | 계산기·그래프 임베드 |
| mathsteps | github.com/google/mathsteps | Apache-2.0 / ⚠️ 2024 아카이브 | 단계별 풀이 전개 |

> 회피: Khan Academy(⚠️ 비상업+각색 제한 정황), OpenStax(대학 수준, 유아용 없음).

과목별 기준·구현 아이디어는 [curriculum-sources.md](curriculum-sources.md), 교육과정
성취기준 원문은 **NCIC(ncic.re.kr)** — 단 data.go.kr 배포본은 **⚠️ 공공저작물 제2유형
(상업 이용 금지)**이라 원문 재배포에 주의.

---

## 2. 로컬 처리 스택 (온디바이스 · 프라이버시)

아이의 음성·손글씨는 **로컬에서만** 처리한다. 클라우드 STT/TTS/발음평가
(ReturnZero·ETRI·CLOVA·Kakao·SpeechAce·Azure)는 아동 음성을 외부로 보내므로
로컬 우선 원칙과 충돌 → **사용하지 않는다.** (ETRI 오픈API 포털은 2025-06 종료)

### 2.1 STT (받아쓰기)

| 자원 | 라이선스 | 비고 |
| --- | --- | --- |
| ⭐ whisper.cpp | **MIT** | Mac Metal/Core ML·ANE 최적, 오프라인. GPU 없는 Mac 1순위 |
| faster-whisper | **MIT** | CPU INT8 빠름(Mac은 CPU) |
| mlx-whisper | **MIT** | Apple Silicon 네이티브(Python 선호 시) |
| 한국어 파인튠 Whisper (ghost613/whisper-large-v3-turbo-korean 등) | 대개 MIT(카드별 확인) | KO 정확도↑, whisper.cpp로 변환해 구동 |
| kresnik/wav2vec2-xlsr-korean | Apache-2.0 | 성인 낭독 기준 우수(아동엔 저하) |

> **아동 음성 주의**: 공개 한국어 STT 수치는 전부 성인 코퍼스 기준. 아동 음성(높은
> 피치·불명확)은 오차 상승 → 큰 Whisper 모델 + "확인/재발화" UX 권장.

### 2.2 TTS (음성 합성)

| 자원 | 라이선스 | 한/영 | 비고 |
| --- | --- | --- | --- |
| ⭐ MeloTTS | **MIT(상업 자유)** | 한+영 전용 모델 | **CPU 실시간·음성복제 없음** — 한국어 커버 유일 안전 선택 |
| Kokoro-82M | Apache-2.0 | 영어만 | 경량 대비 최상 영어(한국어 없음) |
| Piper (ko_KR/kss) | 엔진 GPL / **⚠️ 한국어 보이스=비상업(KSS)** | 초경량 | 가정·비영리엔 OK, 상용 한국어 불가 |

> **윤리(중요)**: **아동 음성 복제 금지.** XTTS-v2·OpenVoice 같은 클로닝 도구는 아동에
> 적용하지 않는다(동의 불가·생체정보·악용 위험). 사전 제작 합성 보이스만 사용.

### 2.3 발음 평가 (영어)

- 로컬: **Kaldi GOP**(gop_speechocean762, Apache-2.0) 또는 wav2vec2-GOP. 무겁지만 로컬 가능.
- 클라우드(SpeechAce/Azure/ETRI)는 아동 음성 유출 → 회피.

### 2.4 OCR (손글씨·인쇄 워크시트)

| 자원 | 라이선스 | 비고 |
| --- | --- | --- |
| ⭐ Apple Vision (VNRecognizeTextRequest) | Apple OS | **Mac 온디바이스·무료**, 인쇄 한/영 우수. 단 Apple 전용·비 OSS |
| Tesseract | Apache-2.0 | 인쇄 한/영(kor+eng), 손글씨 부적합 |
| PaddleOCR | Apache-2.0 | 인쇄 우수, CPU 가능(GPU 권장) |
| microsoft/trocr-base-handwritten | MIT | **영어 손글씨 최강**(줄단위+검출기 필요) |

> **한국어 아동 손글씨**: 즉시 쓸 검증된 무료 로컬 솔루션이 **사실상 없음**. 필요하면
> **AI-Hub 한국어 손글씨 데이터로 TrOCR 파인튜닝**을 별도 과제로 둔다.

---

## 3. 문서 생성 · 인쇄 (Pandoc·WeasyPrint 외)

인쇄 품질 활동지 출력용. 상용/기관 확장 시 카피레프트에 유의(개인용은 무관).

| 자원 | 라이선스 | 용도 |
| --- | --- | --- |
| ⭐ Typst | **Apache-2.0** | 스크립트 가능 마크업→고품질 PDF(수식·증분컴파일). LaTeX보다 빠름 |
| ⭐ Jinja2 + Paged.js + Playwright/Puppeteer | BSD / MIT / Apache-2.0 | HTML/CSS 템플릿→페이지분할→Chromium PDF(대량생성) |
| docxtpl | LGPL | **Word 템플릿+`{{변수}}`** — 비개발자(부모)가 유지보수 |
| python-docx | MIT | .docx 저수준 생성(docxtpl 하위엔진) |
| ReportLab(오픈판) | BSD(오픈판만) | 코드로 정밀 PDF. RML 템플릿은 유료판 전용 |
| Gotenberg | MIT | 도커화 문서→PDF API(대량·다형식, 개인엔 과함) |
| math-worksheet-generator (januschung) | GPL-2.0 | **바로 쓰는 초등 사칙연산 워크시트 PDF 생성기** |
| LaTeX / TeX Live | LPPL 등(자유) | 최고 정밀 조판(러닝커브 높음, Typst 폴백) |

> 회피: **wkhtmltopdf**(2023 아카이브), **PrinceXML**(상용·로고 강제),
> **Vivliostyle**(AGPL — SaaS 시 소스공개).

---

## 4. 인터랙티브 · 창작 · 미디어

| 자원 | 라이선스 | 용도 |
| --- | --- | --- |
| ⭐ Blockly (Google) | **Apache-2.0** | 블록 코딩 에디터 자체 구축(상업 안전) |
| H5P | 핵심 MIT(임베드 방식별 상이) | 인터랙티브 워크시트·퀴즈(50+ 타입) |
| Scratch (scratch-gui/vm) | **⚠️ AGPL-3.0 + 상표** | 학습용 자체호스팅만. 상용 SaaS 고위험·리브랜딩 필수 |
| OSMD + VexFlow | BSD / MIT | 웹 악보 표시(MusicXML) |
| abcjs | MIT | 텍스트(ABC)→악보+재생(초보 친화) |
| MuseScore | GPL-3.0 | 데스크톱 악보 제작(독립앱, 웹표시는 OSMD로 분리) |
| ⭐ Openclipart | **CC0(귀속 불요)** | 저작권 걱정 없는 클립아트. ⚠️ 가동 불안정 이력→미러링 권장 |
| Openverse API | API 오픈 | 8억+ CC/PD 이미지 검색(**작품별 라이선스 직접 확인·표기**) |
| Wikimedia Commons | 파일별 상이 | 백과 삽화(BY-SA 승계 주의) |

---

## 5. 콘텐츠 생성 · RAG 내부 스택

외부 API는 아니지만 어댑터와 함께 쓰는 후보. 상세는 [architecture.md](architecture.md).

- RAG/생성: LangChain, LlamaIndex, LangGraph, Chroma/Qdrant(로컬 임베디드)
- 저장: SQLite(로컬), Markdown 파일
- 문서 출력(PDF): 위 3절 참고
- 배포: **데스크탑 앱 패키징**(Tauri/Electron/pywebview + Python 코어). 홈서버·Docker
  는 목표가 아니다([architecture.md](architecture.md)).

---

## 6. (나중) 기관 확장용 표준 — 지금은 범위 밖

현재 목표(개인 홈스쿨링)에서는 **필요 없다.** 훗날 기관/LMS 시장에 들어갈 때만 검토할
상호운용 표준을 이름만 남겨 둔다(도입 시 [references.md](references.md) 재조사).

- **CASE / OpenSALT(MIT)** — 교육과정 성취기준을 기계판독 데이터로 매핑
- **LTI 1.3 / Advantage** — 외부 도구를 LMS(Canvas·Moodle)에 연결(기관 진입 관문)
- **QTI 3.0** — 문항·검사 이식성(벤더 종속 회피)
- **xAPI(IEEE 9274) + Ralph LRS(MIT)** — 여러 도구에 걸친 통합 학습이력
- **SCORM / Common Cartridge** — 레거시 LMS 호환·코스 패키징

---

## 7. 어댑터 설계 원칙

- 각 외부 소스는 `adapters/` 안의 독립 모듈로 감싸 교체·비활성화가 쉽게 한다.
- **네트워크 실패 시에도 코어 기능(로컬 생성·기록)은 동작**해야 한다(외부는 선택적 보강).
- API 키는 `.env`로 두고 저장소에 올리지 않는다([privacy-and-safety.md](privacy-and-safety.md)).
- rate limit·캐싱·저작권 표기·**라이선스 메타데이터 파싱**(이미지·오픈콘텐츠)을 어댑터
  단에서 처리한다.

## 8. 라이선스 빠른 참고

- **완전 자유(CC0/PD/BSD/MIT/Apache)**: Wikidata, NASA, Openclipart, SymPy, Manim,
  Blockly, spaCy, WordNet, CMUdict, whisper.cpp/faster-whisper/mlx-whisper, MeloTTS,
  Tesseract/PaddleOCR/TrOCR, Typst, Jinja2/Paged.js/Playwright, python-docx, OSMD/VexFlow/abcjs.
- **가능하나 귀속(+상속) 의무**: StoryWeaver·Tatoeba·Illustrative Math 1판·PhET(BY),
  우리말샘·Free Dictionary API·Wikimedia Commons(BY-SA→파생도 개방).
- **⚠️ 비상업/조건부 → 개인용은 OK, 기관/상용 확장 시 회피·재확인**: Datamuse(상업 유료),
  Open Library 라이브 API(비상업), GDL·iNaturalist 사진(BY-NC), Piper 한국어 보이스,
  GeoGebra/Desmos(상업 계약), Khan Academy, NCIC 원문(제2유형), Scratch·Vivliostyle(AGPL).
