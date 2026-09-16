import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial, MaterialKind } from "../api";
import { MaterialParentGuide } from "./MaterialParentGuide";

function material(kind: MaterialKind, guide: string | undefined = "## 진행\n천천히 관찰합니다."): GeneratedMaterial {
  return {
    id: "material-1",
    child_id: "child-1",
    kind,
    title: "테스트 자료",
    content_markdown: "# 본문",
    status: "approved",
    source_refs: [],
    generator_mode: "template",
    review_note: null,
    request_topic: "테스트",
    request_goal: null,
    version: 1,
    parent_material_id: null,
    version_note: null,
    curriculum_targets: [],
    parent_guide_markdown: guide,
    ai_status: "not_requested",
    ai_job_id: null,
  };
}

describe("MaterialParentGuide", () => {
  it("renders a kind-specific science worksheet contract for print", () => {
    const html = renderToStaticMarkup(<MaterialParentGuide material={material("science_inquiry")} />);

    expect(html).toContain('data-material-kind="science_inquiry"');
    expect(html).toContain('data-presentation-layout="science"');
    expect(html).toContain("과학 탐구 시트");
    expect(html).toContain("예측");
    expect(html).toContain("관찰·실험");
    expect(html).toContain("결과·설명");
    expect(html).toContain("부모용 교안 · 진행 안내");
    expect(html).toContain("진행 안내");
  });

  it("keeps the printable worksheet even when no parent guide was generated", () => {
    const html = renderToStaticMarkup(<MaterialParentGuide material={material("field_trip", undefined)} />);

    expect(html).toContain("현장학습 기록 시트");
    expect(html).toContain("가기 전 궁금증");
    expect(html).toContain("현장 관찰·사진 메모");
    expect(html).toContain("돌아와서 연결");
    expect(html).not.toContain("부모용 교안 · 진행 안내");
  });
});
