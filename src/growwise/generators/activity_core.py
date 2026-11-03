"""Model response structure; publication and safety remain the material service's responsibility."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

_Step = Annotated[str, Field(min_length=1, max_length=2_000)]
_SourceRef = Annotated[str, Field(min_length=1, max_length=500)]


class ActivitySection(BaseModel):
    heading: str = Field(min_length=1, max_length=160, description="짧고 의미 있는 활동 소제목")
    steps: list[_Step] = Field(
        min_length=1, max_length=6,
        description="실제로 실행할 구체적인 행동. 각 항목은 행동 하나이며 번호와 HTML은 쓰지 않음",
    )
    question: str = Field(
        min_length=1, max_length=1_000,
        description="생각이나 방법의 이유를 묻는 열린 질문. 영아는 보호자의 관찰 질문",
    )


class ActivityCoreDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    sections: list[ActivitySection] = Field(min_length=2, max_length=4)
    parent_guide_markdown: str = Field(
        max_length=12_000, description="학습자 활동과 분리한 추가 부모 진행 도움만",
    )
    source_refs: list[_SourceRef] = Field(max_length=100)

    def render_markdown(self) -> str:
        # Render explicit model-authored sections/actions; never guess structure from arbitrary
        # HTML or add missing educational content to make an inadequate candidate pass the gate.
        return "\n\n".join(
            f"## {section.heading}\n"
            + "\n".join(f"{number}. {step}" for number, step in enumerate(section.steps, 1))
            + f"\n\n{section.question}"
            for section in self.sections
        )
