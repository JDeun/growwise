from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from growwise.domain import ChildProfile, LearningLog, ResourceKind, ResourceRecord, Stage
from growwise.domain.links import EntityLinkRelation
from growwise.rag import HybridRagIndex
from growwise.services.context import ChildContextService
from growwise.services.entity_links import EntityLinkService
from growwise.storage import EntityStore

T = TypeVar("T", bound=BaseModel)


class CapturingProvider:
    def __init__(self) -> None:
        self.users: list[str] = []

    def generate_text(self, *, system: str, user: str) -> str:
        raise AssertionError("structured context path expected")

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        self.users.append(user)
        return schema(
            answer="근거를 확인했습니다.",
            source_ids=[],
            insufficient_evidence=True,
        )


def test_child_context_prompt_preserves_directional_graph_semantics(tmp_path: Path) -> None:
    store = EntityStore(tmp_path / "records", tmp_path / "index.sqlite3")
    child = ChildProfile(name="아이", nickname="아이", stage=Stage.ELEMENTARY)
    store.save(child)

    result = LearningLog(
        child_id=child.id,
        parent_observation="별자리 활동 결과를 기록했다.",
    )
    source = ResourceRecord(
        child_id=child.id,
        kind=ResourceKind.NOTE,
        title="별자리 활동 원본",
        content="밤하늘 별자리를 관찰하는 활동 자료",
    )
    store.save(result)
    store.save(source)
    EntityLinkService(store).create(
        source_id=result.id,
        target_id=source.id,
        relation=EntityLinkRelation.DERIVED_FROM,
    )

    provider = CapturingProvider()
    service = ChildContextService(
        entity_index=store.index,
        rag_index=HybridRagIndex(tmp_path / "rag.sqlite3", embedding=None),
        provider=provider,
    )

    service.ask(child_id=str(child.id), query="별자리 활동 결과")

    assert len(provider.users) == 1
    prompt = provider.users[0]
    assert "relation=derived_from" in prompt
    assert "direction=outgoing" in prompt
    assert f"source={result.id}" in prompt
    assert f"target={source.id}" in prompt
    assert "별자리 활동 원본" in prompt
