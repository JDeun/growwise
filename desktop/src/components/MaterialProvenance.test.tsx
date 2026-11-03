import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { GeneratedMaterial } from "../api";
import { MaterialParentGuide } from "./MaterialParentGuide";

const material: GeneratedMaterial = {
  id: "material-a", child_id: "child-a", kind: "activity_guide", title: "부모 활동",
  content_markdown: "## 함께 관찰", parent_guide_markdown: "## 부모 진행\n반응을 기다립니다.",
  status: "archived", source_refs: [], generator_mode: "llm_enhanced", review_note: null,
  request_topic: null, request_goal: null, version: 1, parent_material_id: null, version_note: null,
};

describe("optional material producer and parent-decision provenance", () => {
  it("shows the real model/version and decision time inside existing collapsed guidance", () => {
    const html = renderToStaticMarkup(<MaterialParentGuide stage="infant_0_2" material={{
      ...material, model_provider: "OllamaProvider", model_id: "synthetic:model-a",
      generator_version: "growwise.material.v2", review_decision: "approved",
      reviewed_at: "2026-11-03T01:00:00Z", updated_at: "2040-01-01T00:00:00Z",
    }} />);
    expect(html).toContain("Ollama · synthetic:model-a");
    expect(html).toContain("growwise.material.v2");
    expect(html).toContain("사용 승인");
    expect(html).toContain("부모 결정 시각");
    expect(html).not.toContain("2040");
    expect(html).not.toContain('class="material-parent-guide" open');
    expect(html).not.toContain("material-presentation-template");
  });

  it("does not label fallback or parent edits as authored by a stale AI model", () => {
    for (const mode of ["template_quality_fallback", "parent_edit"]) {
      const html = renderToStaticMarkup(<MaterialParentGuide material={{ ...material,
        generator_mode: mode, model_id: "stale:model", generator_version: "known-version",
      }} />);
      expect(html).not.toContain("stale:model");
      expect(html).not.toContain("AI 보강");
      expect(html).toContain(mode === "parent_edit" ? "부모가 직접 수정" : "기본 활동 구성");
    }
  });

  it("does not infer missing legacy provenance or a review time from updated_at", () => {
    const html = renderToStaticMarkup(<MaterialParentGuide material={{ ...material,
      updated_at: "2040-01-01T00:00:00Z",
    }} />);
    expect(html).not.toContain("자료 생성·검토 정보");
    expect(html).not.toContain("부모 결정 시각");
  });
});
