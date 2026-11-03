"""Actual reviewed synthetic model cores for tests that need accepted, kind-specific output."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from growwise.domain import MaterialKind
from growwise.generators import MaterialDraft


@lru_cache(maxsize=1)
def _observed_cores() -> dict[str, dict]:
    artifact = json.loads((Path(__file__).resolve().parents[1] /
        "docs/knowledge/experiments/model-typed-quality-20261103.json").read_text(encoding='utf-8'))
    rows = artifact["gemma_typed_six_kinds_before_english_contract"]["benchmark"]["rows"]
    rows += artifact["gemma_corrected_english"]["benchmark"]["rows"]
    cores = {}
    for row in rows:
        cores[row["kind"]] = {
            "title": row["title"],
            "content_markdown": row["content_markdown"].split("## 활동 자료\n", 1)[1]
                                                      .split("\n## 막힐 때 힌트", 1)[0],
            "parent_guide_markdown": row["parent_guide_markdown"]
                .split("## 맞춤 진행 메모\n", 1)[-1].split("\n## 사용 전 확인", 1)[0],
        }
    # The general activity family may use this concrete manipulation/comparison activity too.
    cores[MaterialKind.ACTIVITY_GUIDE.value] = cores[MaterialKind.MATH_ACTIVITY.value]
    return cores


def observed_draft_for_request(user: str) -> MaterialDraft:
    kind = next(kind for kind in MaterialKind if f"Material kind: {kind.value}" in user)
    return MaterialDraft.model_validate(_observed_cores()[kind.value])
