import { describe, expect, it } from "vitest";

import type { GeneratedMaterial, MaterialStatus } from "./api";
import { canPrintMaterial, materialLane } from "./material-workflow";

const base: GeneratedMaterial = {
  id: "m1",
  child_id: "c1",
  kind: "reading_activity",
  title: "읽기",
  content_markdown: "# 읽기",
  status: "draft",
  source_refs: [],
  generator_mode: "template",
  review_note: null,
  request_topic: "읽기",
  request_goal: null,
  version: 1,
  parent_material_id: null,
  version_note: null,
};

describe("material workflow policy", () => {
  it.each<MaterialStatus>(["draft", "review_pending", "revision_requested", "rejected", "archived"])(
    "never permits print for %s material",
    (status) => expect(canPrintMaterial({ ...base, status })).toBe(false),
  );

  it("permits print only after explicit parent approval", () => {
    expect(canPrintMaterial({ ...base, status: "approved" })).toBe(true);
  });

  it.each([
    ["draft", "review"],
    ["review_pending", "review"],
    ["revision_requested", "review"],
    ["approved", "approved"],
    ["rejected", "inactive"],
    ["archived", "inactive"],
  ] as const)("routes %s into %s lane", (status, lane) => {
    expect(materialLane(status)).toBe(lane);
  });
});
