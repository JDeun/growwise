import { describe, expect, it } from "vitest";

import type { MaterialKind, Stage } from "./api";
import { MATERIAL_CATALOG, materialCatalogForStage, materialCatalogItem } from "./material-catalog";

const ALL_KINDS: MaterialKind[] = ["activity_guide", "reading_activity", "english_card", "math_activity", "science_inquiry", "writing_prompt", "field_trip"];
const ALL_STAGES: Stage[] = ["infant_0_2", "preschool_3_5", "elementary", "middle", "high"];

describe("material catalog", () => {
  it("defines every IPC material kind exactly once", () => {
    expect(MATERIAL_CATALOG.map((item) => item.kind)).toEqual(ALL_KINDS);
    expect(new Set(MATERIAL_CATALOG.map((item) => item.kind)).size).toBe(ALL_KINDS.length);
  });

  it("keeps infant choices parent-led and developmentally bounded", () => {
    expect(materialCatalogForStage("infant_0_2").map((item) => item.kind)).toEqual([
      "activity_guide", "reading_activity", "english_card",
    ]);
  });

  it.each(ALL_STAGES.filter((stage) => stage !== "infant_0_2"))("exposes the full deterministic catalog for %s", (stage) => {
    expect(materialCatalogForStage(stage).map((item) => item.kind)).toEqual(ALL_KINDS);
  });

  it.each(ALL_KINDS)("provides actionable copy for %s", (kind) => {
    const item = materialCatalogItem(kind);
    expect(item.label.trim().length).toBeGreaterThan(0);
    expect(item.description.trim().length).toBeGreaterThan(10);
    expect(item.placeholder).toMatch(/^예:/);
  });
});
