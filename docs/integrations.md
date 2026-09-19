# 외부 연동과 오픈소스 자원 (어댑터)

growwise가 자료를 생성할 때 쓰는 **오픈 API·오픈소스·오픈 콘텐츠**를 정리한다. 모든
외부 접근은 [architecture.md](architecture.md)의 **External API Adapters**
(`src/growwise/adapters/`) 계층으로만 이뤄지며, 두 원칙을 지킨다.

1. **경계 통제** — 외부로 나가는 요청에 아이 식별 정보를 포함하지 않는다.
2. **로컬 우선** — 인터넷 없이도 기본 생성·기록·조회가 되도록, 외부 API는 보조로 둔다.
   ([privacy-and-safety.md](privacy-and-safety.md))

> **선정 기준 (중요).** 지금은 개인 홈스쿨링용 무료 앱이지만, 나중에 유료/기관으로
> **확장해도 걸리지 않도록** 의존성은 **상업-안전 permissive 라이선스(MIT/BSD/Apache/
> CC0/CC-BY, LGPL은 라이브러리 사용 한정)만** 채택한다. 비상업(NC)·독점·AGPL은 **처음부터
> 배제**하고, 그런 소스는 9절 "함정 → 대체" 표에 대체재와 함께 명시했다. ⭐ = 1순위.
>
> **크로스플랫폼(Windows·macOS)**: 플랫폼 전용 API에 의존하지 않는다. 크로스플랫폼
> 기본값 위에 플랫폼별 최적화를 선택적으로 얹는다.
>
> 모든 항목은 리서치 시점(2026-09)에 실재·라이선스를 확인한 것이다. 버전 고정 시
> 라이선스를 다시 확인한다(특히 모델 가중치·데이터셋).

---

## 현재 코드 연결 상태

이 문서는 **후보 자원 전체 목록**과 라이선스 검토 메모를 함께 포함한다. 문서에 항목이 있다고 해서
모두 GrowWise가 네트워크로 직접 호출하는 것은 아니다. 현재 `EducationDiscoveryService`에 실제
연결된 경로는 다음과 같다.

- **오프라인/로컬 카탈로그**: 공식 한국 교육과정, GrowWise 공식 교육 콘텐츠 링크 카탈로그
- **키 기반**: 도서관 정보나루, 국립중앙도서관 ISBN, 한국어기초사전, 기상청, 전국 박물관·미술관
- **선택적 공개 보강**: Open Library, Google Books, Wikipedia, Wikidata, Wikimedia Commons,
  NASA Image and Video Library, GBIF, 국가유산청 궁궐·문화유산
- **명시적 위치 기반**: OpenStreetMap Overpass, 전국 박물관·미술관, 기상청

그 밖의 Gutendex, Tatoeba, OpenTopoData, KBR, 로컬 NLP/수학 엔진 등은 이 문서의 **후보/확장
matrix**다. 안정적인 endpoint, 라이선스, 캐시·rate limit, 테스트가 코드로 검증되기 전에는
"연결됨"으로 표시하지 않는다. 비공식 endpoint 추정이나 HTML scraping으로 빈칸을 메우지 않는다.

모든 외부 검색 문자열은 allow-list 기반 일반 교육 주제어로 축약하며, 위치 기반 요청은 부모가 직접
좌표를 입력한 경우에만 실행한다.

## 1. 콘텐츠 데이터 소스 (외부 API·데이터)

### 1.1 도서 · 문해력

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ 도서관 정보나루 | data4library.kr | 오픈API(키), 이용약관 | 연령·주제별 추천도서, 대출 통계(ISBN). 1일 500건 초과→캐싱 |
| ⭐ 국립중앙도서관 ISBN/서지 | data.go.kr(3078982) | 제한 없음(무료) | ISBN→서지 메타데이터 자동 채움 |
| Google Books API | developers.google.com/books | 무료(약관) | 표지·서지(영어 포함) |
| Open Library | openlibrary.org/developers | **데이터 덤프 CC0** (라이브 API는 비상업→덤프 사용) | 서지·표지 |
| Gutendex + Gutenberg | gutendex.com | 본문 퍼블릭도메인 | 영어 고전(아동용은 적음) |
| ⭐ Pratham StoryWeaver | storyweaver.org.in | **CC BY 4.0(전부)** | 5.3만+ 그림책, 읽기 수준별, **한국어 포함, 번역·개작·상업 재배포 가능** |
| Global Digital Library | digitallibrary.io | CC BY 책만 채택(BY-NC 책 제외) | 레벨별 초기 리더 |
| Standard Ebooks | standardebooks.org | 퍼블릭도메인 | 고학년 영어 원서 |

### 1.2 사전 · 어휘 · NLP

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ KRDict(한국어기초사전) | krdict.korean.go.kr | **CC BY-SA 2.0 KR**(상업 OK·상속, 미디어 제외) | 학습자·아동용 쉬운 뜻풀이+예문+다국어 대역 |
| 우리말샘 | opendict.korean.go.kr | **CC BY-SA 2.0 KR**(상업 OK·상속) | 대규모 개방형 국어사전 |
| ⭐ WordNet(Princeton) | wordnet.princeton.edu | **BSD류(상업 자유)** | 영어 동의어·의미관계(로컬) |
| ⭐ CMU Pronouncing Dictionary | github.com/cmusphinx/cmudict | 허용적(상업 자유) | 영어 발음→**파닉스·운율 로컬 계산** |
| wordfreq | github.com/rspeer/wordfreq | 코드 Apache-2.0 / 데이터 CC BY-SA | 단어 빈도(난이도 등급). 데이터는 2021 스냅샷 |
| ⭐ kiwipiepy / Kiwi | github.com/bab2min/kiwipiepy | LGPL(현재)→**Apache-2.0(v0.24.0~)** | 한국어 형태소 분석(순수 C++/파이썬) |
| spaCy | spacy.io | **MIT** | 한/영 NLP(토큰·품사) |
| soynlp / KR-WordRank | github.com/lovit/soynlp | LGPL-3.0 | 비지도 한국어 단어·키워드 추출 |
| LanguageTool | github.com/languagetool-org | LGPL(자체호스팅) | 영어 문법·문체 교정(한국어는 약함) |
| hunspell-dict-ko | github.com/spellcheck-ko/hunspell-dict-ko | 오픈(자체호스팅) | 한국어 맞춤법 |
| Tatoeba | tatoeba.org | **CC BY**(귀속) | 다국어 예문·한영 대역 |

> 영어 어휘 도구는 **호스티드 word-API(Datamuse 등)를 쓰지 않고** WordNet+CMUdict+
> wordfreq를 **로컬 번들**해 자립화한다(운율은 CMUdict 음소로 직접 계산). 이유는 9·10절.

### 1.3 탐방 · 지리 · 역사 (Tour Activity Generator)

Claude Tour Skill을 원형으로 한 탐방 활동 생성([references.md](references.md)).

| 용도 | 소스 / API | 라이선스 / 비고 |
| --- | --- | --- |
| 장소 지오코딩 | Nominatim (OSM) | 이용정책·rate limit 준수 |
| 주변 공공시설 | Overpass API (OSM) | 예: 학교 반경 2km 도서관·주민센터 |
| 지형(등고선·고도) | OpenTopoData (SRTM90m, ETOPO1) | 등고선·3D·단면 |
| 지도 / 3D | Leaflet · Three.js | 렌더링 |
| ⭐ 백과 사실 | Wikidata | **CC0(완전 자유)** — 사실 텍스트 |
| 사건·이미지 | Wikipedia / Wikimedia Commons | Commons는 **파일별 라이선스 파싱 필수** |
| 국가유산 | 국가유산청 국가유산정보 API | XML, 출처표시 권장 |
| 유물·미술 | e뮤지엄(국립중앙박물관) | 무료, 이미지 저작권 필드 확인 |

**생성 흐름**: `역사 사건/장소 → 관련 장소 → 관찰 포인트 → 탐구 질문 → 활동지`. 장소
정보 제공에서 끝내지 말고 아이가 질문·관찰·검증을 하게 한다([pedagogy.md](pedagogy.md)).

### 1.4 과학 · 자연

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ NASA Open APIs | api.nasa.gov | 대체로 공공영역(로고 제외) | 천체사진(APOD)·화성·지구 실사진 |
| ⭐ Wikidata | query.wikidata.org | **CC0** | 과학 사실 텍스트(정확도 검증 병행) |
| ⭐ PhET Simulations | phet.colorado.edu | 시뮬 **CC BY 4.0**(오프라인 앱 有) | 물리·화학 체험 시뮬(저학년+) |
| ⭐ BioCLIP (종 식별 모델) | huggingface.co/imageomics/bioclip | 모델 **MIT**(학습데이터 별도) | **오프라인 제로샷 종 분류**(Pl@ntNet API 대체) |
| 이미지(자연·생물) | Wikimedia Commons | 파일별 CC0/CC BY 필터 | 종·자연 삽화(파일별 검증) |
| 종 분포·기록 | GBIF API | 레코드 CC0/CC BY 필터(이미지는 재검증) | 종 분포·분류 |
| KMA 기상청 | data.go.kr(15084084) | 공공(KOGL 확인) | 한국 날씨·계절 |
| 국립생물자원관 KBR | kbr.go.kr | 텍스트 위주(이미지 재사용 불명) | 한국 자생생물 이름·생태 |

### 1.5 수학

| 자원 | URL | 라이선스 / 재사용 | 용도 |
| --- | --- | --- | --- |
| ⭐ SymPy | github.com/sympy/sympy | **BSD** | 문제 자동 생성 + **정답 검증**(완전 오프라인) |
| ⭐ Manim (Community) | github.com/ManimCommunity/manim | **MIT** | **3Blue1Brown가 쓰는 수학 애니메이션 엔진**. 개념 영상(세기·도형 변형·시각화). 원본 `3b1b/manim`(MIT)의 유지보수판. LaTeX/FFmpeg 의존 |
| ⭐ JSXGraph | github.com/jsxgraph/jsxgraph | **LGPL-3.0 OR MIT**(MIT 갈래 선택) | 인터랙티브 기하·함수 플롯·차트(**GeoGebra/Desmos 대체**, 외부 의존 없음) |
| mathjs | mathjs.org | **Apache-2.0** | 수식 파싱·평가·기호연산 |
| Illustrative Mathematics **1판** | illustrativemathematics.org | **CC BY 4.0**(1판만! 2판=NC) | 초등 수학 문제·과제 리믹스(미국 CCSS→한국 매핑) |

과목별 기준·구현 아이디어는 [curriculum-sources.md](curriculum-sources.md). 교육과정
성취기준은 **NCIC(ncic.re.kr)** 참고하되, 원문은 상업 이용 제한(제2유형)이라 **재배포하지
말고 성취기준 코드로 매핑 + 자체 설명**을 쓴다.

---

## 2. 로컬 처리 스택 (크로스플랫폼 · 프라이버시)

아이의 음성·손글씨는 **로컬에서만** 처리한다. 클라우드 STT/TTS/발음평가(CLOVA·ETRI·
SpeechAce·Azure 등)는 아동 음성을 외부로 보내므로 **쓰지 않는다.** 모든 항목은
Windows·macOS 공통 동작을 기준으로 고른다.

### 2.1 STT (받아쓰기)

| 자원 | 라이선스 | 크로스플랫폼 | 비고 |
| --- | --- | --- | --- |
| ⭐ whisper.cpp | **MIT** | Win/macOS/Linux | 플랫폼별 가속 자동(Metal/CUDA/Vulkan/CPU). 오프라인 |
| faster-whisper | **MIT** | Win/macOS/Linux | CPU INT8 빠름 |
| 한국어 파인튠 Whisper (예: whisper-large-v3-turbo-korean) | 대개 MIT(카드별) | 변환 후 위 런타임 | KO 정확도↑ |

> **아동 음성 주의**: 공개 KO STT 수치는 성인 코퍼스 기준 → 아동은 오차 상승. 큰 Whisper
> 모델 + "확인/재발화" UX 권장.

### 2.2 TTS (음성 합성)

| 자원 | 라이선스 | 한/영 | 비고 |
| --- | --- | --- | --- |
| ⭐ MeloTTS | **MIT(상업 자유)** | 한+영 전용 모델 | CPU 실시간·**음성복제 없음**. 크로스플랫폼(Python) |
| Kokoro-82M | Apache-2.0 | 영어 | 경량 대비 최상 영어 |

> **윤리(중요)**: **아동 음성 복제 금지.** 클로닝 도구(XTTS·OpenVoice 등)는 아동에 적용
> 하지 않는다. 사전 제작 합성 보이스만 사용. (Piper 한국어 보이스는 비상업이라 배제)

### 2.3 발음 평가 (영어)

- 로컬: **Kaldi GOP**(gop_speechocean762, Apache-2.0) 또는 wav2vec2-GOP. 클라우드 회피.

### 2.4 OCR (손글씨 · 인쇄 워크시트)

| 자원 | 라이선스 | 크로스플랫폼 | 비고 |
| --- | --- | --- | --- |
| ⭐ Tesseract | Apache-2.0 | Win/macOS/Linux | 인쇄 한/영(kor+eng). **크로스플랫폼 기본** |
| ⭐ PaddleOCR | Apache-2.0 | Win/macOS/Linux | 인쇄 우수, CPU 가능 |
| microsoft/trocr-base-handwritten | MIT | 파이썬 | **영어 손글씨**(줄단위+검출기) |
| (보너스) Apple Vision | Apple OS | macOS만 | Mac에서 온디바이스 최적화로 선택 적용 |
| (보너스) Windows.Media.Ocr | Windows OS | Windows만 | Windows 내장 OCR로 선택 적용 |

> **플랫폼 전용(Apple Vision / Windows OCR)은 "있으면 더 좋은" 최적화**로만 쓰고,
> 기본 동작은 Tesseract/PaddleOCR로 양 OS에서 동일하게 보장한다.
>
> **한국어 아동 손글씨**: 즉시 쓸 검증된 무료 로컬 솔루션이 **사실상 없음** → 필요하면
> **AI-Hub 한국어 손글씨 데이터로 TrOCR 파인튜닝**을 별도 과제로 둔다.

---

## 3. 문서 생성 · 인쇄

| 자원 | 라이선스 | 용도 |
| --- | --- | --- |
| ⭐ WeasyPrint | **BSD-3-Clause** | HTML/CSS→PDF 주력(워크시트·리포트) |
| ⭐ Typst | **Apache-2.0** | 스크립트 조판→고품질 PDF(수식·증분컴파일) |
| Jinja2 + Paged.js + Playwright | BSD / MIT / Apache-2.0 | HTML 템플릿→페이지분할→PDF(대량) |
| docxtpl / python-docx | LGPL / MIT | Word 템플릿+`{{변수}}`(비개발자 유지보수) |
| ReportLab(오픈판) | BSD(오픈판만) | 코드로 정밀 PDF |
| SymPy(생성) + 위 도구 | BSD | **사칙연산 등 워크시트를 직접 생성**(GPL 생성기 대신) |

> 회피(→ 대체): wkhtmltopdf(아카이브)·PrinceXML(독점)·Vivliostyle(AGPL) → **WeasyPrint/Typst**.

---

## 4. 인터랙티브 · 창작 · 미디어

| 자원 | 라이선스 | 용도 |
| --- | --- | --- |
| ⭐ Blockly (Google) | **Apache-2.0** | 블록 코딩 **에디터** 자체 구축 |
| H5P | 핵심 MIT(임베드 방식별 확인) | 인터랙티브 워크시트·퀴즈 |
| OSMD + VexFlow | BSD / MIT | 웹 악보 표시(MusicXML) |
| abcjs | MIT | 텍스트(ABC)→악보+재생 |
| ⭐ Openclipart | **CC0** | 클립아트(귀속 불요). 가동 불안정→미러링 |
| Openverse API | API 오픈 | CC/PD 이미지 검색(작품별 라이선스 확인) |
| Wikimedia Commons | 파일별 | 백과 삽화(파일별 검증) |

> Scratch는 2025년 **AGPL로 전환**돼 배제. 블록 코딩은 **Blockly(에디터) + 자체 실행
> 런타임**으로 간다(9·10절). 악보 저작이 필요하면 MuseScore(GPL, 독립앱)는 파일 생성
> 도구로만 쓰고, 앱 내 표시는 OSMD/VexFlow로 분리한다.

---

## 5. 콘텐츠 생성 · RAG 내부 스택

- RAG/생성: LangChain, LlamaIndex, LangGraph, Chroma/Qdrant(로컬 임베디드)
- **모델 실행/공급자(교체 가능)**: 현재 코드는 Ollama와 OpenAI-compatible Chat Completions
  adapter를 제공한다. 따라서 llama.cpp/vLLM/LM Studio 같은 local 호환 endpoint와 opt-in remote
  호환 endpoint를 동일 `ModelProvider` 경계로 사용할 수 있다. 원격은 명시적 privacy opt-in을
  요구하고 API-key 사용 시 HTTPS만 허용한다. embedding endpoint는 text endpoint와 분리한다.
  Anthropic/Google 같은 vendor-specific adapter는 필요 시 추가하며 특정 SDK를 Core 필수 의존성으로
  만들지 않는다([architecture.md](architecture.md)).
- 저장: SQLite(로컬 인덱스), Markdown 파일(SoT)
- 앱 셸/패키징: **Tauri + Python 사이드카**(Win/macOS). 상세 [architecture.md](architecture.md)

---

## 6. (나중) 기관 확장용 표준 — 지금은 범위 밖

현재 목표(개인 홈스쿨링)에서는 **필요 없다.** 훗날 기관/LMS 진입 시에만 검토
(도입 시 [references.md](references.md) 재조사).

- CASE / OpenSALT(MIT) — 성취기준 매핑 · LTI 1.3 — LMS 연결 · QTI 3.0 — 문항 이식성
- xAPI(IEEE 9274) + Ralph LRS(MIT) — 학습이력 · SCORM/Common Cartridge — 레거시 호환

---

## 7. 어댑터 설계 원칙

- 각 외부 소스는 `adapters/`의 독립 모듈로 감싸 교체·비활성화가 쉽게 한다.
- **네트워크 실패 시에도 코어 기능(로컬 생성·기록)은 동작**해야 한다.
- API 키는 `.env`로 두고 저장소에 올리지 않는다([privacy-and-safety.md](privacy-and-safety.md)).
- rate limit·캐싱·저작권 표기·**라이선스 메타데이터 파싱**(이미지·오픈콘텐츠)을 어댑터
  단에서 처리한다.

---

## 8. 라이선스 방침 요약

- **자유(CC0/PD/BSD/MIT/Apache)** — 기본 채택: Wikidata, NASA, Openclipart, SymPy,
  Manim, JSXGraph(MIT), mathjs, Blockly, spaCy, WordNet, CMUdict, BioCLIP(모델),
  whisper.cpp/faster-whisper, MeloTTS/Kokoro, Tesseract/PaddleOCR/TrOCR, WeasyPrint,
  Typst, Paged.js/Playwright, python-docx, OSMD/VexFlow/abcjs.
- **귀속(+상속) 조건, 채택 가능**: StoryWeaver·Tatoeba·PhET·IM 1판(BY),
  KRDict·우리말샘·wordfreq 데이터(BY-SA → **파생 데이터도 개방·미디어 제외**),
  kiwipiepy·soynlp(LGPL, 라이브러리 사용).
- **배제(비상업/독점/AGPL)** — 9절에서 대체함: Datamuse, Open Library 라이브 API,
  iNaturalist 사진·Pl@ntNet, GeoGebra·Desmos, KoNLPy, Khan·CK-12·Eureka·CommonLit·
  IM 2판, wkhtmltopdf·PrinceXML·Vivliostyle, Scratch, Piper 한국어·XTTS, 클라우드 음성.

---

## 9. 함정 → 상업-안전 대체 (매핑)

| 쓰지 않음 (이유) | 대체 | 대체 라이선스 |
| --- | --- | --- |
| GeoGebra(비상업)/Desmos(독점) | **JSXGraph**(+mathjs) | LGPL **OR MIT** / Apache-2.0 |
| KoNLPy(GPLv3) | **kiwipiepy/Kiwi**, spaCy | LGPL→Apache-2.0 / MIT |
| Datamuse(호스티드·상업 사전문의) | **WordNet+CMUdict+wordfreq 로컬 번들**(운율 직접 계산) | BSD류 / 허용적 / Apache |
| Khan·CK-12·Eureka·CommonLit·IM 2판(NC) | **IM 1판**, **Siyavula 비브랜드판** | CC BY 4.0 |
| wkhtmltopdf(아카이브)·PrinceXML(독점)·Vivliostyle(AGPL) | **WeasyPrint + Typst** | BSD / Apache-2.0 |
| Scratch(2025 AGPL 전환) | **Blockly(에디터) + 자체 런타임** | Apache-2.0(에디터) |
| iNaturalist 사진(BY-NC)·Pl@ntNet(호스티드) | **BioCLIP(오프라인 식별)** + Wikimedia/GBIF **CC0·CC BY만** | MIT(모델) / 파일별 |
| Piper 한국어(비상업)·XTTS(NC) | **MeloTTS** | MIT |
| 클라우드 음성(CLOVA/ETRI/SpeechAce) | 로컬 whisper.cpp / MeloTTS / Kaldi GOP | MIT / MIT / Apache |

---

## 10. 정직한 공백 (좋은 허용적 대체가 없는 곳)

유료·비상업 소스로 때우지 않고, 한계를 명시하고 자체 구축 과제로 남긴다.

1. **Scratch식 실행 런타임** — 완전 허용적 대체가 **없다**(Scratch는 AGPL). Blockly는
   에디터일 뿐. → 블록 코딩은 Blockly 위에 **자체 실행 엔진**을 얹거나 초기에는 범위에서
   제외한다.
2. **완전 허용적 무료 word-API** — 없다. → WordNet+CMUdict+wordfreq(+Wiktextract)를
   **로컬 번들**해 자립화하고, 운율/발음연관은 음소로 직접 구현한다.
3. **유아~초3 CC BY 커리큘럼** — 매우 얇다(IM 1판·Siyavula뿐, 저학년 커버 약함). →
   **자체 제작 비중을 크게** 잡는다.
4. **한국어 아동 손글씨 OCR** — 검증된 무료 로컬 솔루션 없음 → AI-Hub 데이터로 TrOCR
   파인튜닝(별도 과제).
5. **CC BY-SA 상속·미디어 제외** — KRDict/우리말샘/Wiktextract/wordfreq 데이터는 상업
   가능하나 **파생 데이터도 동일 라이선스 공개** 의무 + **발음 음성·이미지 등 미디어는
   오픈 아님(재배포 금지)**. 폐쇄형 데이터와 섞지 말고 격리 설계한다.
6. **GBIF/Commons 이미지** — 레코드는 필터되나 **이미지 파일 라이선스는 파일별 재검증**
   필요("소스가 GBIF니까 안전" 금지).
