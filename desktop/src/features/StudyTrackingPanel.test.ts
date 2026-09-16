import { describe, expect, it } from "vitest";

import { isSecondaryStage } from "./StudyTrackingPanel";

describe("StudyTrackingPanel stage gate", () => {
  it("shows the specialized tracker only for middle and high school stages", () => {
    expect(isSecondaryStage("middle")).toBe(true);
    expect(isSecondaryStage("high")).toBe(true);
    expect(isSecondaryStage("infant_0_2")).toBe(false);
    expect(isSecondaryStage("preschool_3_5")).toBe(false);
    expect(isSecondaryStage("elementary")).toBe(false);
    expect(isSecondaryStage(null)).toBe(false);
    expect(isSecondaryStage(undefined)).toBe(false);
  });
});
