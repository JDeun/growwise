from __future__ import annotations

from pydantic import BaseModel, Field

from growwise.model import ModelProvider
from growwise.rag import HybridRagIndex
from growwise.storage import SQLiteProjection


class ContextAnswer(BaseModel):
    answer: str
    source_ids: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class ChildContextService:
    SYSTEM = """Answer using only the supplied GrowWise records and resources.
Distinguish direct observations from interpretation. Do not diagnose, rank against peers,
or infer fixed ability or personality. If the evidence is insufficient, say so explicitly.
Use only source IDs included in the context. Return concise Korean for Korean questions."""

    def __init__(
        self,
        *,
        entity_index: SQLiteProjection,
        rag_index: HybridRagIndex,
        provider: ModelProvider | None,
    ) -> None:
        self.entity_index = entity_index
        self.rag_index = rag_index
        self.provider = provider

    def ask(self, *, child_id: str, query: str, limit: int = 8) -> ContextAnswer:
        records = self.entity_index.search_entities(
            child_id=child_id,
            query_text=query,
            entity_types=("learning_log", "activity_plan"),
            limit=limit,
        )
        chunks = self.rag_index.search(query=query, child_id=child_id, limit=limit)

        sources: list[tuple[str, str]] = []
        for record in records:
            source_id = f"record:{record['id']}"
            text = record.get("parent_observation") or record.get("title") or str(record)
            sources.append((source_id, str(text)))
        for chunk in chunks:
            source_id = f"chunk:{chunk['chunk_id']}"
            text = f"{chunk['title']}\n{chunk['text']}"
            sources.append((source_id, text))

        if not sources:
            return ContextAnswer(
                answer="관련 기록이나 자료를 찾지 못했습니다.",
                insufficient_evidence=True,
            )

        if self.provider is None:
            return ContextAnswer(
                answer=f"관련 기록과 자료 {len(sources)}건을 찾았습니다.",
                source_ids=[source_id for source_id, _ in sources],
            )

        context = "\n\n".join(f"[{source_id}] {text}" for source_id, text in sources)
        try:
            answer = self.provider.generate_structured(
                system=self.SYSTEM,
                user=f"Question: {query}\n\nContext:\n{context}",
                schema=ContextAnswer,
            )
            allowed = {source_id for source_id, _ in sources}
            answer.source_ids = [
                source_id for source_id in answer.source_ids if source_id in allowed
            ]
            if not answer.source_ids and not answer.insufficient_evidence:
                answer.insufficient_evidence = True
            return answer
        except Exception:
            return ContextAnswer(
                answer="관련 기록과 자료는 찾았지만 답변 생성에 실패했습니다.",
                source_ids=[source_id for source_id, _ in sources],
            )
