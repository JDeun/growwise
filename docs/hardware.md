# 하드웨어 요구 사항

GrowWise는 로컬 우선 데스크탑 앱(Tauri + Python Core sidecar)이다. 현재 구현에서 요구 사양을
가르는 가장 큰 변수는 **선택적 로컬 LLM/embedding을 사용하느냐**다. 기록·검색·성장 지도·활동·
Parent Review·결정적 자료 템플릿 같은 Core 기능은 AI 모델 없이도 동작한다
([architecture.md](architecture.md) 모델 공급자 추상화).

> [!IMPORTANT]
> 아래 8 GB / 16 GB 구분은 **실기기 벤치마크 전의 잠정 운영 기준**이다. 최종 최소·권장 사양은
> `scripts/benchmark_hardware.py`와 `scripts/benchmark_model.py`를 대표 Windows/macOS 기기에서
> 실행한 뒤 확정한다. 완료 기준은 [operational-validation.md](operational-validation.md)를 따른다.

## 지원 OS

- **Windows 10/11 (64-bit)** — WebView2 런타임 필요(대개 기본 설치, 없으면 최초 설치).
- **macOS 12(Monterey) 이상** — Apple Silicon 및 Intel.
- Linux는 Core/CI 검증에는 사용하지만 현재 배포 1차 목표는 아니다.

## 최소 사양 (잠정)

Core-only 기능 중심, 또는 원격/별도 모델 구성을 사용하는 경우의 출발점이다.

| 항목 | 잠정 최소 |
| --- | --- |
| CPU | 최근 4코어급 |
| RAM | **8 GB** |
| 저장 | 여유 **5 GB** 이상, SSD 권장 |
| GPU | Core-only 사용에는 불필요 |
| 네트워크 | 설치·업데이트·외부 자료/원격 모델 사용 시 필요. Core 기능은 오프라인 우선 |

이 사양에서 로컬 LLM의 사용 가능성은 모델 크기·양자화·플랫폼에 크게 좌우되므로 별도 모델
벤치마크 없이 “쾌적함”을 보장하지 않는다.

## 권장 사양 (잠정)

선택적 로컬 LLM/embedding까지 함께 사용하는 개인용 환경의 출발점이다.

| 항목 | 잠정 권장 |
| --- | --- |
| CPU | 6코어+ 최신 세대 |
| RAM | **16 GB+** |
| 저장 | **SSD 20 GB+** — 로컬 모델·인덱스·백업 여유 포함 |
| GPU/가속 | Apple Silicon 또는 지원되는 NVIDIA GPU가 있으면 로컬 추론에 유리. 필수는 아님 |
| 네트워크 | 오프라인 우선. 외부 자료·원격 모델·업데이트 사용 시 필요 |

더 큰 로컬 모델이나 여러 모델을 함께 보관하려면 32 GB+ RAM과 추가 SSD 여유가 유리하지만,
GrowWise 자체의 Core 기능 요구사항으로 간주하지 않는다.

### 로컬 모델 권장 출발점

현재 Ollama 모델 크기와 GrowWise 동시 실행 여유를 고려한 문서상 출발점은 다음과 같다.

| 메모리 | 텍스트 모델 |
| --- | --- |
| 8 GB | `qwen3.5:2b` |
| 16 GB | `qwen3.5:4b` |
| 24–32 GB | `qwen3.5:9b` |
| 48 GB | `qwen3.5:27b` |
| 64 GB+ | `qwen3.5:35b` |

이 표는 실기기 benchmark를 대체하지 않는다. 모델 파일 외에 KV cache, runtime, OS, GrowWise,
vision model이 추가 메모리를 사용한다. 설치 명령과 GPU/Apple Silicon별 가이드는
[local-ai-setup.md](local-ai-setup.md)를 따른다.

## 구성 요소별 부하

| 구성 | 상대 부하 | 현재 동작 |
| --- | --- | --- |
| Tauri/WebView 앱 셸 | 낮음 | 시스템 WebView 기반 UI |
| Markdown SoT + SQLite projection | 낮음 | 기록·검색·상태 관리의 기본 저장 경로 |
| lexical 검색 | 낮음 | 모델 없이 사용 가능 |
| optional embedding / hybrid RAG | 낮음~중간 | embedding 기능이 켜진 경우에만 추가 부하 |
| optional 로컬 LLM 자료 생성 | **높음** | 모델 크기·양자화·가속기와 provider에 좌우 |
| Core deterministic 자료 생성 | 낮음 | LLM 실패/비활성 시에도 사용 가능 |
| 인쇄/PDF | 낮음~중간 | 별도 WeasyPrint/Typst 엔진이 아니라 WebView + OS native print pipeline 사용 |
| 백업/복원 | 낮음~중간 | 데이터 양에 따라 일시적으로 디스크 I/O 증가 |

PDF 출력 전략은 [ADR 0001](adr/0001-pdf-export.md)에 고정되어 있다. GrowWise는 reviewed
WebView 렌더링과 OS print dialog를 사용하며, PDF 전용 런타임이나 CJK 폰트를 별도로 bundle하지
않는다.

## 저장 공간 계획

정확한 설치 크기는 플랫폼 package artifact와 선택한 로컬 모델에 따라 달라진다.

- 데스크탑 앱 + bundled Core: 플랫폼 package 결과로 검증
- GrowWise 기록/자료/SQLite 인덱스: 사용량에 따라 증가
- 백업 파일: 사용자 보존 개수와 데이터 양에 따라 추가 공간 필요
- optional 로컬 LLM/embedding 모델: GrowWise 앱과 별도의 모델 provider 저장 공간 사용 가능

따라서 로컬 모델을 쓰지 않는 사용자의 저장 요구량과 여러 GB 모델을 보유하는 사용자의 요구량을
같은 값으로 취급하지 않는다.

## 운영 원칙

- **Core 기능은 최소 사양에서도 모델 장애와 무관하게 동작**해야 한다.
- 로컬 LLM은 보강 기능이며, 성능이 부족하면 비활성화하거나 다른 provider 구성으로 바꿀 수 있다.
- 앱이 특정 대형 모델을 필수 다운로드한다고 가정하지 않는다. 모델 설치·provider 설정은 선택적이다.
- 최소/권장 사양을 확정할 때 RAM 수치만 보지 않고 packaged sidecar 시작, CRUD/search/material 흐름,
  UI 반응성, 모델 latency/quality를 함께 확인한다.
- 실제 측정 결과가 현재 잠정 8/16 GB 기준과 다르면 문서 수치를 측정 결과에 맞춰 갱신한다.
