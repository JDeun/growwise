import { describe, expect, it } from "vitest";
import { queueMaterialComposition, takeMaterialComposition } from "./material-composition-request";
import type { MaterialAction } from "./api";

const action: MaterialAction = {
  material_kind: "reading_activity", topic: "동물 책 활동",
  source_refs: ["resource:book-1"], needs_book_selection: false,
};

describe("conversation to material composition", () => {
  it("consumes a request once for the same child", () => {
    queueMaterialComposition("child-a", action);
    expect(takeMaterialComposition("child-a")).toEqual(action);
    expect(takeMaterialComposition("child-a")).toBeNull();
  });
  it("discards another child's request when the active child changes", () => {
    queueMaterialComposition("child-a", action);
    expect(takeMaterialComposition("child-b")).toBeNull();
    expect(takeMaterialComposition("child-a")).toBeNull();
  });
});
