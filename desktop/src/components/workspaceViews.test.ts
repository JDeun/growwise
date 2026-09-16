import { describe, expect, it } from "vitest";

import { isWorkspaceView, WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceViews", () => {
  it("keeps the ten product workspaces explicit", () => {
    expect(WORKSPACE_VIEWS).toHaveLength(10);
    expect(isWorkspaceView("materials")).toBe(true);
    expect(isWorkspaceView("photos")).toBe(true);
    expect(isWorkspaceView("discovery")).toBe(true);
    expect(isWorkspaceView("unknown")).toBe(false);
  });
});
