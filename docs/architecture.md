# 아키텍처 (초안)

> **형태: 크로스플랫폼 데스크탑 앱 (Tauri, 개인용 우선).** 홈서버·Docker·상시 백엔드
> 배포는 목표가 아니다. **Windows·macOS**에 설치해 오프라인 우선으로 동작하는 개인
> 홈스쿨링 앱이 1차 목표다. UI 셸은 **Tauri**로 확정. 기관용 확장은 나중 단계로 미뤄
> 둔다([roadmap.md](roadmap.md)).

## 파이프라인

```
Desktop UI
    ->  App Core (로컬, 인프로세스 또는 로컬 사이드카)
        ->  Request Router
            ->  Generator Modules
                ->  Local RAG
                    ->  Markdown / SQLite Storage (로컬)
                        ->  PDF Export
                            ->  External API Adapters (선택적, 오프라인 시 우회)
```

입력 유형을 라우터가 분류해 적절한 생성 모듈로 보내고, 생성 모듈은 로컬 RAG로
근거 자료를 참고해 결과를 만든다. 결과와 학습 로그는 **데스크탑 로컬 저장소**에 남고,
필요 시 PDF로 출력된다. 외부 자료(도서 메타데이터, 지도 등)는 어댑터를 통해서만
접근하며, 외부 연결이 없어도 기본 생성·기록·조회는 동작한다.

## 모듈

| 모듈 | 책임 | 소스 경로 |
| --- | --- | --- |
| App Core | 데스크탑 UI ↔ 코어 연결(로컬 인프로세스 또는 로컬 API), 세션 | `src/growwise/api/` |
| Request Router | 입력 유형 분류 → 생성 모듈 라우팅 | `src/growwise/router/` |
| Reading Material Generator | 독서 활동지 생성 | `src/growwise/generators/` |
| English Card Generator | 영어 대화 카드 생성 | `src/growwise/generators/` |
| Tour Activity Generator | 탐방/여행 활동지 생성 | `src/growwise/generators/` |
| Math Play Generator | 수학 놀이 활동 생성 | `src/growwise/generators/` |
| Science Activity Generator | 과학 탐구 활동 생성 | `src/growwise/generators/` |
| Learning Log Writer | 학습 로그 기록 | `src/growwise/storage/` |
| Parent Review Layer | 노출 전 검토(난이도·민감성·PII) | `src/growwise/review/` |
| Local RAG | 로컬 근거 자료 검색 | `src/growwise/rag/` |
| Storage | Markdown/SQLite 저장·조회 | `src/growwise/storage/` |
| PDF Export | 인쇄 품질 문서 출력 | `src/growwise/export/` |
| External API Adapters | 외부 자료 접근(경계 통제) | `src/growwise/adapters/` |

## 설계 원칙

- **단순한 라우터 먼저**: 초기에는 복잡한 멀티에이전트보다 입력 유형을 보고 독서·영어·
  탐방·수학·과학·로그 모듈로 보내는 단순 라우터가 적합하다.
- **로컬 우선**: 기본 자료 생성·기록 조회는 오프라인에서 동작한다. 외부 API는 어댑터
  계층으로 격리해 경계를 통제한다([privacy-and-safety.md](privacy-and-safety.md)).
- **검토 계층 분리**: 생성과 노출 사이에 Parent Review Layer를 반드시 둔다.

## 기술 스택 후보

아직 확정 전이며, 후보를 적어 둔다. 첫 마일스톤에서 하나로 고정한다
([roadmap.md](roadmap.md) 미해결 질문 참고). 외부 API·데이터 소스의 구체 목록과
어댑터 설계는 [integrations.md](integrations.md), 설계 근거가 된 선행 사례는
[references.md](references.md)를 참고한다.

### 콘텐츠 생성과 RAG

- LangChain / LlamaIndex / LangGraph
- 벡터 저장소: Chroma / Qdrant (로컬 임베디드 모드)
- 데이터: SQLite(로컬), Markdown 파일 저장

> 초기에는 복잡한 멀티에이전트보다 단순한 라우터가 적합하다.

### 문서 출력

- Pandoc / WeasyPrint / Playwright PDF
- Markdown → PDF 파이프라인, Obsidian export

> 활동지는 부모·교사가 바로 인쇄할 수 있어야 하므로 PDF 출력 품질이 중요하다.

### 지도와 탐방

- Leaflet / OpenLayers / Three.js
- OpenStreetMap / Overpass API / OpenTopoData

> 실제 서비스에서는 API 안정성, 지도 저작권, 외부 이미지 라이선스를 별도 점검한다.

### 음성

- STT: Whisper 계열
- TTS: Piper / Coqui TTS / MisoTTS

> 아이 음성 데이터는 외부 전송을 기본값으로 삼지 않는다.

### 데스크탑 앱 (Tauri, 크로스플랫폼)

목표는 홈서버가 아니라 **Windows·macOS에서 동작하는 데스크탑 앱**이다. UI 셸은
**Tauri**(Rust 코어 + 시스템 웹뷰: Windows=WebView2, macOS=WKWebView)로 확정.
설치물이 작고 크로스플랫폼이라 목표에 맞는다. 생성·RAG·PDF·음성 등 핵심 처리는 Python
이므로, **Tauri가 Python 백엔드를 사이드카(번들 바이너리)로 실행**하고 로컬(127.0.0.1)로
통신하는 구조를 기본으로 한다.

- **UI 셸**: Tauri (Rust + 시스템 웹뷰). 프론트는 웹기술(HTML/CSS/JS)
- **코어**: 로컬 Python — 라우터·생성 모듈·RAG·PDF·음성. Tauri sidecar로 번들(PyInstaller 등)
- **데이터**: SQLite + 로컬 파일(Markdown). 서버 DB 불요
- **로컬 모델**: 임베딩·STT/TTS는 가능한 CPU 실행, 플랫폼별 가속(Metal/CUDA/CPU) 자동
  선택. 자원은 앱에 번들하거나 최초 실행 시 내려받기
- **패키징**: Tauri 번들러(Win: MSI/NSIS, macOS: .app/.dmg) + Python 사이드카(PyInstaller)

**크로스플랫폼 원칙**: Windows·macOS 양쪽을 **CI에서 함께 빌드·검증**한다. 경로 구분자·
웹뷰(WebView2/WKWebView)·번들 차이를 초기부터 고려하고, **플랫폼 전용 API(예: macOS
Apple Vision OCR)에 의존하지 않는다** — 크로스플랫폼 기본값(예: Tesseract/PaddleOCR)
위에 플랫폼별 최적화를 선택적으로 얹는다([integrations.md](integrations.md)).

> 인터넷 없이도 기본 생성·기록·조회가 가능해야 한다(오프라인 우선).
