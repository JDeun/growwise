import { describe, expect, it } from "vitest";

import { isWorkspaceView, WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceViews", () => {
  it("keeps the eleven product workspaces explicit", () => {
    expect(WORKSPACE_VIEWS).toHaveLength(11);
    expect(isWorkspaceView("materials")).toBe(true);
    expect(isWorkspaceView("photos")).toBe(true);
    expect(isWorkspaceView("learning_records")).toBe(true);
    expect(isWorkspaceView("discovery")).toBe(true);
    expect(isWorkspaceView("unknown")).toBe(false);
  });
});
