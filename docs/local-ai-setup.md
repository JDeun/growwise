# GrowWise 로컬 AI 설정 가이드

GrowWise는 AI 없이도 사용할 수 있습니다. 로컬 AI는 기록 검색, 자료 생성, 사진 이해 등을 **보강하는 선택 기능**입니다.

가장 간단한 로컬 실행 방법은 [Ollama](https://ollama.com/)입니다. GrowWise는 기본적으로 `http://127.0.0.1:11434`의 Ollama를 찾습니다.

> 이 문서의 모델 크기와 권장은 **2026년 9월 기준**입니다. 모델 생태계와 Ollama 최적화는 빠르게 바뀌므로 실제 속도는 CPU/GPU, 메모리 대역폭, 컨텍스트 길이에 따라 달라집니다.

---

## 일반 사용자: 가장 쉬운 설정

명령줄에서 모델 이름을 직접 입력할 필요는 없습니다.

1. Ollama를 설치하고 실행합니다.
2. GrowWise를 엽니다.
3. **설정 → AI 보조 기능**으로 이동합니다.
4. 상태가 **모델 준비 필요**라면 **기본 AI 준비**를 선택합니다.
5. 기본 Qwen 3.5 모델 하나가 텍스트 생성과 사진 이해를 함께 담당합니다.

GrowWise는 단순히 Ollama 포트가 열렸는지만 확인하지 않습니다. **현재 설정된 모델이 실제로 설치되어 있는지까지 확인**한 뒤 AI 사용 가능 여부를 표시합니다.

기본 AI 준비는 **텍스트+이미지 입력을 모두 지원하는 Qwen 3.5 모델 하나**와 검색용 임베딩 모델을 준비합니다. text/vision 처리는 애플리케이션 내부에서 별도 역할로 유지하지만, 기본 설치에서는 같은 모델 파일을 공유해 중복 다운로드와 모델 교체 비용을 줄입니다.

Desktop은 하드웨어에 따라 다음처럼 자동 선택합니다.

### Apple Silicon

| 통합 메모리 | 기본 멀티모달 모델 |
| --- | --- |
| 16 GB 미만 | `qwen3.5:2b` |
| 16 GB 이상 | `qwen3.5:4b` |
| 24 GB 이상 | `qwen3.5:9b` |
| 48 GB 이상 | `qwen3.5:27b` |
| 64 GB 이상 | `qwen3.5:35b` |

### NVIDIA GPU가 감지되는 Windows/Linux

| 감지된 총 VRAM | 기본 멀티모달 모델 |
| --- | --- |
| 6 GB 미만 | `qwen3.5:2b` |
| 6 GB 이상 | `qwen3.5:4b` |
| 10 GB 이상 | `qwen3.5:9b` |
| 24 GB 이상 | `qwen3.5:27b` |
| 32 GB 이상 | `qwen3.5:35b` |

여러 NVIDIA GPU가 보이면 감지 가능한 VRAM을 합산합니다. Apple Silicon은 GPU와 CPU가 공유하는 통합 메모리를 기준으로 봅니다. AMD/Intel GPU나 감지가 불확실한 환경에서는 시스템 메모리를 보수적으로 참고하며 자동 선택은 최대 9B로 제한합니다.

검색용 임베딩은 `nomic-embed-text`를 별도로 사용합니다.

일반 사용자는 GrowWise 설정 화면의 **사용 가능 / 모델 준비 필요 / Ollama 준비 필요** 상태만 확인하면 됩니다.

수동 설치나 개발 환경에서는 아래의 고급 설정을 사용할 수 있습니다.

---

## 고급 사용자: 명령줄에서 직접 준비

GrowWise가 자동으로 모델을 준비하도록 두지 않고 직접 관리하려면 다음 명령을 사용할 수 있습니다.

```bash
ollama pull qwen3.5:9b
ollama pull nomic-embed-text
```

설치 확인:

```bash
ollama list
```

---

## Ollama 설치

### Windows

Windows 10 이상에서 [Ollama Windows 다운로드](https://ollama.com/download/windows)를 사용할 수 있습니다.

PowerShell 설치 명령:

```powershell
irm https://ollama.com/install.ps1 | iex
```

설치 후 새 PowerShell을 열고 확인합니다.

```powershell
ollama --version
```

### macOS

[Ollama 다운로드 페이지](https://ollama.com/download)에서 macOS 앱을 설치하는 것이 가장 간단합니다.

Apple Silicon에서는 최신 Ollama가 MLX 기반 가속을 사용할 수 있으며, 모델에 따라 통합 메모리를 GPU 추론에 활용합니다.

설치 후 Terminal에서 확인합니다.

```bash
ollama --version
```

### Linux

공식 설치 스크립트:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

GrowWise 데스크톱의 현재 1차 배포 대상은 Windows/macOS이지만 Core 개발·검증에는 Linux도 사용할 수 있습니다.

---

## 내 컴퓨터에는 어떤 모델이 적당한가요?

아래 표는 **GrowWise를 함께 실행하면서 사용할 수 있도록 여유를 둔 권장 출발점**입니다. 모델 파일 크기가 곧 실제 메모리 사용량은 아닙니다. KV cache, 컨텍스트, Ollama 런타임, GrowWise, 운영체제가 추가 메모리를 사용합니다.

| 시스템 RAM / Apple 통합 메모리 | 권장 모델 | Ollama 모델 크기 | 용도 |
| --- | --- | ---: | --- |
| **8 GB** | `qwen3.5:2b` | 약 2.7 GB | AI 기능을 가볍게 시험 |
| **16 GB** | `qwen3.5:4b` | 약 3.4 GB | 일반적인 저사양 로컬 사용 |
| **24–32 GB** | **`qwen3.5:9b`** | 약 6.6 GB | GrowWise 기본 권장 균형점 |
| **48 GB** | `qwen3.5:27b` | 약 17 GB | 응답 품질 우선 |
| **64 GB 이상** | `qwen3.5:35b` | 약 24 GB | 큰 모델을 로컬에서 운용 |

Qwen 3.5 Ollama 모델은 텍스트와 이미지 입력을 지원하며 2B, 4B, 9B, 27B, 35B 등 여러 크기로 제공됩니다.

### NVIDIA/AMD/Intel GPU가 있는 Windows PC

시스템 RAM뿐 아니라 **VRAM**이 중요합니다.

대략적으로 모델 전체와 실행 여유가 VRAM에 들어가면 속도가 크게 유리합니다. 모델이 VRAM보다 크더라도 Ollama가 일부를 시스템 메모리에 둘 수 있지만 속도는 낮아질 수 있습니다.

보수적인 출발점:

| VRAM | 권장 시작 모델 |
| --- | --- |
| 4 GB 전후 | `qwen3.5:2b` |
| 6–8 GB | `qwen3.5:4b` |
| 10–12 GB | `qwen3.5:9b` |
| 16 GB | `qwen3.5:9b` 또는 더 큰 모델 시험 |
| 24 GB+ | `qwen3.5:27b` 시험 가능 |

Ollama 0.30 이후에는 NVIDIA 성능 개선과 함께 AMD/Intel 등을 위한 Vulkan 지원 범위도 확대되었습니다.

### Apple Silicon Mac

Apple Silicon은 CPU와 GPU가 통합 메모리를 공유합니다.

- **8 GB**: AI 없이 사용하거나 2B 모델 권장
- **16 GB**: 4B 모델이 가장 편안한 출발점
- **24 GB / 32 GB**: 9B 모델 권장
- **48 GB 이상**: 27B급 모델을 고려
- **64 GB 이상**: 35B급까지 고려 가능

큰 모델을 선택할수록 GrowWise와 브라우저, 다른 앱이 사용할 메모리도 남겨 두는 것이 좋습니다.

---

## 사양이 부족하면

로컬 AI를 반드시 켤 필요는 없습니다.

AI 기능을 끄면 다음은 계속 사용할 수 있습니다.

- 아이 프로필
- 학습·관찰 기록
- 사진 저장과 직접 기록
- 기본 검색
- 활동 관리
- 기본 자료 생성
- 교육과정 연결
- 백업과 복원

개발판에서 AI를 완전히 끄려면:

```bash
GROWWISE_LLM_FEATURES_ENABLED=false
GROWWISE_EMBEDDING_FEATURES_ENABLED=false
GROWWISE_VISION_FEATURES_ENABLED=false
```

---

## 더 작은 텍스트 모델로 바꾸기

예를 들어 16 GB PC에서 `qwen3.5:4b`를 사용하려면 먼저 모델을 받습니다.

```bash
ollama pull qwen3.5:4b
```

현재 pre-1.0 빌드에서 **기본 모델을 다른 모델로 바꾸는 고급 설정**은 환경변수 기반입니다. 일반 사용자는 이 설정을 건드릴 필요가 없으며, Desktop의 **기본 AI 준비**는 현재 설정된 모델을 자동으로 준비합니다.

### Windows

PowerShell:

```powershell
setx GROWWISE_MODEL_ID "qwen3.5:4b"
```

GrowWise가 이미 실행 중이라면 완전히 종료한 뒤 다시 실행합니다.

기본값으로 되돌리기:

```powershell
setx GROWWISE_MODEL_ID "qwen3.5:9b"
```

### macOS

현재 로그인 세션의 GUI 앱 환경에 적용:

```bash
launchctl setenv GROWWISE_MODEL_ID qwen3.5:4b
```

GrowWise를 완전히 종료한 뒤 다시 실행합니다.

기본값으로 되돌리기:

```bash
launchctl setenv GROWWISE_MODEL_ID qwen3.5:9b
```

이 설정은 현재 pre-1.0 운영 방식입니다. 정식 사용자 배포에서 모델 선택 UX가 변경되면 이 문서도 함께 갱신합니다.

---

## 사진 AI

GrowWise의 기본 사진 이해도 텍스트와 같은 Qwen 3.5 모델을 사용합니다. Qwen 3.5의 현재 Ollama 배포는 2B, 4B, 9B, 27B, 35B 모두 Text+Image 입력을 지원하므로 별도 비전 모델이 필수는 아닙니다.

애플리케이션 내부에서는 vision provider와 timeout을 독립적으로 유지합니다. 따라서 향후 특정 비전 모델이 더 적합한 경우에만 `GROWWISE_VISION_MODEL_ID`로 다른 모델을 지정할 수 있습니다.

메모리가 부족하거나 사진 분석을 원하지 않으면 기능만 끌 수 있습니다.

```bash
GROWWISE_VISION_FEATURES_ENABLED=false
```

---

## 검색용 임베딩

현재 기본값:

```bash
ollama pull nomic-embed-text
```

파일 크기가 작아 기본 검색 보강용으로 부담이 적습니다.

한국어·다국어 검색을 더 중시한다면 Ollama의 Qwen3 Embedding 계열도 사용할 수 있습니다. 가장 작은 공식 태그는 약 639 MB입니다.

```bash
ollama pull qwen3-embedding:0.6b
```

설정:

```bash
GROWWISE_EMBEDDING_MODEL_ID=qwen3-embedding:0.6b
```

임베딩 모델을 바꾸면 기존 벡터 인덱스와 차원이 달라질 수 있으므로 실제 배포에서는 인덱스 재생성 여부를 확인해야 합니다. 일반 사용자는 기본값을 유지하는 것이 가장 안전합니다.

---

## 모델 다운로드 용량 확인

Ollama에 설치된 모델:

```bash
ollama list
```

사용하지 않는 모델 삭제:

```bash
ollama rm qwen3.5:27b
```

모델은 GrowWise 설치 파일 안에 포함되지 않으며 Ollama의 모델 저장 영역에 별도로 저장됩니다.

---

## 기본 연결 정보

GrowWise의 기본 설정:

```text
Ollama 주소       http://127.0.0.1:11434
텍스트 모델       qwen3.5:9b
사진 모델         gemma4:e4b
임베딩 모델       nomic-embed-text
```

Ollama 상태 확인:

```bash
ollama list
```

API 확인:

```bash
curl http://127.0.0.1:11434/api/tags
```

Windows PowerShell에서는 브라우저에서 아래 주소를 열어 Ollama가 실행 중인지 확인하는 방법도 있습니다.

```text
http://127.0.0.1:11434
```

---

## 문제가 있을 때

### GrowWise는 켜지는데 AI만 동작하지 않음

1. **설정 → AI 보조 기능**의 상태를 확인합니다.
2. **Ollama 준비 필요**라면 Ollama가 실행 중인지 확인한 뒤 **상태 다시 확인**을 선택합니다.
3. **모델 준비 필요**라면 **기본 AI 준비**를 선택합니다.
4. 메모리가 부족하다면 아래 고급 설정에서 더 작은 모델을 선택할 수 있습니다.
5. AI가 준비되지 않아도 GrowWise의 로컬 기록 기능은 그대로 사용할 수 있습니다.

### 처음 응답만 매우 느림

모델을 처음 메모리에 올리는 시간일 수 있습니다. 같은 모델의 두 번째 요청부터 빨라지는지 확인합니다.

### 메모리가 부족함

- 텍스트 모델을 한 단계 줄입니다.
- 사진 AI를 끕니다.
- 브라우저나 다른 대형 앱을 종료합니다.
- 긴 컨텍스트를 사용하는 다른 Ollama 작업을 함께 실행하지 않습니다.

### 모델 속도를 실제로 측정하고 싶음

개발자용 benchmark:

```bash
uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3
```

하드웨어 기준 검증은 [운영 검증 문서](operational-validation.md)를 참고하세요.

---

## 공식 모델 정보

- [Ollama Qwen 3.5](https://ollama.com/library/qwen3.5)
- [Ollama Qwen3 Embedding](https://ollama.com/library/qwen3-embedding)
- [Ollama nomic-embed-text](https://ollama.com/library/nomic-embed-text)
- [Ollama 다운로드](https://ollama.com/download)
