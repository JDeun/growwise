from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.domain import ChildProfile, GeneratedMaterial, MaterialKind, MaterialStatus
from growwise.model import ModelProvider


class MaterialDraft(BaseModel):
    title: str
    content_markdown: str
    source_refs: list[str] = Field(default_factory=list)


_FORBIDDEN_DRAFT_MARKERS = (
    "adhd",
    "autism",
    "autistic",
    "disorder",
    "diagnos",
    "자폐",
    "발달장애",
    "진단",
    "비정상",
    "정상 발달",
    "또래보다",
    "또래 평균",
    "상위 ",
    "하위 ",
    "퍼센타일",
)


def _unsafe_draft(draft: MaterialDraft) -> bool:
    text = f"{draft.title}\n{draft.content_markdown}".casefold()
    return any(marker in text for marker in _FORBIDDEN_DRAFT_MARKERS)


class MaterialGenerationService:
    """Generate parent-reviewable materials with deterministic template fallback."""

    SYSTEM = """Create a concise GrowWise learning material for a parent to review.
Respect the supplied child stage and request. Do not diagnose development, compare with peers,
or make unsupported factual claims. Preserve source references exactly when supplied.
The material is a draft for parent review, not an automatically approved child-facing artifact.
Return Markdown content in the requested structured schema."""

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider

    def generate(
        self,
        *,
        child: ChildProfile,
        kind: MaterialKind,
        topic: str,
        goal: str | None = None,
        source_refs: list[str] | None = None,
    ) -> GeneratedMaterial:
        refs = list(source_refs or [])
        fallback = self._template(
            child=child,
            kind=kind,
            topic=topic,
            goal=goal,
            source_refs=refs,
        )
        draft = fallback
        generator_mode = "template"

        if self.provider is not None:
            try:
                candidate = self.provider.generate_structured(
                    system=self.SYSTEM,
                    user=self._llm_request(
                        child=child,
                        kind=kind,
                        topic=topic,
                        goal=goal,
                        source_refs=refs,
                        fallback=fallback,
                    ),
                    schema=MaterialDraft,
                )
                candidate.source_refs = [ref for ref in candidate.source_refs if ref in refs]
                if refs and not candidate.source_refs:
                    candidate.source_refs = refs
                if _unsafe_draft(candidate):
                    draft = fallback
                    generator_mode = "template_safety_fallback"
                else:
                    draft = candidate
                    generator_mode = "llm_enhanced"
            except Exception:
                draft = fallback
                generator_mode = "template_fallback"

        return GeneratedMaterial(
            child_id=child.id,
            kind=kind,
            title=draft.title,
            content_markdown=draft.content_markdown,
            status=MaterialStatus.REVIEW_PENDING,
            source_refs=draft.source_refs,
            generator_mode=generator_mode,
        )

    def _template(
        self,
        *,
        child: ChildProfile,
        kind: MaterialKind,
        topic: str,
        goal: str | None,
        source_refs: list[str],
    ) -> MaterialDraft:
        goal_text = goal or "주제를 함께 탐색하고 아이의 반응을 관찰한다."
        stage_text = child.stage.value
        title = f"{topic} 활동 가이드"

        if kind is MaterialKind.READING_ACTIVITY:
            content = (
                f"# {title}\n\n"
                f"- 대상 단계: `{stage_text}`\n"
                f"- 목표: {goal_text}\n\n"
                "## 시작 전\n"
                f"- `{topic}`과 관련된 책이나 그림을 하나 준비합니다.\n"
                "- 아이가 관심을 보이는 지점을 먼저 관찰합니다.\n\n"
                "## 함께 하기\n"
                "1. 아이가 바라보거나 손을 뻗는 부분을 따라갑니다.\n"
                "2. 짧은 문장으로 보이는 것을 말해 줍니다.\n"
                "3. 반응이 없으면 정답을 요구하지 않고 다른 페이지로 넘어갑니다.\n\n"
                "## 부모 기록\n"
                "- 무엇에 오래 관심을 보였는지\n"
                "- 어떤 말이나 소리에 반응했는지\n"
                "- 다음에 다시 시도해볼 만한 것이 있는지\n"
            )
        else:
            content = (
                f"# {title}\n\n"
                f"- 대상 단계: `{stage_text}`\n"
                f"- 목표: {goal_text}\n\n"
                "## 준비\n"
                f"- `{topic}`과 연결된 안전한 재료나 자료를 준비합니다.\n\n"
                "## 활동\n"
                "1. 부모가 먼저 짧게 보여줍니다.\n"
                "2. 아이가 스스로 탐색할 시간을 둡니다.\n"
                "3. 반응에 맞춰 활동을 줄이거나 확장합니다.\n\n"
                "## 관찰\n"
                "- 관심을 보인 대상\n"
                "- 반복한 행동이나 질문\n"
                "- 다음 활동과 연결할 수 있는 단서\n"
            )

        if source_refs:
            content += "\n## 참고 자료\n" + "\n".join(f"- `{ref}`" for ref in source_refs) + "\n"

        return MaterialDraft(
            title=title,
            content_markdown=content,
            source_refs=source_refs,
        )

    @staticmethod
    def _llm_request(
        *,
        child: ChildProfile,
        kind: MaterialKind,
        topic: str,
        goal: str | None,
        source_refs: list[str],
        fallback: MaterialDraft,
    ) -> str:
        return (
            f"Child stage: {child.stage.value}\n"
            f"Age months: {child.age_months}\n"
            f"Interests: {', '.join(child.interests)}\n"
            f"Material kind: {kind.value}\n"
            f"Topic: {topic}\n"
            f"Goal: {goal or ''}\n"
            f"Allowed source refs: {source_refs}\n\n"
            f"Deterministic fallback draft:\n{fallback.content_markdown}"
        )
