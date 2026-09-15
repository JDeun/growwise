import { describe, expect, it } from "vitest";
import { MATERIAL_KIND_LABELS } from "../material-workflow";
describe("material kind labels", () => {
  it("avoids raw enum names in parent-facing labels", () => {
    for (const [kind, label] of Object.entries(MATERIAL_KIND_LABELS)) {
      expect(label).not.toBe(kind);
      expect(label).not.toContain("_");
    }
  });
});
