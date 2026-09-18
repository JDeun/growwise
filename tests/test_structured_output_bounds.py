from __future__ import annotations

import pytest
from pydantic import ValidationError

from growwise.generators.material import MaterialDraft
from growwise.rag.query import GroundedAnswer
from growwise.services.infant import (
    ActivitySuggestion,
    BoardBookRecommendation,
    InfantCurriculumDomain,
    ObservationHint,
)
from growwise.services.observation import ObservationEnrichment


def test_material_draft_generated_output_is_bounded() -> None:
    with pytest.raises(ValidationError):
        MaterialDraft(title="x" * 201, content_markdown="content")
    with pytest.raises(ValidationError):
        MaterialDraft(title="title", content_markdown="x" * 20_001)
    with pytest.raises(ValidationError):
        MaterialDraft(
            title="title",
            content_markdown="content",
            source_refs=["ref"] * 101,
        )
    with pytest.raises(ValidationError):
        MaterialDraft(
            title="title",
            content_markdown="content",
            source_refs=["x" * 501],
        )


def test_observation_enrichment_generated_output_matches_learning_log_bounds() -> None:
    with pytest.raises(ValidationError):
        ObservationEnrichment(tags=["tag"] * 101)
    with pytest.raises(ValidationError):
        ObservationEnrichment(tags=["x" * 201])
    with pytest.raises(ValidationError):
        ObservationEnrichment(interest="x" * 2_001)
    with pytest.raises(ValidationError):
        ObservationEnrichment(difficulty_note="x" * 4_001)


def test_infant_generated_payloads_are_bounded() -> None:
    with pytest.raises(ValidationError):
        ActivitySuggestion(
            title="활동",
            description="설명",
            materials=["도구"] * 21,
        )
    with pytest.raises(ValidationError):
        ActivitySuggestion(
            title="활동",
            description="x" * 4_001,
        )
    with pytest.raises(ValidationError):
        ObservationHint(
            domain=InfantCurriculumDomain.COMMUNICATION,
            cue="x" * 4_001,
            rationale="근거",
        )
    with pytest.raises(ValidationError):
        BoardBookRecommendation(
            title="x" * 501,
            reason="이유",
            read_aloud_tip="팁",
        )


def test_grounded_answer_generated_output_is_bounded() -> None:
    with pytest.raises(ValidationError):
        GroundedAnswer(answer="x" * 20_001)
    with pytest.raises(ValidationError):
        GroundedAnswer(answer="답변", source_chunk_ids=["chunk"] * 101)
    with pytest.raises(ValidationError):
        GroundedAnswer(answer="답변", source_chunk_ids=["x" * 501])
