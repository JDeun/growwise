import { describe, expect, it } from "vitest";

import type { ChildProfile } from "./api";
import { resolveActiveChildId } from "./active-child-context";

const children: ChildProfile[] = [
  { id: "child-a", nickname: "A", stage: "elementary", age_months: 96, interests: [] },
  { id: "child-b", nickname: "B", stage: "infant_0_2", age_months: 10, interests: [] },
];

describe("resolveActiveChildId", () => {
  it("prefers an explicit child when it still exists", () => {
    expect(resolveActiveChildId(children, "child-b", "child-a")).toBe("child-b");
  });

  it("falls back to the remembered child and then the first child", () => {
    expect(resolveActiveChildId(children, "missing", "child-b")).toBe("child-b");
    expect(resolveActiveChildId(children, "missing", "also-missing")).toBe("child-a");
  });

  it("returns an empty selection when there are no profiles", () => {
    expect(resolveActiveChildId([], "child-a", "child-b")).toBe("");
  });
});
