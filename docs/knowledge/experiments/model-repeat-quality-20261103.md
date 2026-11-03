# Repeated production material quality observation · 2026-11-03

This extends the [earlier typed-output experiment](model-typed-quality-20261103.md). That evidence,
including the weak Qwen 4B outputs and the initial unsafe infant response, remains unchanged.
The [new complete JSON artifact](model-repeat-quality-20261103.json) contains every completed
synthetic response, model input, provider-parsed typed response, full final material and parent guide,
acceptance/fallback mode, per-call manual review, source hashes and memory samples. It excludes
chain-of-thought. These are implementation-agent artifact reviews, not actual parent approval,
teacher evaluation, child-use tests or evidence of learning gains.

## Method and effective profile

All inference used the existing local `hf.co/google/gemma-4-12B-it-qat-q4_0-gguf:Q4_0` installation,
manifest digest `18a4d9511d9965d973356e62310a2793771c22456be408cc06a05f04a6376acd`, on macOS arm64
with 16 GB unified memory and Ollama 0.40.3. No new model, hosted inference, household history,
real child photograph or personal credential was used. The actual production
`create_model_provider(settings, background=True)` and `MaterialGenerationService.generate` were
called, with temperature 0.1, reasoning disabled, context 8,192 tokens, output limit 8,192 tokens and
configured client timeout 600 seconds. No seed was fixed. A disposable wrapper recorded the parsed
response and production result; it did not alter provider response, prompt or acceptance logic.

One warmup round precedes three measured rounds for each selected stage/kind/topic. Every warmup
is retained and reviewed but excluded from measured latency summaries. Profiles/topics are the
six fixed elementary benchmark cases with animal interest, plus a nine-month infant without added
interests or sources: reading `큰 그림 보드북 함께 보기` and activity guide `소리와 움직임 살펴보기`.
This is one topic per kind, not a broad topic distribution. Repeats reuse the same loaded runtime and
may benefit from runtime prompt caching; they are not independent cold starts.

The coordinator concurrently performed bounded Python/frontend/Rust validation, an actual-Core/UI
soak and a fresh single-process packaged-Core build. Exact load notes are attached. Timings include
production generation and the small diagnostic capture, not subsequent artifact writes. These are
observed concurrent-validation latencies, not idle-hardware performance certification. Host-wide
`vm_stat` and Ollama resident-model estimates are not process-only RSS, leak analysis or certified peaks.

## Failed pilot and superseding corrections

The v3 pilot completed three warmups. Its English card translated `How are you?` as `잘 잤니?` and
supplied a question expression without a matched modeled response. That complete output is retained
as requiring revision; the fourth request was interrupted and is not counted as a completed sample.
The v4 prompt explicitly requires faithful Korean meanings and short paired exchanges. Complete
beginner model dialogues are useful scaffolding, rather than an impermissible replacement for a
learner's thought. The minimum gate rejects a few known wrong greeting glosses; it is not a general
translation or grammar checker. The
[Cambridge publisher excerpt](https://assets.cambridge.org/97805216/34779/excerpt/9780521634779_excerpt.pdf)
provides a primary reference distinguishing greetings, condition responses and parting expressions.
No publisher text or PDF is redistributed.

The v4 run completed all 24 elementary calls (one six-kind warmup and three measured six-kind rounds)
and four infant calls before it was stopped for a confirmed publication defect. The infant model
cores described appropriate caregiver-led book/gaze/touch or voice/face interaction, yet the app's
deterministic parent-guide boilerplate asked a nine-month infant to summarize in their own words,
explain alternative methods and use drawing as a response. All four complete infant artifacts are
therefore recorded as requiring revision despite their automatic acceptance. The earlier one-off
infant review missed this boilerplate contradiction; it must not be cited as final proof of age fit.

Version v5 replaces the infant goal/process, parent scenario, parent actions, hints, observations,
difficulty adjustment, follow-up and recording guidance with caregiver observation, waiting,
responsive interaction and stop signals. Explicit independent-schoolwork demands are checked in
parent notes and the final publication shell, as well as in the AI core. Read-aloud support and
negative protective directions remain allowed. Both template fallback and model-enhanced infant
artifacts receive the age-appropriate shell and existing concrete safety conditions.

One v4 measured science question incorrectly coordinated visible appearance and sound with a hearing
verb. Version v5 asks for sense-appropriate observation questions and permits observing no change or
sound; a narrow regression catches that exact known mismatch. A later v5 sample still contains an
awkward free-form coordination. It is recorded as needing a minor editorial correction rather than
silently treated as perfect semantic output. Version v6 explicitly requests separate short questions
for different senses and rejects this additional observed coordination. It does not rewrite model
text or claim to check all Korean grammar.

The v5 infant activity second measured sample asks the caregiver to repeat interaction until the
infant makes a favored expression or sound. The complete final guide says not to require sounds or
actions, but that should not force a parent to resolve contradictory instructions. This artifact is
recorded as requiring revision. Version v6 rejects positive repetition-until-target-response demands
in core, parent notes and final publication. Negative protective directions, a brief wait for voluntary
response and a caregiver briefly mirroring the infant remain valid. Only the infant activity-guide
prompt receives the additional explanation; the infant reading prompt and publication are unchanged.
A text-contract gate still cannot replace review of every statement.

## Version partitions and comparison limits

The v5 targeted run has 12 completed calls: elementary science and both infant kinds each have
one warmup plus three measured calls. The final v6 targeted run repeats only the changed science
and infant activity paths, each with one warmup and three measured calls (eight calls total).
Five unaffected elementary kinds retain three actual v4 measured samples each; infant reading retains
three actual v5 measured samples. Exact replay of all 24 corresponding provider outputs (including
warmups) verifies byte-identical system/user prompts, published body and parent guide at v6, with
current acceptance checks passing. This is not another model inference or timing observation.
The generator-version label advances to v6. Source file hashes and replay checks are attached.
Intermediate v3/v4/v5 working trees were not separate source releases; hashes alone do not make their
entire historical source recoverable. Their exact prompts/schema, parsed responses and final artifacts
are preserved for inspection and direct prompt replay; the current v7 source files and recorded replay hashes identify the current service path. No reconstruction of missing historical source is
claimed.

Do not combine v4/v5/v6 phase latencies as a controlled model comparison, or count interrupted calls as
fallbacks. Different source contracts, prompts, warmup/residency and concurrent load are explicit.
All manually flagged artifacts remain in the JSON, including the automatically accepted failures.

## Final v7 boundary replay and fallback review

No further model inference was needed for v7. Prompts and accepted model-authored publication stay
unchanged from v6. All 51 completed candidates were replayed through the current production service:
45 remain model-enhanced, five select a quality fallback and one selects a safety fallback. The JSON
records classifications, current gates, exact body/guide hashes and complete fallback materials.
The original actual outputs are retained independently; replay never relabels them as newly generated.

The final v6 measured science first sample contains the copyediting error `기록纸에`. The v7 minimum
gate catches unexpected CJK characters embedded between Korean characters, using fixed-width
lookarounds and a bounded character run. A literal supplied in the topic/source, explicit Hanja/
Chinese/Japanese learning context, normal parenthesized Hanja, ordinary proper names and foreign
sentences remain supported. This does not check every Korean or foreign-language word or grammar.
The saved candidate now selects a quality fallback, rather than being silently corrected.

The first v6 measured infant activity proposes an unspecified `가벼운 방울` within the infant's reach.
That could mean a loose or detachable part; generic final-shell safety does not establish that it is
an age-appropriate enclosed rattle. The v7 conservative safety check rejects positive loose-bell/marble
placement or manipulation unless age-appropriate whole construction and enclosed contents are
explicit. Protective non-use instructions, pictures, voice imitation and explicitly enclosed whole-toy
wording remain allowed. This is an inference for safer text handling informed by official
[CPSC small-parts guidance](https://www.cpsc.gov/Business--Manufacturing/Business-Education/Business-Guidance/Small-Parts-for-Toys-and-Childrens-Products)
and [rattle guidance](https://www.cpsc.gov/FAQ/Rattles); it does not certify any toy or declare every bell unsafe.
That saved candidate now selects the safety fallback.

The exact current science and infant fallback documents were read in full as generic parent-review
scaffolds. The lower-stage science observation variant initially omitted the prediction/comparison
promised by its outer stage contract. A fallback-only adjustment now records a prediction before
observation and compares it with the result afterward. It leaves the example sent to the model and
accepted model content unchanged. Infant fallback supports caregiver observation and responsive play,
voice/face alternatives and concrete safety/stop guidance. These generic templates still require a
parent to select real suitable materials and adapt the activity; they are not bespoke expert lessons.

The final comparison cohort has 24 actual measured samples, partitioned by unchanged inference paths:
15 elementary samples from v4, three infant-reading samples from v5 and six affected-path samples from
v6. Under v7 replay, 22 retain their model-authored core and two use the reviewed generic fallback.
Raw manual judgments still flag the typo and unspecified bell; selecting a fallback does not turn those
raw outputs into quality passes. Source versions, replay and actual inference are separate evidence.

## Artifact review rubric

Each complete raw candidate, final material and final parent guide was read directly for purpose of
the material kind, stage fit, meaningful executable steps, learner choices, parent scaffolding versus
answer substitution, unsupported book/household/child assumptions, prediction/visit chronology,
quantitative consistency, actual English expressions/meanings/grammar, feasibility and concrete safety.
`parent_reviewable` means the synthetic artifact can be considered through the required parent-review
workflow under its recorded conditions. It does not mean approved, independently certified, universally
accurate or suitable for a real child without a parent's review. Editorial notes and limitations are
retained for otherwise usable drafts; `needs_minor_revision` is separate from an unqualified pass.

| Stage/kind | Actual source | Measured calls | Mean (min–max), seconds | v7 replay outcome |
| --- | --- | --- | --- | --- |
| elementary / reading_activity | v4-partial | 3 | 165.763 (112.502–199.232) | 3 llm_enhanced |
| elementary / english_card | v4-partial | 3 | 173.496 (123.821–211.696) | 3 llm_enhanced |
| elementary / math_activity | v4-partial | 3 | 171.698 (128.143–211.870) | 3 llm_enhanced |
| elementary / writing_prompt | v4-partial | 3 | 154.923 (96.059–207.266) | 3 llm_enhanced |
| elementary / field_trip | v4-partial | 3 | 150.053 (116.522–190.127) | 3 llm_enhanced |
| infant_0_2 / reading_activity | v5-targeted | 3 | 80.439 (76.154–87.124) | 3 llm_enhanced |
| elementary / science_inquiry | v6-targeted | 3 | 77.415 (69.033–82.393) | 1 template_quality_fallback, 2 llm_enhanced |
| infant_0_2 / activity_guide | v6-targeted | 3 | 58.104 (56.810–59.960) | 1 template_safety_fallback, 2 llm_enhanced |

## Reproduction

For elementary science use the canonical production benchmark with the exact effective profile above:

```bash
uv run python scripts/benchmark_model.py --stage elementary --kind science_inquiry --warmup-rounds 1 --repeats 3
```

Enable local LLM and set the model/profile through the existing Settings/environment configuration;
the command alone does not select the model or enable features. For the infant cases use the same
background provider and `MaterialGenerationService`, creating a synthetic `ChildProfile` with
`stage=Stage.INFANT_0_2, age_months=9` and the two explicit topics above. Run one warmup and then three
measured rounds. The JSON records the exact system/user prompts, response schema, profile and source
hashes needed to reproduce individual requests. The local diagnostic wrapper and full intermediate
files were retained under temporary experiment directories for the coordinator; those paths contain
only synthetic state and are not product storage locations.

Model weights are not redistributed. The previously recorded model-card/license and memory caveats
still apply. Automatic RAM-based model selection remains a starting configuration, not an educational
quality recommendation. This observation does not justify making Gemma 12B the default for every
16 GB device or weakening safety/quality checks for smaller models.

## Host memory, cleanup and artifact identity

Across sampled concurrent-validation runs, host-wide wired memory reached 12.66 GiB and
compressor occupancy reached 3.28 GiB; these maxima may occur at different times.
Ollama reported about 7.65 GB resident allocation for the selected model/context. This is tight on
16 GB hardware and is not model-only RSS, a memory leak test or a certified peak measurement.
Both completed v5/v6 runs verified `/api/ps` empty after unloading the experiment-owned model.
Earlier pilot/partial-run CLI exit flags alone are explicitly not promoted to proof of unload.

JSON SHA-256: `06012e1f4866cec8e819dcf6b953f345313b6eb6bb14a0e9b3ea239f29abbe36`.

There are 51 completed inference artifacts: three v3 pilot warmups, 28 v4 partial-run calls,
12 v5 targeted calls and eight v6 targeted calls. The interrupted v3 fourth request and unstarted
v4 remaining infant calls are not counted as completed samples. No v7 inference was performed.
