# Observed typed activity generation and infant safety follow-up

- Experiment: `EXP-MODEL-TYPED-QUALITY-OBSERVED-20261103`, observed 2026-11-03, workstream `models`.
- Revision: modified working tree based on `e3c3b3b`; exact available phase/final source hashes and
  model manifest digests are retained in the [sanitized output artifact](model-typed-quality-20261103.json).
- JSON artifact SHA256: `5092dfc0092e7f47b255a5630298ecd88ebfb24751b8845ff8b3e7161ebcf52e`.
  Public sanitized artifacts remain in repository history; disposable raw diagnostic files may expire.
- This appends to the [earlier model diagnosis](model-quality-20261103.md); its files and ledger rows
  remain unchanged. Earlier inadequate outputs remain evidence, not successes retroactively relabeled.
- Environment: macOS arm64, 16 GB unified memory, Python 3.12.13, Ollama 0.40.3, one resident model at a time.
- Sources: source:GW-OLLAMA-STRUCTURED-20261103, source:GW-GEMMA-12B-CARD-20261103,
  source:GW-QWEN-4B-CARD-20261103, source:GW-CPSC-TOY-SAFETY-20261103,
  source:GW-CANADA-TOY-SAFETY-20261103.

## Conditions and exact execution

All samples used the actual production `create_model_provider(background=True)` and material service,
temperature 0.1, explicit reasoning off, context 8,192, output limit 4,096, timeout 600 seconds,
zero warm-up rounds, one measured request per topic and no fixed random seed. Synthetic elementary
inputs are the six fixed topics in `scripts/benchmark_model.py`; interests are `동물`, with no
supplied age/grade or source records. Infant input is separately recorded below.

The six-kind commands were run with model/runtime environment explicitly set, disposable synthetic
data directories, and no household data:

```bash
GROWWISE_DATA_DIR=/tmp/growwise-synthetic-4b-benchmark \
GROWWISE_MODEL_PROVIDER=ollama GROWWISE_MODEL_ID=qwen3.5:4b \
GROWWISE_MODEL_BASE_URL=http://127.0.0.1:11434 GROWWISE_LLM_FEATURES_ENABLED=true \
GROWWISE_MODEL_TEMPERATURE=0.1 GROWWISE_BACKGROUND_AI_MAX_OUTPUT_TOKENS=4096 \
GROWWISE_BACKGROUND_AI_REASONING_ENABLED=false GROWWISE_BACKGROUND_AI_MODEL_CONTEXT_TOKENS=8192 \
.venv/bin/python scripts/benchmark_model.py --stage elementary
```

The Gemma run used the same profile with `GROWWISE_DATA_DIR=/tmp/growwise-synthetic-gemma-benchmark`
and `GROWWISE_MODEL_ID=hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0`. The English correction used
that model/profile and `--stage elementary --kind english_card` with another disposable directory.
The two model batches differed by generic pedagogy refinements; this is not a controlled model-only
comparison. The six-kind Gemma material-file hash was not independently captured at launch; the JSON
states its phase and retains exact subsequent source hashes instead of inventing a historical digest.

## Typed response fixes formatting, not educational judgment

The free-form Qwen 4B math sample took 28.427 seconds and returned one heading with HTML `<br>`
separators. It failed the unchanged structure gate. Instead of guessing structure or repairing
arbitrary HTML, the model now declares actual section headings, action arrays and open questions;
the app renders those declared fields into Markdown and applies the same safety and quality checks.
The public `MaterialDraft` remains compatible with custom providers and is revalidated at the boundary.

The subsequent Qwen 4B typed six-kind batch accepted all six structurally, average 23.900 seconds,
reported p95 27.482 seconds. Manual inspection still required revision in every kind:

| Kind | Manual finding |
| --- | --- |
| Reading | Invented a smiling cat and assumed a household pet without selected-book evidence |
| English | Incoherent role/topic progression and mother-only framing |
| Math | Cards 1–3 followed by a fourth block; unhelpful instruction to give no feedback |
| Science | Prediction after observation, imprecise sequencing and a malformed word |
| Writing | Parent edits the learner's text |
| Field trip | Compares actual findings before visiting; inappropriate moving-book assumption |

A separate typed math sample also included mixed Chinese/Korean fragments and a leading question
about counting the last block first. These outputs are preserved in JSON. A structural `llm_enhanced`
flag is insufficient to recommend the model's educational quality.

## Stronger-model review and English contract correction

Gemma 4 12B QAT Q4_0 accepted six structures, average 105.606 seconds, reported p95 114.557 seconds.
The implementation and coordinating agents read the actual cores and parent notes. Reading asks for
picture evidence; math compares counting the same set in different arrangements; science predicts
before observing; writing preserves learner-owned revision; field trips separate preparation,
observation and later reflection. Parents must still choose suitable books/materials and follow venue
rules. No family field trial or learning-effect evaluation was performed.

Its initial English card contained only Korean instructions with no actual English expression.
That sample was **not accepted for use**, despite its structural flag. The kind contract now asks for
usable target expressions and a short modeled exchange; the candidate gate rejects English cards
without a Latin target expression before any publication shell is added. This is only a minimum
language-presence check, not grammar/proficiency validation. The deterministic Core English fallback
also supplies optional, stage-appropriate real expressions and turn-taking examples.

The English-only rerun took 114.802 seconds and produced `Good morning!`, `Hello!`, and `Hi there!`
with Korean meanings, parent-child turn-taking and learner choices of animal, situation and voice.
Both reviewing agents found it usable as a parent-review draft. The other five kinds' generation
paths were unchanged by this English-specific correction. This does not make untested topics or
model versions automatically ready.

## Nine-month first-use check and safety correction

The exact synthetic first-use input was stage `infant_0_2`, age 9 months, kind `activity_guide`, topic
`소리와 움직임 살펴보기`, no interests, source records, private history or extra goal instructions.
A disposable capture wrapper called the actual production provider/service; it recorded the returned
typed response and final material without changing prompts or acceptance logic:

```bash
.venv/bin/python /tmp/growwise-infant-model-acceptance.py
```

The first request took 99.780 seconds and passed the old structural checks, but permitted mouthing an
unspecified wooden block/cloth. Manual safety review rejected it. Its exact candidate and old generic
safety shell remain in the artifact. The new infant contract starts with voice/face/hand interaction,
requires close adult supervision on a flat floor/mat, excludes small/detachable parts and cords, and
does not encourage object-mouthing or forced sound/posture performance. Preparation and safety
instructions now appear in both the main material and parent guide, including offline fallback.

A narrow, conservative infant hazard check rejects positive object-mouthing and named play hazards
before publication, while allowing protective directions such as `입에 넣지 않게` and removal if the
child brings a material toward the mouth. Regression tests cover mixed positive/negative clauses,
unsafe model notes, neutral protective prose, and all deterministic infant kinds. The check is not a
complete language or toy-safety classifier. CPSC/Health Canada guidance informs the small-parts,
age-label and cord precautions; the application does not certify products.

The same-input rerun took 92.128 seconds and passed the checks. Both reviewing agents found it
parent-reviewable **within the explicit visible safety shell**: voice/face turn-taking first,
observation of spontaneous movement, no reading/writing/correct-speech/independent-sitting demand,
no small parts and no object-mouthing instruction. Optional cloth/cushion exploration still requires
adult age/size/cleanliness/damage checks, continuous arm-reach floor supervision, no face covering
and removal if brought toward the mouth. The material remains `review_pending`.

## Memory, reproduction and limits

The official Qwen 4B tag installed as MLX NVFP4, digest
`7f3251fa6878a78a606bcb3c074283306e5ad2ea411a7774a9dd98a4bc7f2d13`, file 3,973,305,013 bytes.
Ollama reported about 4.0 GB resident. Gemma's GGUF Q4_0 digest remains
`18a4d9511d9965d973356e62310a2793771c22456be408cc06a05f04a6376acd`; Ollama reported about 7.7 GB
resident. Host-wide wired samples were about 8.6 GiB with 4B and 12.3 GiB with Gemma. Those are not
model-only RSS or measured peaks. **Gemma 12B is not a blanket recommendation for 16 GB devices.**
Both model cards report Apache-2.0; weights are not redistributed in this repository.

To reproduce the infant case, use the same model/profile and call the maintained API directly:

```python
from growwise.domain import ChildProfile, MaterialKind, Stage
from growwise.generators import MaterialGenerationService
from growwise.model import create_model_provider
from growwise.config import Settings

settings = Settings()  # use the explicit synthetic data directory/model/profile above
material = MaterialGenerationService(create_model_provider(settings, background=True)).generate(
    child=ChildProfile(nickname="합성아이", stage=Stage.INFANT_0_2, age_months=9),
    kind=MaterialKind.ACTIVITY_GUIDE,
    topic="소리와 움직임 살펴보기",
)
print(material.model_dump_json(indent=2))
```

There are no repeated per-kind latency distributions: reported p95 across six different topics is
essentially their slowest sample, not a stable latency promise. No seed was fixed, so outputs vary.
Quantizations, runtimes, other languages, stages, topics and safety circumstances remain unproven.
Software regressions, deterministic structure, agent artifact review and real learning outcomes are
different claims. No real child history, credentials, home paths or device identifiers are published.
