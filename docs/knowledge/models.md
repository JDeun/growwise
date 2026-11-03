# Model selection investigation

현재 근거: source:GW-MODEL-DESIGN, source:GW-MODEL-CODE, source:GW-MODEL-BENCHMARK,
source:GW-PR-177.

[설정 안내](../local-ai-setup.md)는 하드웨어별 출발점이다. 모델 이름·설치 성공·출력 길이만으로
지연, 메모리 적합성 또는 교육 품질을 증명하지 않는다. 실제 사용 artifact는 모델의 정확한
revision/digest, provider, 양자화, 일반화한 OS/CPU/RAM/VRAM, 컨텍스트·warmup·반복 조건을
남겨야 한다. 머신 이름·사용자 경로·장치 식별자는 제거한다.

[benchmark harness](../../scripts/benchmark_model.py)는 고정 synthetic 입력을 사용한다.
원하는 provider가 실제 호출됐는지, generator mode가 fallback인지, 본문과 부모 교안이
안전·연령 적합·실행 가능한지 확인한다. core-only 측정은 LLM 성능 증거가 아니다.

2026-11-03 [실제 로컬 모델 조사](experiments/model-quality-20261103.md)는 합성 초등 수학 입력을
앱의 실제 생성 경로로 실행했다. Gemma 12B Q4_0 한 건은 구조·안전 검사와 구현 에이전트의 본문
검토를 통과했고, Qwen 2B MXFP8 한 건은 품질 fallback이었다. 모델 크기별 보편적 품질이나
교육 효과를 입증한 결과는 아니다. source:GW-MODEL-QUALITY-OBSERVED-20261103.

실측 절차는 [operational validation](../operational-validation.md), 추적 상태는
[experiment ledger](experiments.jsonl)에 있다. 실제 모델 비교 전 두 설정에 같은 fixture를
쓰고 latency와 품질을 각각 보고한다.
