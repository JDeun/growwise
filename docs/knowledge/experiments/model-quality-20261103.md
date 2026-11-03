# Observed local material generation: structured output and model quality

- Experiment: `EXP-MODEL-QUALITY-OBSERVED-20261103`, workstream `models`, observed 2026-11-03.
- Status: observed partial comparison; the complete multi-stage, six-kind hardware benchmark remains open.
- Revision: modified working tree based on `5c92dac76c32a8910dee6461556354c822713d33`.
- [Sanitized exact output and source hashes](model-quality-20261103.json), SHA256
  `0e6ef9495f269d0b910aa7b1a4096995ede755a7f7f79b39adcc5c31c0850b90`.
- Sources: source:GW-MODEL-BENCHMARK, source:GW-OLLAMA-STRUCTURED-20261103,
  source:GW-QWEN-2B-CARD-20261103, source:GW-GEMMA-12B-CARD-20261103.

## Question and method

Can the actual `Settings → create_model_provider(background=True) → OllamaProvider →
MaterialGenerationService` path produce a useful, structurally valid parent-review draft, rather
than merely complete a request or silently return the deterministic fallback?

The fixed synthetic input was elementary stage, math activity, topic `블록으로 수 세기`, interests
`동물`, no age/grade, no selected sources, no real records, and no Learning Wiki context. Each final
production-path model received one request, without warm-up or a fixed random seed. Both used
temperature 0.1, explicit reasoning off, context 8,192, output limit 4,096, timeout 600 seconds.
Timing includes model loading. Environment: macOS arm64, 16 GB unified memory, Python 3.12.13,
Ollama 0.40.3. Models were unloaded between comparisons.

A local synthetic capture wrapper recorded the candidate returned by the real provider, gate
issues and final publication artifact. It changed neither the production prompt nor its schema,
decoding, safety checks, candidate acceptance or publication logic. Original execution commands:

```bash
.venv/bin/python /tmp/growwise-production-model-acceptance.py
DIAG_MODEL=qwen3.5:2b .venv/bin/python /tmp/growwise-production-model-acceptance.py
```

The first wrapper invocation selected the installed Gemma model listed below. The disposable wrapper
and raw diagnostics remain local; the committed JSON contains the complete candidate, final material,
configuration, model digests and exact relevant source hashes, excluding generated IDs and timestamps.

## Production observations

| Model | Quantization / runner | One request | Final result |
| --- | --- | ---: | --- |
| `hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0` | GGUF Q4_0 / ggml | 95.511 s | `llm_enhanced`; candidate and published gates pass |
| `qwen3.5:2b` | safetensors MXFP8 / MLX | 10.911 s | `template_quality_fallback`; all four core structure checks fail |

Gemma manifest: `18a4d9511d9965d973356e62310a2793771c22456be408cc06a05f04a6376acd`.
Qwen manifest: `dfaf2605162e689c8cac330dc4a190c4c50ad30aa47814a8fe9b79fa5127e97e`.
Both official model cards display Apache-2.0. No model weights are redistributed here.

The implementation agent read Gemma's actual output, and the coordinating agent also inspected it.
It uses the synthetic animal interest to count animal blocks, build a house, add animals and revise
the construction. The learner chooses and draws/describes a counting strategy and considers another
method; the parent waits, listens and offers a concrete hint. There are genuine Markdown headings,
executable steps and open questions, no supplied final answer, no apparent counting misconception,
and no invented citations. The resulting material remains `review_pending`, never auto-approved.

Qwen generated only a preparation sentence. It had insufficient substantive content, fewer than two
headings, no executable numbered sequence and no open question. The quality gate correctly rejected
it; the published artifact is the intact deterministic fallback, not evidence of AI enhancement.

Gemma's model file was 7,150,993,832 bytes. During the request, host-wide wired memory was about
12.3 GiB and free memory was low. This is neither model-only resident memory nor a sampled peak;
it does not justify recommending Gemma 12B to every 16 GB device.

## Failure diagnosis and implemented correction

An earlier Qwen 2B request with the old English/full-publication prompt and implicit model-default
reasoning consumed all 8,192 output tokens in 263.272 seconds, returned empty final content and
ended with `done_reason=length`. The structured parser failed correctly. This was output-budget
exhaustion before final JSON, not a network timeout or broken function-call parser. Qwen's official
card also warns that the 2B model can enter thinking loops.

Turning thinking off made requests finish, but the earlier prompt still produced headings only or
copied the child and parent publication shells into one Markdown line. A three-line minimal native
JSON-schema test preserved newlines correctly, ruling out generic decoder newline loss. Increasing
context alone did not solve the weak candidate.

The production correction grounds the schema in the system prompt as Ollama recommends, describes
the two output audiences, and requests Korean activity core only. It supplies the existing selected
stage/kind standards and parent role, instead of showing every developmental stage and duplicating
the complete deterministic child and parent shells. Background thinking is now explicitly off by
default and can be opted into; its context is explicitly bounded/configurable. Source evidence and
internal guidance remain untrusted delimited data. Safety checks and Parent Review remain mandatory.
The candidate gate still requires substantive content, two distinct headings, two executable numbered
steps and an open question. No format-normalization shortcut or gate relaxation was used to accept
Gemma's output.

## Durable reproduction

The maintained benchmark now supports one selected kind. This command uses the same synthetic model
input and production provider path, and records full published output for inspection:

```bash
GROWWISE_DATA_DIR=/tmp/growwise-synthetic-model-check \
GROWWISE_MODEL_PROVIDER=ollama \
GROWWISE_MODEL_BASE_URL=http://127.0.0.1:11434 \
GROWWISE_MODEL_ID=hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0 \
GROWWISE_LLM_FEATURES_ENABLED=true \
GROWWISE_MODEL_TEMPERATURE=0.1 \
GROWWISE_BACKGROUND_AI_MODEL_TIMEOUT_SECONDS=600 \
GROWWISE_BACKGROUND_AI_MAX_OUTPUT_TOKENS=4096 \
GROWWISE_BACKGROUND_AI_REASONING_ENABLED=false \
GROWWISE_BACKGROUND_AI_MODEL_CONTEXT_TOKENS=8192 \
uv run python scripts/benchmark_model.py --kind math_activity --stage elementary
```

Unload that model before substituting `GROWWISE_MODEL_ID=qwen3.5:2b`. This is a reproduction procedure,
not a promise of byte-identical model output. Omitting `--kind` runs all six fixed kinds; warm-up and
repeated runs are needed before reporting a latency distribution.

## Limits and next action

These are two single production samples of one stage, kind and topic, without household testing,
teacher/parent review or measured learning effects. Synthetic regression tests separately cover all
material kinds, malformed output, safety, trust boundaries and durable worker recovery; those tests
do not establish every real model's quality. Small-model adequacy, a practical middle memory tier,
other stages/kinds and repeatability remain empirical questions. Do not weaken the quality gate to
turn a small-model fallback into success. No personal keys, child history, home paths or device
identifiers appear in the public evidence.
