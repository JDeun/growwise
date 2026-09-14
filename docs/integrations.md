# 외부 연동과 API (어댑터)

growwise가 자료를 생성할 때 참고할 수 있는 외부 API·데이터 소스를 정리한다. 모든
외부 접근은 [architecture.md](architecture.md)의 **External API Adapters**
(`src/growwise/adapters/`) 계층으로만 이뤄지며, 다음 두 원칙을 지킨다.

1. **경계 통제** — 외부로 나가는 요청에 아이 식별 정보를 포함하지 않는다.
2. **로컬 우선** — 인터넷 없이도 기본 자료 생성·기록 조회가 되도록, 외부 API는
   보조로 둔다. ([privacy-and-safety.md](privacy-and-safety.md))

> 아래 API·데이터는 후보다. 실제 연동 전 각 소스의 **이용 약관·라이선스·요금·안정성**을
> 개별 확인한다. 특히 지도·도서 메타데이터·이미지가 그렇다.

---

## 탐방·지리·역사 (Tour Activity Generator)

Claude Tour Skill을 원형으로 한 탐방 활동 생성의 외부 소스다
([references.md](references.md)).

| 용도 | 소스 / API | 비고 |
| --- | --- | --- |
| 장소 지오코딩 | Nominatim (OpenStreetMap) | 이용 정책·rate limit 준수 |
| 주변 공공시설 검색 | Overpass API (OpenStreetMap) | 예: 학교 반경 2km 주민센터·도서관·소방서 |
| 지형(등고선·고도) | OpenTopoData (SRTM90m, ETOPO1) | 등고선·3D·단면도 |
| 지도 렌더링 | Leaflet / OpenLayers | 2D 지도 |
| 3D 시각화 | Three.js | 지형 3D |
| 백과·사건 정보 | Wikipedia / Wikidata | 역사 사건 → 장소 연결 |
| 이미지 | Wikimedia Commons | **이미지 라이선스 개별 확인 필수** |

**생성 흐름**: `역사 사건/장소 입력 → 관련 장소 수집 → 관찰 포인트 → 탐구 질문 →
활동지/보고서`. 장소 정보 제공에서 끝내지 말고, 아이가 질문을 만들고 관찰을 기록하며
현장에서 AI 설명을 검증하도록 구성한다([pedagogy.md](pedagogy.md)).

## 도서·문해력 (Reading / English Generator)

| 용도 | 소스 / API | 비고 |
| --- | --- | --- |
| 도서 메타데이터 | Google Books API | 표지·서지·분류 |
| 공개 도서 | Open Library API | 서지·판본 |
| 추천도서·독서 | 공공도서관 추천목록, 독서교육종합지원시스템 | 국내 자료 |
| 영어 기준 | CEFR, Cambridge English 공개자료, Oxford Owl | 단계·리더스 |

## 음성 (English 듣기·말하기)

| 용도 | 후보 | 비고 |
| --- | --- | --- |
| STT(받아쓰기) | Whisper 계열 | 로컬 실행 가능 |
| TTS(음성 합성) | Piper, Coqui TTS | 로컬·경량 우선 |
| TTS(고품질 영어) | MisoTTS 8B | 영어 전용·GPU 무거움·라이선스 불명확([references.md](references.md)) |

> **아이 음성 데이터는 외부 전송을 기본값으로 삼지 않는다.** 로컬 STT/TTS를 우선하고,
> 합성 음성 사용 시 워터마킹·동의·윤리 정책을 별도 검토한다.

## 과목별 공개 교육 자료

- 수학: 국내 초등 수학 교육과정, Khan Academy Kids, CK-12, OpenStax
- 과학: NASA Kids' Club, NOAA, National Geographic Kids, 국내 과학관·박물관 공개자료
- 사회·역사: 문화재청 공개자료, 박물관·미술관 교육자료, OpenStreetMap/Wikidata
- 국어: 누리과정, 초등 국어 교육과정, 국립국어원 공개자료
- 기관용: 누리과정 해설서, 교육부·보육과정 공개자료

자세한 과목별 기준·구현 아이디어는 [curriculum-sources.md](curriculum-sources.md) 참고.

## 콘텐츠 생성·RAG·출력 (내부 기술 스택)

외부 API는 아니지만 어댑터와 함께 쓰는 후보 스택. 상세는
[architecture.md](architecture.md).

- RAG/생성: LangChain, LlamaIndex, LangGraph, Chroma/Qdrant
- 저장: SQLite(로컬), Markdown 파일
- 문서 출력(PDF): Pandoc, WeasyPrint, Playwright — 인쇄 품질이 중요
- 배포: **데스크탑 앱 패키징**(Tauri/Electron/pywebview + Python 코어), 로컬 임베딩 모델.
  홈서버·Docker는 목표가 아니다([architecture.md](architecture.md) 데스크탑 앱 패키징)

## 어댑터 설계 원칙

- 각 외부 소스는 `adapters/` 안의 독립 모듈로 감싸, 교체·비활성화가 쉽게 한다.
- 네트워크 실패 시에도 코어 기능(로컬 생성·기록)은 동작해야 한다(외부는 선택적 보강).
- API 키는 `.env`로 두고 저장소에 올리지 않는다([privacy-and-safety.md](privacy-and-safety.md)).
- rate limit·캐싱·저작권 표기를 어댑터 단에서 처리한다.
