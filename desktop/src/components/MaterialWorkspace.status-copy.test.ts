import { describe, expect, it } from "vitest";
import { MATERIAL_STATUS_LABELS } from "../material-workflow";
describe("material status labels", () => {
  it("does not expose raw lifecycle enum names", () => {
    for (const [status, label] of Object.entries(MATERIAL_STATUS_LABELS)) {
      expect(label).not.toBe(status);
      expect(label).not.toContain("_");
    }
  });
});
