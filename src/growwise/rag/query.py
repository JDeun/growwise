from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.model import ModelProvider

from .index import HybridRagIndex


class GroundedAnswer(BaseModel):
    answer: str
    source_chunk_ids: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class GroundedRagService:
    SYSTEM = """Answer the parent's question using only the supplied GrowWise context.
Do not invent facts. If evidence is insufficient, say so and set insufficient_evidence=true.
Do not diagnose development, rank a child against peers, or infer stable personality traits.
Keep observations and interpretation distinct. Cite source_chunk_ids that directly support the answer.
Return concise Korean when the question is Korean."""

    def __init__(
        self,
        *,
        index: HybridRagIndex,
        provider: ModelProvider | None,
    ) -> None:
        self.index = index
        self.provider = provider

    def ask(self, *, query: str, child_id: str | None, limit: int = 8) -> GroundedAnswer:
        hits = self.index.search(query=query, child_id=child_id, limit=limit)
        if not hits:
            return GroundedAnswer(
                answer="관련 근거를 찾지 못했습니다.",
                insufficient_evidence=True,
            )

        if self.provider is None:
            titles = ", ".join(dict.fromkeys(hit["title"] for hit in hits))
            return GroundedAnswer(
                answer=f"관련 자료를 찾았습니다: {titles}",
                source_chunk_ids=[hit["chunk_id"] for hit in hits],
            )

        context = "\n\n".join(
            f"[{hit['chunk_id']}] {hit['title']}\n{hit['text']}" for hit in hits
        )
        try:
            answer = self.provider.generate_structured(
                system=self.SYSTEM,
                user=f"Question: {query}\n\nContext:\n{context}",
                schema=GroundedAnswer,
            )
            allowed = {hit["chunk_id"] for hit in hits}
            answer.source_chunk_ids = [
                chunk_id for chunk_id in answer.source_chunk_ids if chunk_id in allowed
            ]
            if not answer.source_chunk_ids and not answer.insufficient_evidence:
                answer.insufficient_evidence = True
            return answer
        except Exception:
            return GroundedAnswer(
                answer="관련 자료는 찾았지만 로컬 모델로 답변을 생성하지 못했습니다.",
                source_chunk_ids=[hit["chunk_id"] for hit in hits],
                insufficient_evidence=False,
            )
