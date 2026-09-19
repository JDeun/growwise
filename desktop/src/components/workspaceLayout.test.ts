import { describe, expect, it } from "vitest";

import { WORKSPACE_LAYOUT } from "./workspaceLayout";
import { PRODUCT_WORKSPACE_VIEWS, WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceLayout", () => {
  it("assigns every routable workspace an explicit layout", () => {
    for (const view of WORKSPACE_VIEWS) {
      expect(WORKSPACE_LAYOUT[view].length).toBeGreaterThan(0);
    }
  });

  it("recomposes legacy tools beneath the intended product workspaces", () => {
    expect(PRODUCT_WORKSPACE_VIEWS).toContain("profile");
    expect(WORKSPACE_LAYOUT.profile).toEqual(["profile", "growth"]);
    expect(WORKSPACE_LAYOUT.learning).toEqual(["learning-records", "observations"]);
    expect(WORKSPACE_LAYOUT.materials).toEqual(["materials", "library", "discovery", "activities"]);
    expect(WORKSPACE_LAYOUT.conversation).toEqual(["search"]);
    expect(WORKSPACE_LAYOUT.backup).toEqual(["backup"]);
    expect(WORKSPACE_LAYOUT.settings).toEqual(["settings"]);
    expect(WORKSPACE_LAYOUT.help).toEqual(["help"]);
  });
});
