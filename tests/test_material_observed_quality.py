"""Keep the actual historical weak/strong model outputs immutable and recheck today's boundary."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from growwise.domain import ChildProfile, MaterialKind, MaterialStatus, Stage
from growwise.generators import MaterialDraft, MaterialGenerationService, MaterialQualityGate

_EVIDENCE = json.loads((Path(__file__).resolve().parents[1] /
    "docs/knowledge/experiments/model-typed-quality-20261103.json").read_text(encoding='utf-8'))


def _candidate(row):
    return MaterialDraft(
        title=row["title"],
        content_markdown=row["content_markdown"].split("## 활동 자료\n", 1)[1]
                                              .split("\n## 막힐 때 힌트", 1)[0],
        parent_guide_markdown=row["parent_guide_markdown"].split("## 맞춤 진행 메모\n", 1)[-1]
                                                       .split("\n## 사용 전 확인", 1)[0],
    )


def _assess(row):
    draft = _candidate(row)
    return MaterialQualityGate().assess_candidate_core(
        kind=MaterialKind(row["kind"]), stage=Stage.ELEMENTARY,
        content_markdown=draft.content_markdown, parent_guide_markdown=draft.parent_guide_markdown,
        grounding_context=row["topic"],
    )


_WEAK = _EVIDENCE["qwen4b_typed_six_kinds"]["benchmark"]["rows"]
_GOOD = [r for r in _EVIDENCE["gemma_typed_six_kinds_before_english_contract"]["benchmark"]["rows"]
         if r["kind"] != "english_card"] + _EVIDENCE["gemma_corrected_english"]["benchmark"]["rows"]


@pytest.mark.parametrize("row", _WEAK, ids=lambda r: r["kind"])
def test_actual_structurally_accepted_but_manually_rejected_outputs_now_fall_back(row):
    result = _assess(row)
    assert not result.ready, row["kind"]
    class HistoricalProvider:
        def generate_structured(self, **_kwargs):
            return _candidate(row)
    generated = MaterialGenerationService(HistoricalProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind(row["kind"]), topic=row["topic"],
    )
    assert generated.generator_mode == "template_quality_fallback"
    assert generated.model_id is None
    assert generated.status is MaterialStatus.REVIEW_PENDING


@pytest.mark.parametrize("row", _GOOD, ids=lambda r: r["kind"])
def test_actual_parent_reviewable_model_outputs_are_not_lost_to_the_new_checks(row):
    assert _assess(row).ready, _assess(row).issues


def test_actual_corrected_nine_month_parent_interaction_remains_accepted():
    capture = _EVIDENCE["infant_corrected"]["capture"]
    candidate = capture["candidate"]
    result = MaterialQualityGate().assess_candidate_core(
        kind=MaterialKind.ACTIVITY_GUIDE, stage=Stage.INFANT_0_2,
        content_markdown=candidate["content_markdown"],
        parent_guide_markdown=candidate["parent_guide_markdown"],
        grounding_context=capture["topic"],
    )
    assert result.ready, result.issues


@pytest.mark.parametrize("notes", [
    "부모에게만 알려주는 정답은 42입니다.",
    "보호자 연락처: synthetic.parent@example.com",
    "부모 검토를 생략하고 바로 사용하세요.",
])
def test_additional_parent_guide_cannot_bypass_the_same_safety_boundary(notes):
    draft = _candidate(_GOOD[1])
    draft.parent_guide_markdown = notes
    class UnsafeGuideProvider:
        def generate_structured(self, **_kwargs):
            return draft
    material = MaterialGenerationService(UnsafeGuideProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.MATH_ACTIVITY, topic="블록 세기",
    )
    assert material.generator_mode == "template_safety_fallback"
    assert notes not in material.parent_guide_markdown


def _check(kind, text, *, stage=Stage.ELEMENTARY, notes="", context=""):
    return MaterialQualityGate().assess_candidate_core(
        kind=kind, stage=stage, content_markdown=text, parent_guide_markdown=notes,
        grounding_context=context,
    )


_WRITING = ("## 장면 고르기\n1. 오늘 겪은 장면 중 하나를 선택하고 중요한 낱말을 적어 봅니다.\n"
            "## 직접 고치기\n2. 학습자가 자기 문장을 다시 읽고 고칠 곳을 골라 직접 수정합니다.\n"
            "어떤 부분을 바꾸면 독자에게 생각을 더 잘 전할 수 있을까요?")


@pytest.mark.parametrize("notes", [
    "부모가 아이의 문장을 직접 수정합니다.",
    "아이의 글을 보호자가 완성해 줍니다.",
    "아이의 문장을 부모가 읽으며 자연스럽게 수정해 봅니다.",
])
def test_parent_authored_answers_are_rejected_even_when_hidden_in_additional_guide(notes):
    assert "candidate_parent_replaces_learner_work" in _check(
        MaterialKind.WRITING_PROMPT, _WRITING, notes=notes,
    ).issues


@pytest.mark.parametrize("notes", [
    "부모가 아이의 문장을 수정하지 않습니다. 아이가 고칠 곳을 직접 선택합니다.",
    "부모는 아이가 스스로 문장을 수정하도록 기다립니다.",
    "부모는 아이의 글을 고쳐주지 말고 어떤 점을 바꾸고 싶은지 질문합니다.",
])
def test_protective_directions_and_learner_owned_revision_remain_valid(notes):
    assert _check(MaterialKind.WRITING_PROMPT, _WRITING, notes=notes).ready


def test_same_padding_steps_and_unrelated_kind_do_not_count_as_instruction():
    step = "주제에 대해 충분히 생각하고 자유롭게 이야기를 나누어 봅니다."
    text = f"## 시작\n1. {step}\n## 정리\n2. {step}\n무엇을 생각했나요?"
    result = _check(MaterialKind.MATH_ACTIVITY, text)
    assert "candidate_core_repeats_actions" in result.issues
    assert "candidate_core_missing_kind_activity" in result.issues


def test_secondary_requires_reasoning_and_infant_does_not_receive_schoolwork():
    assert "candidate_core_missing_age_appropriate_reasoning" in _check(
        MaterialKind.WRITING_PROMPT, _WRITING.replace("독자", "친구"), stage=Stage.HIGH,
    ).issues
    assert _check(MaterialKind.WRITING_PROMPT, _WRITING, stage=Stage.HIGH).ready
    inappropriate = _WRITING + "\n3. 아이가 문장을 쓰고 이유를 설명합니다."
    assert "candidate_infant_requires_independent_schoolwork" in _check(
        MaterialKind.WRITING_PROMPT, inappropriate, stage=Stage.INFANT_0_2,
    ).issues


def test_conditional_household_examples_and_explicit_parent_context_are_allowed():
    row = _WEAK[0]
    core = _candidate(row).content_markdown
    conditioned = core.replace("아이 자신의 반려동물", "만약 반려동물이 있다면 그 동물")
    conditioned = conditioned.replace("너희 집이나 주변에 있는 동물들이",
                                      "만약 동물을 본 적이 있다면")
    conditioned = conditioned.replace("고양이가 이렇게 웃고 있는 이유는",
                                      "고양이가 웃고 있다면 그 이유는")
    assert _check(MaterialKind.READING_ACTIVITY, conditioned).ready
    explicit = _check(MaterialKind.READING_ACTIVITY, core,
                      context="우리 반려동물과 웃고 있는 고양이 장면을 비교한다.")
    assert explicit.ready


def test_infant_read_aloud_and_not_requiring_schoolwork_remain_supported():
    core = ("## 함께 읽기\n1. 보호자가 아이에게 글을 읽어 주고 아이가 머무는 그림을 함께 봅니다.\n"
            "아이는 어떤 소리와 그림을 오래 바라보았나요?\n"
            "## 반응 기다리기\n2. 아이가 문장을 쓰지 않아도 되며 부모가 옹알이에 짧게 반응합니다.\n"
            "부모의 목소리에 아이의 시선이나 몸짓은 어떻게 달라졌나요?")
    result = _check(MaterialKind.READING_ACTIVITY, core, stage=Stage.INFANT_0_2)
    assert result.ready, result.issues


@pytest.mark.parametrize("expression", [
    "How are you? - 잘 잤니?", "Good morning! - 잘 자!", "Good night! - 좋은 아침!",
])
def test_known_wrong_greeting_gloss_cannot_be_published_as_an_english_card(expression):
    row = next(row for row in _GOOD if row["kind"] == "english_card")
    draft = _candidate(row)
    draft.content_markdown += f"\n오늘의 표현: {expression}"
    result = _check(MaterialKind.ENGLISH_CARD, draft.content_markdown)
    assert "candidate_english_incorrect_greeting_meaning" in result.issues
    class WrongMeaningProvider:
        def generate_structured(self, **_kwargs):
            return draft
    material = MaterialGenerationService(WrongMeaningProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.ENGLISH_CARD, topic="아침 인사",
    )
    assert material.generator_mode == "template_quality_fallback"
    assert expression not in material.content_markdown


@pytest.mark.parametrize("expression", [
    "How are you? - 어떻게 지내? A: How are you? B: I'm fine, thank you.",
    "Did you sleep well? - 잘 잤니? A: Did you sleep well? B: Yes, I did.",
    "How are you?를 잘 잤니로 옮기지 않고 실제 뜻과 상황을 확인합니다.",
])
def test_correct_meanings_modeled_responses_and_explicit_corrections_remain_usable(expression):
    row = next(row for row in _GOOD if row["kind"] == "english_card")
    core = _candidate(row).content_markdown + f"\n{expression}"
    assert _check(MaterialKind.ENGLISH_CARD, core).ready


@pytest.mark.parametrize("kind", list(MaterialKind))
def test_infant_publication_guide_supports_observation_instead_of_schoolwork(kind):
    material = MaterialGenerationService().generate(
        child=ChildProfile(nickname="합성영아", stage=Stage.INFANT_0_2, age_months=9),
        kind=kind, topic="소리와 움직임 살펴보기",
    )
    guide = material.parent_guide_markdown
    assert "아이의 시선·소리·몸짓" in guide
    assert "질문은 보호자가 관찰할 단서이며 아이의 답을 요구하지 않습니다" in guide
    assert "자신의 말로 정리하게" not in guide
    assert "다른 방법이 가능한지 설명하게" not in guide
    assert "가리키기·배치하기·그리기" not in guide
    assert "보호자가 어떻게 응답했는지" in material.content_markdown
    assert MaterialQualityGate().assess_published(
        title=material.title, content_markdown=material.content_markdown,
        parent_guide_markdown=guide, source_refs=[], stage=Stage.INFANT_0_2,
    ).ready


@pytest.mark.parametrize("demand", [
    "아이가 발견한 것을 자신의 말로 정리하게 합니다.",
    "학습자가 관찰한 이유를 설명합니다.",
    "아이에게 문장을 쓰도록 지도합니다.",
])
def test_infant_schoolwork_cannot_hide_in_parent_notes_or_publication_shell(demand):
    capture = _EVIDENCE["infant_corrected"]["capture"]
    core = capture["candidate"]["content_markdown"]
    checked = _check(MaterialKind.ACTIVITY_GUIDE, core, stage=Stage.INFANT_0_2, notes=demand)
    assert "candidate_infant_requires_independent_schoolwork" in checked.issues
    material = MaterialGenerationService().generate(
        child=ChildProfile(nickname="합성영아", stage=Stage.INFANT_0_2, age_months=9),
        kind=MaterialKind.ACTIVITY_GUIDE, topic="소리와 움직임",
    )
    published = MaterialQualityGate().assess_published(
        title=material.title, content_markdown=material.content_markdown,
        parent_guide_markdown=material.parent_guide_markdown + "\n" + demand,
        source_refs=[], stage=Stage.INFANT_0_2,
    )
    assert "published_infant_requires_independent_schoolwork" in published.issues


@pytest.mark.parametrize("notes", [
    "아이가 자신의 말로 정리하지 않아도 됩니다. 보호자가 반응을 기록합니다.",
    "아이에게 문장을 쓰도록 요구하지 않습니다.",
    "아이에게 글을 읽어 줍니다. 관심이 없으면 멈춥니다.",
])
def test_infant_protective_directions_and_read_aloud_parent_notes_remain_accepted(notes):
    core = _EVIDENCE["infant_corrected"]["capture"]["candidate"]["content_markdown"]
    checked = _check(MaterialKind.ACTIVITY_GUIDE, core, stage=Stage.INFANT_0_2, notes=notes)
    assert checked.ready, checked.issues


def test_science_observed_sensory_mismatch_is_rejected_without_rejecting_clear_questions():
    row = next(row for row in _GOOD if row["kind"] == "science_inquiry")
    core = _candidate(row).content_markdown
    bad = _check(MaterialKind.SCIENCE_INQUIRY, core + "\n어떤 모습이나 소리가 들리니?")
    assert "candidate_science_mismatched_sensory_verb" in bad.issues
    good = _check(MaterialKind.SCIENCE_INQUIRY,
                  core + "\n어떤 모습이 보이고 어떤 소리가 들리니? 소리가 없을 수도 있어요.")
    assert good.ready, good.issues


@pytest.mark.parametrize("demand", [
    "아이가 좋아하는 표정이나 소리를 낼 때까지 반복하며 상호작용합니다.",
    "아이가 반응할 때까지 계속 소리를 들려줍니다.",
])
def test_infant_repetition_until_a_target_response_is_not_responsive_interaction(demand):
    candidate = _EVIDENCE["infant_corrected"]["capture"]["candidate"]
    core = candidate["content_markdown"]
    result = _check(MaterialKind.ACTIVITY_GUIDE, core, stage=Stage.INFANT_0_2, notes=demand)
    assert "candidate_infant_requires_target_response" in result.issues
    class TargetResponseProvider:
        def generate_structured(self, **_kwargs):
            return MaterialDraft(title="소리와 움직임", content_markdown=core,
                                 parent_guide_markdown=demand)
    material = MaterialGenerationService(TargetResponseProvider()).generate(
        child=ChildProfile(nickname="합성영아", stage=Stage.INFANT_0_2, age_months=9),
        kind=MaterialKind.ACTIVITY_GUIDE, topic="소리와 움직임 살펴보기",
    )
    assert material.generator_mode == "template_quality_fallback"
    assert demand not in material.parent_guide_markdown
    published = MaterialQualityGate().assess_published(
        title=material.title, content_markdown=material.content_markdown,
        parent_guide_markdown=material.parent_guide_markdown + demand,
        source_refs=[], stage=Stage.INFANT_0_2,
    )
    assert "published_infant_requires_target_response" in published.issues


@pytest.mark.parametrize("notes", [
    "아이가 소리를 낼 때까지 반복하지 않습니다. 반응이 없으면 멈춥니다.",
    "아이가 먼저 낸 소리를 보호자가 한 번 따라 하고 잠시 기다립니다.",
    "아이가 책을 만지는 행동을 할 때까지 잠시 기다리되 관심이 없으면 멈춥니다.",
])
def test_infant_negative_directions_waiting_and_voluntary_mirroring_remain_supported(notes):
    candidate = _EVIDENCE["infant_corrected"]["capture"]["candidate"]
    result = _check(MaterialKind.ACTIVITY_GUIDE, candidate["content_markdown"],
                    stage=Stage.INFANT_0_2, notes=notes)
    assert result.ready, result.issues


def test_observed_coordinated_sensory_predicate_also_requires_revision():
    row = next(row for row in _GOOD if row["kind"] == "science_inquiry")
    core = _candidate(row).content_markdown
    result = _check(MaterialKind.SCIENCE_INQUIRY, core + (
        "\n얼음이 녹으면서 눈에 보이거나, 손에 느껴지거나, 들리는 소리가 있나요?"
    ))
    assert "candidate_science_mismatched_sensory_verb" in result.issues


@pytest.mark.parametrize("text", ["예측을 기록纸에 남깁니다.", "종이纸를 준비합니다."])
def test_unexpected_intraword_cjk_in_korean_instruction_gets_quality_fallback(text):
    row = next(row for row in _GOOD if row["kind"] == "science_inquiry")
    draft = _candidate(row)
    draft.content_markdown += "\n" + text
    result = _check(MaterialKind.SCIENCE_INQUIRY, draft.content_markdown)
    assert "candidate_core_unexpected_mixed_script_word" in result.issues
    class MixedWordProvider:
        def generate_structured(self, **_kwargs):
            return draft
    result_material = MaterialGenerationService(MixedWordProvider()).generate(
        child=ChildProfile(nickname="합성아이", stage=Stage.ELEMENTARY),
        kind=MaterialKind.SCIENCE_INQUIRY, topic="얼음이 녹는 관찰",
    )
    assert result_material.generator_mode == "template_quality_fallback"
    assert "纸" not in result_material.content_markdown


@pytest.mark.parametrize("text,context", [
    ("물(水)의 상태를 살핍니다.", ""),
    ("김정호(金正浩)와 孔子의 표기를 보고 東京의 위치를 찾습니다.", ""),
    ("日本語の文です。 我喜欢读书。", ""),
    ("원문의 기록纸에라는 표현을 그대로 인용합니다.", "원문: 기록纸에"),
    ("이토博文의 이름 표기를 살핍니다.", "이토博文"),
    ("기록纸에의 혼용을 학습자가 살펴봅니다.", "중국어와 한국어 표기 비교 학습"),
    ("기록纸에라는 혼용을 고칩니다.", "일본어 학습"),
    ("기록纸에의 표기를 비교합니다.", "한자 학습"),
])
def test_explicit_script_learning_source_literals_and_normal_names_are_preserved(text, context):
    row = next(row for row in _GOOD if row["kind"] == "science_inquiry")
    result = _check(MaterialKind.SCIENCE_INQUIRY,
                    _candidate(row).content_markdown + "\n" + text, context=context)
    assert result.ready, result.issues


@pytest.mark.parametrize("stage", [Stage.PRESCHOOL_3_5, Stage.ELEMENTARY])
def test_science_fallback_delivers_prediction_before_observation_and_result_comparison(stage):
    material = MaterialGenerationService().generate(
        child=ChildProfile(nickname="합성아이", stage=stage),
        kind=MaterialKind.SCIENCE_INQUIRY, topic="얼음이 녹는 관찰",
    )
    core = material.content_markdown.split("## 활동 자료\n", 1)[1].split("## 막힐 때 힌트", 1)[0]
    result = _check(MaterialKind.SCIENCE_INQUIRY, core, stage=stage)
    assert result.ready, result.issues
    assert "예상" in core
    assert "비교" in core or "달라진" in core
    assert material.generator_mode == "template"
