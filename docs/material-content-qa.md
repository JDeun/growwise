# Material content QA and pedagogical release gate

GrowWise treats "commercial quality" as two separate claims:

1. **Product-system quality** — generation, review, versioning, provenance, safety, print/PDF, and fallback behavior are reliable.
2. **Content quality** — the generated activity is developmentally appropriate, executable, useful to a parent, appropriately rigorous for the learner's stage, and honest about evidence.

The first claim is covered by the normal test suite. This document defines the second claim and the remaining evidence required before making stronger field-effectiveness claims.

## September 2026 adversarial editorial audit

The audit re-read the deterministic fallback templates, publication shell, parent guide, curriculum mapping, quality gate, and 140-case golden corpus as actual educational content rather than only as software contracts.

### Material issue found

The previous deterministic body library had a dedicated infant pool, but preschool, elementary, middle, and high-school stages drew from the same general activity pool. Stage labels, duration, and curriculum metadata differed, but the central task could still be materially similar. This created two editorial risks:

- a 3-5-year-old could receive a body that implicitly expected conventional writing or school-like explanation;
- a middle/high-school learner could receive a task whose cognitive demand and parent involvement read like an elementary activity.

That was structurally valid but not sufficient evidence for stage-appropriate commercial content.

### Remediation

The deterministic pipeline now has four distinct body pools:

- **0-2:** sensory play, co-regulation, observation, no performance pressure;
- **3-5:** child-led play, oral/gesture/drawing expression, no required conventional reading/writing;
- **elementary:** concrete experience → representation → explanation;
- **middle/high:** evidence/reasoning-oriented tasks using claims, assumptions, variables, sources, alternative interpretations, limitations, revision, and independent planning.

Middle and high school share a secondary body pool but receive different publication-level instructional contracts. Middle school emphasizes increasing independence and comparison of evidence. High school explicitly adds source/assumption checking, counterexamples or alternative interpretations, limitations, and next-validation design.

Every published material now includes:

- `## 단계별 활동 기준`
- `## 단계별 진행 기준` in the parent guide

Those sections are part of the deterministic quality gate, so an enhanced model cannot silently remove the developmental contract.

## Editorial rubric

A release sample is reviewed against all dimensions below. A serious failure in safety, stage fit, factual grounding, or executability is a release blocker even when the other dimensions are strong.

| Dimension | Pass condition |
| --- | --- |
| Stage fit | language, task demand, representation, independence, and parent role match the stage |
| Goal-task alignment | the activity actually practices the stated public goal |
| Executability | steps can be performed with the listed materials and within a plausible session |
| Learner agency | the learner observes, chooses, reasons, creates, or explains rather than copying an answer |
| Scaffolding | help moves from open prompt → narrowed cue → concrete support without giving the final answer |
| Parent usability | a parent can prepare, facilitate, simplify/deepen, stop safely, and record useful evidence |
| Evidence/factuality | factual claims are grounded when sources are selected; unsupported certainty is avoided |
| Safety | age, material, allergy, travel, experiment, and stop conditions are explicit where relevant |
| Editorial quality | no placeholders, internal metadata, contradictory directions, or obviously childish/over-advanced framing |
| Reflection/transfer | the material closes with reflection and a bounded extension rather than endless task volume |

## Automated editorial regression coverage

The codebase now checks all **35 Stage × MaterialKind families** for a stage-specific instructional contract. It also verifies that a single topic does not collapse to the same publication across stages, that preschool writing is expression-first, that secondary science requires evidence/reasoning/limitation awareness, and that the publication quality gate rejects a document whose stage contract was removed.

This complements, rather than replaces, the existing **140-case** Stage × MaterialKind × topic golden corpus. The 140-case corpus protects publication completeness and safety; the editorial suite protects developmental differentiation.

## Curriculum basis

GrowWise continues to use copyright-safe paraphrased alignment rather than copying official achievement standards:

- 2024 revised Standard Childcare Curriculum for ages 0-2;
- 2019 revised Nuri Curriculum for ages 3-5;
- 2015/2022 revised national elementary/middle/high curricula selected by grade and date,
  including the 2024 and 2026 partial amendments when their grade-specific effective dates apply.

The preschool implementation deliberately preserves child-led, play-centered activity rather than turning curriculum alignment into teacher-directed worksheets. School-stage materials increase representation, reasoning, evidence use, and learner independence instead of merely changing the stage label.

## What this validation can and cannot establish

Repository review and automated tests can establish that generated artifacts have the intended instructional structure, developmental differentiation, safety rails, source boundaries, review workflow, and fallback behavior.

They **cannot** establish by themselves:

- actual child/teen engagement;
- measured completion time in a household;
- learning gains;
- accessibility for every learner;
- teacher consensus on every generated topic;
- factual correctness of arbitrary future model-generated claims without appropriate source review.

Before a public claim such as "teacher-validated" or "proven to improve learning," GrowWise still needs real field evidence. A practical release validation set is 30-50 approved outputs sampled across stages and material kinds, followed by household use and, if that marketing claim is desired, review by qualified educators.

Until then, the defensible product claim is:

> GrowWise provides a commercially structured, stage-differentiated educational-material generation and parent-review system with deterministic fallbacks and automated editorial safeguards. Actual learner engagement and educational effectiveness remain field-validation questions.
