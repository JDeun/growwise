import { describe, expect, it, vi } from "vitest";

import { LAST_WORKSPACE_KEY, readWorkspaceView, writeWorkspaceView } from "./workspaceStorage";

describe("workspaceStorage", () => {
  it("falls back to home for an invalid stored view", () => {
    expect(readWorkspaceView({ getItem: () => "invalid" })).toBe("home");
  });

  it("restores and persists a valid view", () => {
    expect(readWorkspaceView({ getItem: () => "materials" })).toBe("materials");
    const setItem = vi.fn();
    writeWorkspaceView({ setItem }, "growth");
    expect(setItem).toHaveBeenCalledWith(LAST_WORKSPACE_KEY, "growth");
  });
});
