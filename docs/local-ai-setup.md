# GrowWise 로컬 AI 설정 가이드

GrowWise는 AI 없이도 사용할 수 있습니다. 로컬 AI는 기록 검색, 자료 생성, 사진 이해 등을 **보강하는 선택 기능**입니다.

가장 간단한 로컬 실행 방법은 [Ollama](https://ollama.com/)입니다. GrowWise는 기본적으로 `http://127.0.0.1:11434`의 Ollama를 찾습니다.

> 하드웨어 표는 설치를 시작할 때의 참고값이며 교육 자료 품질을 보증하지 않습니다.
> **2026-11-03 실측**과 그 한계는 아래 자료 생성 품질 항목에 기록했습니다. 실제 속도와 메모리는
> CPU/GPU, 메모리 대역폭, 컨텍스트 길이에 따라 달라집니다.

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
| 16 GB 미만 | `qwen3.5:2b-mlx` |
| 16 GB 이상 | `qwen3.5:4b-mlx` |
| 24 GB 이상 | `qwen3.5:9b-mlx` |
| 48 GB 이상 | `qwen3.5:27b-mlx` |
| 64 GB 이상 | `qwen3.5:35b-mlx` |

### NVIDIA GPU가 감지되는 Windows/Linux

| 감지된 총 VRAM | 기본 멀티모달 모델 |
| --- | --- |
| 6 GB 미만 | `qwen3.5:2b` |
| 6 GB 이상 | `qwen3.5:4b` |
| 10 GB 이상 | `qwen3.5:9b` |
| 24 GB 이상 | `qwen3.5:27b` |
| 32 GB 이상 | `qwen3.5:35b` |

여러 NVIDIA GPU가 보이면 감지 가능한 VRAM을 합산합니다. Apple Silicon은 GPU와 CPU가 공유하는 통합 메모리를 기준으로 보고, Ollama가 제공하는 Qwen 3.5 MLX 태그를 우선 사용합니다. AMD/Intel GPU나 감지가 불확실한 환경에서는 시스템 메모리를 보수적으로 참고하며 자동 선택은 최대 9B로 제한합니다.

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

| 시스템 RAM / Apple 통합 메모리 | 하드웨어 출발점 | 모델 파일 크기 예시 | 용도 |
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

### 자료 생성 품질과 실제 확인 범위

현재 `growwise.material.v7`의 검사 범위와 한계는
[자료 초안 품질 경계](material-quality-contract.md)를 참고하세요. 과거 실측 결과는 당시
출력으로 보존되며, 새 검사에 통과한 회귀 사례를 새 모델 실행이나 교육 효과 검증으로 세지 않습니다.

모델이 설치되어 있고 연결 확인에 성공해도 교육 자료를 제대로 만드는지는 별도 문제입니다.
자동 선택 표는 실행 가능한 모델의 출발점이며, 해당 크기의 교육 품질 평가 결과가 아닙니다.

2026-11-03 macOS arm64·통합 메모리 16 GB·Ollama 0.40.3에서 초기 자유 형식 본문 경로의
합성 입력 하나(`초등 / 수학 / 블록으로 수 세기`)를 실제 생성 코드로 확인했습니다.

| 실제 모델·설정 | 1회 결과 | 해석 |
| --- | --- | --- |
| `qwen3.5:2b` · MLX MXFP8 | 약 10.91초, 품질 대체 초안 | 준비 문장만 생성해 본문 구조·단계·질문 기준을 통과하지 못함 |
| `hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0` | 약 95.51초, AI 보강 초안 | 실행 단계·열린 질문·부모 진행 도움을 생성하고 구조·안전 검사를 통과함 |

두 측정 모두 추론 모드 끔, 컨텍스트 8,192, 출력 상한 4,096 토큰, temperature 0.1,
워밍업 없이 1회이며 모델 로딩 시간을 포함합니다. Gemma 결과는 구현 에이전트가 본문을 읽고
수 개념 오류, 아이의 선택·설명, 부모의 힌트 방식도 점검했습니다. 이는 실제 부모·교사의 평가나
학습 효과 검증이 아닙니다. 다른 단계·자료 유형·모델 버전·기기까지 일반화하지 않습니다.

후속 구현은 모델이 소제목·활동 단계·질문을 각각 생성하게 하여 표시 형식의 실패를 줄였습니다.
형식이 맞아도 내용 검토는 별개입니다.

| 후속 실제 확인 | 자동 검사와 본문 검토 |
| --- | --- |
| Qwen 4B · 초등 여섯 유형, 평균 약 23.90초 | 여섯 형식은 통과했지만 확인되지 않은 전제·수량 불일치·부모의 글 수정 지시 등이 있어 모두 보완 필요 |
| Gemma 12B · 초등 여섯 유형, 평균 약 105.61초 | 다섯 유형은 부모 검토용으로 읽을 수 있었고, 영어 유형은 실제 영어 표현이 없어 보완 필요 |
| Gemma 12B · 수정 후 영어 한 건, 약 114.80초 | 실제 인사 표현·의미·주고받기를 포함한 본문 확인 |
| Gemma 12B · 9개월 활동 가이드 한 건, 수정 후 약 92.13초 | 보호자 소리·표정 놀이와 자발적 움직임 관찰; 본문·교안의 구체적 영아 안전 조건 아래 검토 가능 |

영아의 첫 응답은 불명확한 물건의 구강 탐색을 허용해 검토에서 거절했습니다. 현재는 보호자 근접
관찰, 평평한 바닥, 작은 물건·분리 부품·끈 제외, 물건을 입에 넣도록 유도하지 않기와 중단 기준을
기본 초안에도 표시하고 위험한 긍정 지시를 거절합니다. 이 검사가 모든 위험을 찾아내거나
장난감 안전을 인증하는 것은 아닙니다. 영어 카드의 기본 초안도 실제 영어 표현과 짧은 대화 예시를
포함하며, AI 본문이 한국어 지시만 반환하면 품질 대체 초안을 유지합니다.

후속 측정도 워밍업 없이 유형별 한 건이며 반복 지연 분포나 실제 학습 효과를 확인한 결과가 아닙니다.
Qwen 4B와 Gemma 비교 사이에 교육 지침도 보완되어 순수한 모델 간 성능 비교로 해석할 수 없습니다.
[후속 실제 생성물·거절·안전 보완 기록](knowledge/experiments/model-typed-quality-20261103.md)에
원래 부족했던 출력과 수정 후 출력을 모두 보존했습니다. **2B/4B 자동 선택은 교육 품질 보증이 아닙니다.**

후속 반복 검사는 워밍업 뒤 유형별 3회를 실제 생성하고 전체 본문과 부모 교안을 읽었습니다.
실측 중 영어 뜻 오류, 영아 교안의 학령기 문구, 반응이 나올 때까지 반복하는 지시,
불명확한 방울과 문자 혼용을 발견해 검사를 보완했습니다. 최종 비교 범위의 24개 실제 측정
응답을 현재 v7 경로로 재생하면 22개는 AI 본문을 유지하고, 2개는 검토한 기본 초안을 선택합니다.
이는 서로 다른 버전에서 입력·출판이 변하지 않은 경로를 구분해 모은 범위이며 v7로 24회를
새로 생성한 결과가 아닙니다. 모든 부족 출력과 fallback, 모델 digest·설정·메모리·지연·검토
한계는 [반복 실측 기록](knowledge/experiments/model-repeat-quality-20261103.md)에 있습니다.
자동 검사는 전체 문법·사실·교육 효과를 판정하지 않으며 부모의 실제 검토가 계속 필요합니다.

Gemma의 모델 파일은 약 7.15 GB였지만 실행 중 **호스트 전체** wired 메모리가 약 12.3 GiB로
관찰돼 16 GB 장비의 여유가 작았습니다. 모델 단독 메모리나 최대 사용량을 측정한 값은 아닙니다.
따라서 Gemma 12B를 모든 16 GB 장비의 기본 권장으로 지정하지 않습니다. 작은 모델이 계속
기준을 통과하지 못하면 기본 초안을 검토해 사용하거나, 여유 있는 기기에서 더 큰 모델을 평가하세요.
검사를 약하게 바꾸어 작은 모델의 결과를 통과시키지 않습니다.

모델 digest, 실제 생성물, 실패 분석과 재현 조건은
[초기 합성 실험](knowledge/experiments/model-quality-20261103.md)과 위 후속 기록에 있습니다.
[Qwen 2B 모델 카드](https://huggingface.co/Qwen/Qwen3.5-2B)와
[실측 Gemma 배포 모델 카드](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf)는
모두 Apache-2.0을 표시합니다. 모델 파일은 앱에 포함하지 않습니다.

### 오래 걸리는 자료 생성의 설정

자료 AI 보강은 먼저 저장한 초안을 바탕으로 백그라운드에서 진행합니다. 기본값은 다음과 같습니다.
대화의 짧은 응답 제한과 별도로 적용되며, 품질·안전 검사에서 거절된 결과가 원본 초안을 덮어쓰지 않습니다.

| 환경변수 | 기본값 | 적용 범위 |
| --- | ---: | --- |
| `GROWWISE_BACKGROUND_AI_MODEL_TIMEOUT_SECONDS` | `600` | 백그라운드 모델 호출 제한, 초 |
| `GROWWISE_BACKGROUND_AI_MAX_OUTPUT_TOKENS` | `8192` | 백그라운드 출력 상한 |
| `GROWWISE_BACKGROUND_AI_REASONING_ENABLED` | `false` | Ollama 추론 모드 명시적 선택 |
| `GROWWISE_BACKGROUND_AI_MODEL_CONTEXT_TOKENS` | `8192` | Ollama 컨텍스트, 입력과 출력에 필요한 메모리에 영향 |

긴 추론이 언제나 좋은 본문을 만들지는 않습니다. 기존 Qwen 2B 기본 추론 모드에서는 8,192 토큰을
모두 사용하고 최종 JSON을 반환하지 않은 사례도 직접 확인했습니다. 추론을 사용하려면 `true`로
명시한 뒤 실제 결과를 다시 평가하세요. 더 긴 컨텍스트도 메모리를 더 사용하므로 동시에 여러 모델을
올리지 말고 모델과 기기에 맞추어 조절합니다. 모델별 추론 지원 여부는 공급자 문서를 확인해야 합니다.

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

모델을 받은 뒤 **설정 → 로컬 AI 모델 관리**에서 **기록·자료 만들기** 용도를 선택하고
설치 목록의 **이 모델 사용**을 누릅니다. 용도 지원 여부를 확인한 뒤 선택을 저장하고 Core를
다시 시작하므로 실제 생성에 새 모델이 적용됩니다. 다른 용도의 모델은 자동 변경하지 않습니다.
사진·검색 모델도 각각 지원 용도에 맞는 설치 모델을 선택할 수 있습니다.

아래 환경변수는 저장된 앱 선택이 없는 경우의 고급 기본값입니다. 로컬 Ollama의 앱 선택은
다음 실행에도 유지되며 이 기본 모델 ID보다 우선합니다. 원격·비-Ollama 구성을 사용하면
저장된 로컬 모델 선택을 그 공급자에 강제로 적용하지 않습니다.

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

일반 사용자는 환경변수보다 앱의 모델 선택을 사용하면 됩니다. 모델 변경은 Core 연결을
재시작하므로 진행 중인 AI 작업이 끝난 뒤 실행하는 편이 좋습니다.

---

## 사진 AI

GrowWise의 기본 사진 이해도 텍스트와 같은 Qwen 3.5 모델을 사용합니다. 기본 설치에서는
text/vision 역할이 같은 모델 artifact를 공유하므로 별도 비전 모델을 추가로 다운로드하지 않습니다.
Qwen 3.5의 현재 Ollama 배포는 2B, 4B, 9B, 27B, 35B 모두 Text+Image 입력을 지원합니다.

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

모델이나 endpoint가 바뀌면 기존 벡터를 새 모델의 벡터와 섞어 비교하지 않습니다. 저장된 원문으로
검색 시 필요한 벡터를 순차 재생성하며, 모델을 사용할 수 없을 때도 원문과 어휘 검색은 유지합니다.

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

앱에서도 **설정 → 로컬 AI 모델 관리 → 삭제…**로 모델을 선택해 확인 후 삭제할 수 있습니다.
같은 Ollama를 사용하는 다른 앱에도 영향을 주지만 GrowWise의 아이 기록·사진·자료는 삭제하지
않습니다. 사용 중 모델을 지우면 다시 준비하기 전까지 해당 AI 기능은 fallback으로 동작합니다.

다운로드의 SHA256 검증은 [Ollama pull](https://github.com/ollama/ollama/blob/main/docs/api.md#pull-a-model)
과정에서 수행합니다. 목록의 digest는 설치 메타데이터이며 현재 디스크 내용을 다시 읽어 검증했다는
의미가 아닙니다. GrowWise는 모델 다운로드·목록·선택·삭제를 configured loopback Ollama에만
요청하며 사용자 입력 URL이나 원격 redirect를 따라가지 않습니다.

---

## 기본 연결 정보

GrowWise의 기본 설정:

```text
Ollama 주소       http://127.0.0.1:11434
텍스트·사진 모델  qwen3.5:9b
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
uv run python scripts/benchmark_model.py --kind math_activity --stage elementary
uv run python scripts/benchmark_model.py --warmup-rounds 1 --repeats 3
```

첫 명령은 자료 유형 하나를 확인합니다. 둘째 명령은 여섯 유형 전체를 워밍업 후 반복합니다.
속도뿐 아니라 `generator_mode_counts`, `llm_used_ratio`와 실제 본문·부모 교안을 함께 읽어야 합니다.
대체 초안만 생성한 빠른 실행은 AI 자료 생성 성공이 아닙니다.

하드웨어 기준 검증은 [운영 검증 문서](operational-validation.md)를 참고하세요.

---

## 공식 모델 정보

- [Ollama Qwen 3.5](https://ollama.com/library/qwen3.5)
- [Ollama Qwen3 Embedding](https://ollama.com/library/qwen3-embedding)
- [Ollama nomic-embed-text](https://ollama.com/library/nomic-embed-text)
- [Ollama 다운로드](https://ollama.com/download)


## 원격 모델 고급 설정과 개인정보

GrowWise의 일반 사용자 경로는 loopback Ollama를 전제로 합니다.

OpenAI-compatible 원격 공급자의 개인 API 키는 **설정 → 개인 API 키 → 원격 호환 AI · 고급 설정**에서
저장할 수 있습니다. macOS Keychain/Windows Credential Manager에만 보관하고 평문 앱 설정이나
portable backup에는 넣지 않습니다. 화면에는 저장 여부만 표시하며 키를 읽어 다시 채우지 않습니다.
키 저장·사용 해제는 Core를 다시 시작해 실제 공급자 환경에 반영합니다.

저장된 키는 환경변수의 키보다 우선합니다. **키 사용 해제…**는 OS 보안 저장소에 해제 상태를
남기므로 상위 환경변수의 키도 이 앱에서는 자동으로 다시 사용하지 않습니다. 발급 서비스의
키 자체를 취소하는 기능은 아니며, 다시 사용하려면 새 키를 저장합니다.

**실제 연결 확인**은 현재 설정된 OpenAI-compatible 공급자에 고정된 테스트 문장만 보냅니다.
학습 기록·장기 맥락·사진을 연결 확인에 사용하지 않습니다. 연결 확인은 모델 품질 평가가 아닙니다.
키를 저장해도 아래 원격 전송 동의나 공급자·endpoint 설정은 자동 변경하지 않습니다.

- text 모델을 다른 PC나 서버의 Ollama/OpenAI-compatible endpoint로 바꾸려면
  `GROWWISE_MODEL_REMOTE_ALLOWED=true`라는 별도 opt-in이 필요합니다.
- 사진 원본이 들어가는 vision 경로는 별도
  `GROWWISE_PHOTO_REMOTE_VISION_ALLOWED=true` 동의 경계를 사용합니다.
- 사진 처리의 text 경로도 `GROWWISE_PHOTO_REMOTE_TEXT_ALLOWED=true`가 별도로 필요합니다.
- 검색용 embedding은 아동 기록을 벡터화하므로 현재 provider 구현에서는 **loopback 전용**입니다.
- Learning Wiki의 장기 기록 합성은 원격 text provider로 보내지 않습니다. 원격 모델만 사용
  가능한 경우에도 Wiki는 로컬 deterministic projection으로 유지됩니다.

Desktop의 **기본 AI 준비**는 모델 존재 여부가 로컬 Ollama에서 명시적으로 "없음"으로 확인된
경우에만 다운로드를 시도합니다. 원격 endpoint나 확인 불가능한 endpoint에는 자동 pull을 보내지
않습니다.
