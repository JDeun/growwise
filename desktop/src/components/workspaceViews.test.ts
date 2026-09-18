import { describe, expect, it } from "vitest";

import {
  isWorkspaceView,
  LEGACY_WORKSPACE_VIEWS,
  PRODUCT_WORKSPACE_VIEWS,
  WORKSPACE_VIEWS,
} from "./workspaceViews";

describe("workspaceViews", () => {
  it("keeps nine user-facing product workspaces explicit", () => {
    expect(PRODUCT_WORKSPACE_VIEWS).toEqual([
      "home",
      "profile",
      "learning",
      "materials",
      "photos",
      "conversation",
      "backup",
      "settings",
      "help",
    ]);
  });

  it("keeps legacy feature routes routable but out of product navigation", () => {
    expect(LEGACY_WORKSPACE_VIEWS).toEqual([
      "observations",
      "growth",
      "activities",
      "search",
      "discovery",
      "library",
    ]);
    expect(WORKSPACE_VIEWS).toHaveLength(15);
    expect(isWorkspaceView("conversation")).toBe(true);
    expect(isWorkspaceView("backup")).toBe(true);
    expect(isWorkspaceView("discovery")).toBe(true);
    expect(isWorkspaceView("unknown")).toBe(false);
  });
});
