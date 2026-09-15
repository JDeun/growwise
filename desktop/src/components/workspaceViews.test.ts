import { describe, expect, it } from "vitest";

import { isWorkspaceView, WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceViews", () => {
  it("keeps the eight product workspaces explicit", () => {
    expect(WORKSPACE_VIEWS).toHaveLength(8);
    expect(isWorkspaceView("materials")).toBe(true);
    expect(isWorkspaceView("unknown")).toBe(false);
  });
});
