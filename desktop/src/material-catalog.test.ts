import { describe, expect, it } from "vitest";

import type { MaterialKind, Stage } from "./api";
import { MATERIAL_CATALOG, materialCatalogForStage, materialCatalogItem } from "./material-catalog";

const ALL_KINDS: MaterialKind[] = [
  "activity_guide",
  "reading_activity",
  "english_card",
  "math_activity",
  "science_inquiry",
  "writing_prompt",
  "field_trip",
];
const ALL_STAGES: Stage[] = ["infant_0_2", "preschool_3_5", "elementary", "middle", "high"];

describe("material catalog", () => {
  it("defines every IPC material kind exactly once", () => {
    expect(MATERIAL_CATALOG.map((item) => item.kind)).toEqual(ALL_KINDS);
    expect(new Set(MATERIAL_CATALOG.map((item) => item.kind)).size).toBe(ALL_KINDS.length);
  });

  it.each(ALL_STAGES)("exposes every deterministic material kind for %s", (stage) => {
    expect(materialCatalogForStage(stage).map((item) => item.kind)).toEqual(ALL_KINDS);
  });

  it("presents infant kinds as parent-led play and observation rather than worksheets", () => {
    const infantCatalog = materialCatalogForStage("infant_0_2");
    const byKind = Object.fromEntries(infantCatalog.map((item) => [item.kind, item]));

    expect(byKind.math_activity.label).toBe("수·크기 감각 놀이");
    expect(byKind.science_inquiry.label).toBe("감각 탐색");
    expect(byKind.writing_prompt.label).toBe("끼적이기·소리 표현");
    expect(byKind.field_trip.label).toBe("짧은 나들이 기록");
    expect(infantCatalog.every((item) => item.flow.includes("부모 메모"))).toBe(true);
    expect(infantCatalog.map((item) => item.description).join(" ")).not.toContain("정답형");
  });

  it.each(ALL_KINDS)("provides actionable product guidance for %s", (kind) => {
    const item = materialCatalogItem(kind);
    expect(item.label.trim().length).toBeGreaterThan(0);
    expect(item.description.trim().length).toBeGreaterThan(10);
    expect(item.placeholder).toMatch(/^예:/);
    expect(item.goalPlaceholder).toMatch(/^예:/);
    expect(item.flow.length).toBeGreaterThanOrEqual(4);
    expect(item.reviewPoints.length).toBeGreaterThanOrEqual(2);
  });

  it("uses distinct workflows for reading, math, science, and field trips", () => {
    expect(materialCatalogItem("reading_activity").flow).toContain("함께 읽으며 질문");
    expect(materialCatalogItem("math_activity").flow).toContain("실물로 탐색");
    expect(materialCatalogItem("science_inquiry").flow).toContain("관찰·실험");
    expect(materialCatalogItem("field_trip").flow).toContain("현장 관찰");
  });
});
