"""Conservative instructional contract checks, not a score of educational effectiveness."""
from __future__ import annotations

import re

from growwise.domain import MaterialKind, Stage

_STEPS = re.compile(r"(?m)^\s*\d+[.)]\s+(.+)$")
_CONDITIONAL = re.compile(r"만약|예를\s*들어|상상|있다면|있으면|경험이\s*있|없다면")
_KIND_ACTIONS = {
    MaterialKind.READING_ACTIVITY: r"책|읽|장면|문장|인물|이야기|본문|글의|주장",
    MaterialKind.MATH_ACTIVITY: r"세어|세고|개수|같은\s*수|덧셈|뺄셈|곱셈|나눗|계산|분수|비율|각도|"
                                r"크기|모양|패턴|규칙|변수|함수|도형|확률|통계|측정|분류|묶음",
    MaterialKind.SCIENCE_INQUIRY: r"예측|예상|가설|관찰|측정|실험|변인|자료|검증",
    MaterialKind.WRITING_PROMPT: r"글|문장|문단|단어|낱말|이야기|그림|표현|주장|근거",
    MaterialKind.FIELD_TRIP: r"현장|방문|탐방|도착|돌아|가기\s*전|장소|풍경",
}
_ANALYTICAL = re.compile(
    r"근거|가설|변인|변수|가정|검증|반론|대안|목적|독자|어조|격식|출처|한계|오차|비판|모델|전략"
)
_PARENT_AUTHOR = re.compile(
    r"(?:부모(?:님)?|보호자|어머니|아버지)(?:가|는|께서)"
    r"(?P<between>[^.!?\n]{0,60}?)(?:수정|고쳐|완성|작성)(?P<tail>[^.!?\n]{0,25})"
)
_INCORRECT_GREETING_MEANING = re.compile(
    r"(?:how\s+are\s+you\s*\?\s*['\"”’]?\s*[-–—:：=(（]\s*잘\s*잤|"
    r"good\s+morning\s*!?\s*['\"”’]?\s*[-–—:：=(（]\s*잘\s*자|"
    r"good\s+night\s*!?\s*['\"”’]?\s*[-–—:：=(（]\s*좋은\s*아침)", re.IGNORECASE,
)
_INFANT_SCHOOLWORK = re.compile(
    r"(?:아이가|아이에게|학습자가)[^.!?\n]{0,60}?"
    r"(?:문장을\s*쓰|글을\s*읽|혼자\s*수행|정답을\s*말|이유를\s*설명|"
    r"자신의\s*말로\s*정리|다른\s*방법[^.!?\n]{0,25}설명)"
)
_INFANT_TARGET_RESPONSE = re.compile(
    r"(?:아이가|아기는|아이에게)[^.!?\n]{0,55}?"
    r"(?:소리|표정|몸짓|동작|반응)[^.!?\n]{0,25}?"
    r"(?:낼|할|보일|지을|나올)\s*때까지[^.!?\n]{0,15}?(?:반복|계속)"
)


def infant_requires_target_response(text: str) -> bool:
    """Reject stimuli repeated until a target response; preserve responsive mirroring."""
    return any(
        not re.match(r"(?:하지|해\s*주지|해?지)\s*(?:않|말)", text[m.end():m.end() + 20])
        for m in _INFANT_TARGET_RESPONSE.finditer(text)
    )


def infant_requires_schoolwork(text: str) -> bool:
    """Catch explicit performance demands, including parent notes and publication boilerplate.

    Reading aloud *to* a baby and statements declining to require schoolwork remain valid.
    This narrow rule does not attempt to infer every developmental expectation from prose.
    """
    for match in _INFANT_SCHOOLWORK.finditer(text):
        before = text[max(0, text.rfind("\n", 0, match.start())):match.start()]
        tail = text[match.end():match.end() + 35]
        if (match.group().startswith("아이에게")
                and (re.search(r"보호자|부모", before) or "글을" in match.group())
                and re.match(r"어\s*(?:주|줍|줘)", tail)):
            continue
        if not re.match(
            r"(?:어도\s*되|지\s*(?:않|말)|하지\s*(?:않|말)|"
            r"(?:게|도록)\s*(?:요구|강요)하지\s*않)", tail,
        ):
            return True
    return False


def instruction_issues(
    kind: MaterialKind, stage: Stage, text: str, parent_notes: str, grounding_context: str,
) -> list[str]:
    issues: list[str] = []
    steps = _STEPS.findall(text)
    actions = "\n".join(steps)
    distinct = {re.sub(r"\W", "", step).casefold() for step in steps if step.strip()}
    if len(distinct) < 2:
        issues.append("candidate_core_repeats_actions")
    purpose = _KIND_ACTIONS.get(kind)
    if purpose and not re.search(purpose, actions):
        issues.append("candidate_core_missing_kind_activity")
    if stage in {Stage.MIDDLE, Stage.HIGH} and not _ANALYTICAL.search(text):
        issues.append("candidate_core_missing_age_appropriate_reasoning")

    combined = f"{text}\n{parent_notes}"
    # These explicit, known wrong beginner glosses are observable contradictions, not a general
    # translation/grammar checker. Sleep-specific questions remain valid in an actual sleep lesson.
    if kind is MaterialKind.ENGLISH_CARD and _INCORRECT_GREETING_MEANING.search(combined):
        issues.append("candidate_english_incorrect_greeting_meaning")
    if kind is MaterialKind.WRITING_PROMPT:
        for match in _PARENT_AUTHOR.finditer(combined):
            between, tail = match.group("between"), match.group("tail")
            # Korean permits the object before its subject ("아이의 문장을 부모가 수정").
            object_text = combined[max(0, match.start() - 35):match.start()] + between
            if (re.search(r"문장|글|답|과제|결론", object_text)
                    and not re.search(r"스스로|하도록|기다리|기회|아이(?:가|에게)\s*직접", between)
                    and not re.match(r"(?:해\s*)?주?지\s*(?:않|말)|하지\s*(?:않|말)", tail)):
                issues.append("candidate_parent_replaces_learner_work")
                break
    for sentence in re.split(r"[.!?\n]", combined):
        if (re.search(r"(?:부모|보호자)[^.!?\n]{0,60}피드백하지\s*않", sentence)
                and not re.search(r"즉시|성급|정답|맞고|평가|판정", sentence)):
            issues.append("candidate_withholds_all_feedback")
            break

    # Ask for visible evidence before presupposing a book event or household pet. Explicit
    # conditional examples and context actually supplied by the parent remain usable.
    for sentence in re.split(r"[.!?\n]", text):
        if _CONDITIONAL.search(sentence):
            continue
        if (re.search(r"(?:아이\s*자신|아이|가족)의\s*반려동물|너희\s*집[^?\n]{0,12}동물",
                      sentence) and "반려동물" not in grounding_context):
            issues.append("candidate_assumes_household_context")
        if (re.search(r"(?:어머니|아버지|엄마|아빠)가", sentence)
                and not any(role in grounding_context
                            for role in ("어머니", "아버지", "엄마", "아빠"))):
            issues.append("candidate_assigns_unprovided_parent_role")
        if (kind is MaterialKind.READING_ACTIVITY
                and re.search(r"이렇게\s*(?:웃|울|화내|도망|숨|놀라)", sentence)
                and not re.search(r"웃|울|화내|도망|숨|놀라", grounding_context)):
            issues.append("candidate_presupposes_unprovided_scene")

    if kind is MaterialKind.SCIENCE_INQUIRY and stage is not Stage.INFANT_0_2:
        if re.search(
            r"모습(?:이나|과|와|·)\s*소리(?:가|를)?\s*들리|"
            r"보이거나[^?？.!\n]{0,45}느껴지거나[^?？.!\n]{0,45}들리는\s*소리", combined,
        ):
            issues.append("candidate_science_mismatched_sensory_verb")
        prediction = next((i for i, step in enumerate(steps)
                           if re.search(r"예상|예측|가설|미리[^.\n]{0,20}생각|"
                                        r"(?:변할지|될지|일어날지)[^.\n]{0,20}(?:생각|말)", step)),
                          None)
        # Initial inspection is useful; only changing processes/results must follow prediction.
        result_step = next((i for i, step in enumerate(steps)
                            if re.search(r"녹아|녹는|변하는|변화하는|실험\s*결과", step)
                            and re.search(r"관찰|비교|기록|기다리|측정", step)), None)
        if prediction is None:
            issues.append("candidate_science_missing_prediction")
        elif result_step is not None and result_step < prediction:
            issues.append("candidate_science_predicts_after_result")
    if kind is MaterialKind.FIELD_TRIP:
        for section in re.split(r"(?m)^#{1,6}\s+", text):
            heading, _, body = section.partition("\n")
            if re.search(r"(?:가기|방문|탐방).*전|준비", heading):
                for step in _STEPS.findall(body):
                    if (re.search(r"실제[^.\n]{0,35}비교|관찰한[^.\n]{0,25}비교", step)
                            and not re.search(r"나중|뒤|후|하면|때\s*비교|현장에서", step)):
                        issues.append("candidate_field_trip_uses_results_before_visit")
    if stage is Stage.INFANT_0_2 and infant_requires_schoolwork(combined):
        issues.append("candidate_infant_requires_independent_schoolwork")
    if stage is Stage.INFANT_0_2 and infant_requires_target_response(combined):
        issues.append("candidate_infant_requires_target_response")
    return list(dict.fromkeys(issues))
