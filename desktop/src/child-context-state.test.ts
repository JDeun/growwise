import { describe, expect, it } from "vitest";

import { CHILD_CONTEXT_KEYS, childContextState, errorMessage } from "./child-context-state";

describe("child context state", () => {
  it("initializes every child-scoped domain independently", () => {
    const state = childContextState("loading");
    expect(Object.keys(state)).toEqual([...CHILD_CONTEXT_KEYS]);
    expect(Object.values(state).every((value) => value.kind === "loading")).toBe(true);
  });

  it("keeps a useful fallback for non-Error rejections", () => {
    expect(errorMessage("network", "다시 시도해 주세요.")).toBe("다시 시도해 주세요.");
    expect(errorMessage(new Error("연결 실패"), "fallback")).toBe("연결 실패");
  });
});
