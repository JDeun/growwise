import { describe, expect, it } from "vitest";

import type { ResourceRecord } from "./api";
import { canMutateResourceInChildView, resourceScopeLabel } from "./resource-scope";

function resource(childId: string | null): ResourceRecord {
  return {
    id: "resource-1",
    kind: "note",
    title: "자료",
    child_id: childId,
    summary: null,
    content: null,
    source_url: null,
    source_name: null,
    author: null,
    tags: [],
    stage_tags: [],
    provenance: {},
  };
}

describe("resource child scope presentation", () => {
  it("keeps global and current-child resources editable", () => {
    expect(resourceScopeLabel(resource(null), "child-a")).toBe("공용");
    expect(canMutateResourceInChildView(resource(null), "child-a")).toBe(true);
    expect(resourceScopeLabel(resource("child-a"), "child-a")).toBe("현재 아이");
    expect(canMutateResourceInChildView(resource("child-a"), "child-a")).toBe(true);
  });

  it("marks sibling-shared resources as read only in the current child view", () => {
    expect(resourceScopeLabel(resource("child-b"), "child-a")).toBe("다른 아이에서 공유됨");
    expect(canMutateResourceInChildView(resource("child-b"), "child-a")).toBe(false);
  });
});
