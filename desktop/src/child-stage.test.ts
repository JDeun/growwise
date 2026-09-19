import { describe, expect, it } from "vitest";

import { stageForBirthDate } from "./child-stage";

describe("stageForBirthDate", () => {
  it("uses the Korean March school-year boundary", () => {
    expect(stageForBirthDate("2019-10-10", new Date("2026-02-28T12:00:00"))).toBeNull();
    expect(stageForBirthDate("2019-10-10", new Date("2026-03-01T12:00:00"))).toBe("elementary");
    expect(stageForBirthDate("2013-10-10", new Date("2026-03-01T12:00:00"))).toBe("middle");
    expect(stageForBirthDate("2010-10-10", new Date("2026-03-01T12:00:00"))).toBe("high");
  });

  it("distinguishes infant and preschool by completed months", () => {
    expect(stageForBirthDate("2024-04-01", new Date("2026-09-19T12:00:00"))).toBe("infant_0_2");
    expect(stageForBirthDate("2023-01-01", new Date("2026-09-19T12:00:00"))).toBe("preschool_3_5");
  });

  it("rejects empty, invalid, or future values", () => {
    expect(stageForBirthDate("", new Date("2026-09-19T12:00:00"))).toBeNull();
    expect(stageForBirthDate("not-a-date", new Date("2026-09-19T12:00:00"))).toBeNull();
    expect(stageForBirthDate("2027-01-01", new Date("2026-09-19T12:00:00"))).toBeNull();
  });
});
