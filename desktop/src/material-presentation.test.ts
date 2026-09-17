import { describe, expect, it } from "vitest";

import type { MaterialKind } from "./api";
import { materialPresentationTemplate } from "./material-presentation";

const KINDS: MaterialKind[] = [
  "activity_guide",
  "reading_activity",
  "english_card",
  "math_activity",
  "science_inquiry",
  "writing_prompt",
  "field_trip",
];

describe("materialPresentationTemplate", () => {
  it("defines a stable printable worksheet contract for every material kind", () => {
    const templates = KINDS.map((kind) => materialPresentationTemplate(kind));

    expect(templates.map((item) => item.kind)).toEqual(KINDS);
    expect(new Set(templates.map((item) => item.layout)).size).toBe(KINDS.length);
    expect(templates.every((item) => item.label.length > 0)).toBe(true);
    expect(templates.every((item) => item.purpose.length > 0)).toBe(true);
    expect(templates.every((item) => item.zones.length === 3)).toBe(true);
  });

  it("uses inquiry-specific writable zones for science materials", () => {
    expect(materialPresentationTemplate("science_inquiry").zones).toEqual([
      "예측",
      "관찰·실험",
      "결과·설명",
    ]);
  });
});
