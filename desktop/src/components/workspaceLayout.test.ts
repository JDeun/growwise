import { describe, expect, it } from "vitest";

import { WORKSPACE_LAYOUT } from "./workspaceLayout";
import { WORKSPACE_VIEWS } from "./workspaceViews";

describe("workspaceLayout", () => {
  it("assigns every product workspace an explicit layout", () => {
    for (const view of WORKSPACE_VIEWS) {
      expect(WORKSPACE_LAYOUT[view].length).toBeGreaterThan(0);
    }
    expect(WORKSPACE_LAYOUT.materials).toContain("materials");
    expect(WORKSPACE_LAYOUT.settings).toContain("settings");
  });
});
