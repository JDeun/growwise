import { invoke } from "@tauri-apps/api/core";
import { describe, expect, it, vi } from "vitest";

import { createLearningRecord, recordMaterialResult } from "./api";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn().mockResolvedValue({}) }));

describe("learning evidence through both desktop capture bridges", () => {
  it("preserves an explicit false and all optional text/reference values", async () => {
    const evidence = { book_id: "visible-book", ai_hint: "힌트", evidence_checked: false,
      child_reexplanation: "아이의 자기 설명" };
    await createLearningRecord("child-a", {
      kind: "reading_reflection", title: "독서", summary: "함께 읽었다", ...evidence,
    });
    expect(invoke).toHaveBeenLastCalledWith("create_learning_record", {
      childId: "child-a", request: expect.objectContaining(evidence),
    });
    await recordMaterialResult("material-a", {
      outcome: "completed", observation: "설명했다", ...evidence,
    });
    expect(invoke).toHaveBeenLastCalledWith("record_material_result", {
      materialId: "material-a", request: expect.objectContaining(evidence),
    });
  });

  it("keeps omitted evidence unknown rather than inventing a negative check", async () => {
    await createLearningRecord("child-a", { kind: "diary", title: "일기", summary: "썼다" });
    expect(invoke).toHaveBeenLastCalledWith("create_learning_record", {
      childId: "child-a", request: expect.objectContaining({ book_id: null, ai_hint: null,
        evidence_checked: null, child_reexplanation: null }),
    });
    await recordMaterialResult("material-a", { outcome: "partial", observation: "시도했다" });
    expect(invoke).toHaveBeenLastCalledWith("record_material_result", {
      materialId: "material-a", request: expect.objectContaining({ book_id: null, ai_hint: null,
        evidence_checked: null, child_reexplanation: null }),
    });
  });
});
