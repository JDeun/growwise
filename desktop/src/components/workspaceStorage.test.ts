import { describe, expect, it, vi } from "vitest";

import { LAST_WORKSPACE_KEY, readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";

describe("workspaceStorage", () => {
  it("falls back to home for invalid or unavailable storage", () => {
    expect(readWorkspaceView({ getItem: () => "invalid" })).toBe("home");
    expect(readWorkspaceView({ getItem: () => { throw new Error("blocked"); } })).toBe("home");
  });

  it("restores and persists a valid view", () => {
    expect(readWorkspaceView({ getItem: () => "materials" })).toBe("materials");
    const setItem = vi.fn();
    writeWorkspaceView({ setItem }, "growth");
    expect(setItem).toHaveBeenCalledWith(LAST_WORKSPACE_KEY, "growth");
  });

  it("does not break navigation when persistence is blocked", () => {
    expect(() => writeWorkspaceView({ setItem: () => { throw new Error("blocked"); } }, "growth")).not.toThrow();
  });
});
